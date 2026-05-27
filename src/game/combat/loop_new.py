"""Combat tick loop (T20/T26 unified).

run() is the entry point — takes a compiled loadout and runs the full combat.
resolve_combat() delegates to this via the recorder bridge.

The loop implements:
- Action/movement energy meters with overflow carry
- Deterministic ordering of triggered meters
- BFS-based pathing and movement
- Auto-attack resolution with target selection
- Ability casting (via the T20 ability framework)
- Status/modifier processing
- Map effects
- Sudden death timeout
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from src.game.bosses.data import BOSS_DEFS
from src.game.combat.context import CombatContext, hex_distance, HEX_DIRECTIONS, BOARD_WIDTH, BOARD_HEIGHT
from src.game.combat.recorder import BattleResultRecorder
from src.game.content import ENEMY_DEF_BY_ID
from src.game.effects import EventBus, Lifetime, SourceTag
from src.game.events import CombatStartEvent, DeathEvent, TickEvent
from src.game.formation import plan_enemy_formation
from src.game.piece import Piece, ActiveSlot
from src.game.status import STATUS_DEFS, StatusGate, StatusInstance
from src.game.weather_effects import damage_modifier


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TICK_MS = 10
ROUND_TICKS = 600
ENERGY_THRESHOLD = 60_000
MAX_TICKS = 12_000

# Sudden death: kicks in at MAX_TICKS, escalating DOT per tick
SUDDEN_DEATH_TICK_START = MAX_TICKS
# Hard cap — sudden-death DOT will resolve combat well before this
HARD_CAP_TICKS = MAX_TICKS + 2_000

# Damage model constants (T3 MVP lock)
AUTO_STR_COEFF = 1.0
AUTO_INT_COEFF = 0.2
ABILITY_STR_COEFF = 0.2
ABILITY_INT_COEFF = 4.2
MITIGATION_CONSTANT = 100
CRIT_MULTIPLIER: float = 1.5

DMG_PHYSICAL = "physical"
DMG_MAGICAL = "magical"
DMG_TRUE = "true"

# Internal meter kinds
_KIND_MOVEMENT = "movement"
_KIND_ACTION = "action"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _on_board(q: int, r: int) -> bool:
    return 0 <= q < BOARD_WIDTH and 0 <= r < BOARD_HEIGHT


def _both_sides_alive(pieces: list[Piece]) -> bool:
    team = any(p.alive and not p.is_enemy for p in pieces)
    enemy = any(p.alive and p.is_enemy for p in pieces)
    return team and enemy


def _effective_stat(piece: Piece, stat: str) -> float:
    """Get effective stat for meter advancement."""
    return piece.stat(stat)


def _opponents(piece: Piece, pieces: list[Piece]) -> list[Piece]:
    """All living enemies of the given piece."""
    return [p for p in pieces if p.alive and p.is_enemy != piece.is_enemy]


def _select_target(piece: Piece, candidates: list[Piece]) -> Piece | None:
    """Deterministic target priority (plan section 3.4)."""
    if not candidates:
        return None

    def key(target: Piece) -> tuple[float, int, float, float, str]:
        distance = hex_distance(
            piece.position_q, piece.position_r, target.position_q, target.position_r
        )
        hp_pct = target.hp / target.max_hp if target.max_hp > 0 else 0.0
        return (-target.stat("threat"), distance, hp_pct, target.hp, target.id)

    return min(candidates, key=key)


# ---------------------------------------------------------------------------
# Pathing (BFS-based, matching legacy)
# ---------------------------------------------------------------------------


def _next_step_toward(
    piece: Piece,
    enemy_living: list[Piece],
    occupied: set[tuple[int, int]],
) -> tuple[int, int] | None:
    """One BFS step toward the nearest cell in attack range of any enemy."""
    attack_range = int(piece.stat("attack_range"))

    goals: list[tuple[int, int]] = []
    for q in range(BOARD_WIDTH):
        for r in range(BOARD_HEIGHT):
            if (q, r) in occupied:
                continue
            for enemy in enemy_living:
                if hex_distance(q, r, enemy.position_q, enemy.position_r) <= attack_range:
                    goals.append((q, r))
                    break
    if not goals:
        return None

    # Multi-source BFS outward from every goal cell over free tiles.
    dist: dict[tuple[int, int], int] = {cell: 0 for cell in goals}
    queue: deque[tuple[int, int]] = deque(sorted(goals))
    while queue:
        cell = queue.popleft()
        base = dist[cell]
        for dq, dr in HEX_DIRECTIONS:
            neighbour = (cell[0] + dq, cell[1] + dr)
            if neighbour in dist:
                continue
            if not _on_board(*neighbour) or neighbour in occupied:
                continue
            dist[neighbour] = base + 1
            queue.append(neighbour)

    # Step into the free neighbour closest to a goal; ties break by direction.
    start = (piece.position_q, piece.position_r)
    best: tuple[int, int] | None = None
    best_dist: int | None = None
    for dq, dr in HEX_DIRECTIONS:
        neighbour = (start[0] + dq, start[1] + dr)
        if not _on_board(*neighbour) or neighbour in occupied:
            continue
        neighbour_dist = dist.get(neighbour)
        if neighbour_dist is None:
            continue
        if best_dist is None or neighbour_dist < best_dist:
            best_dist = neighbour_dist
            best = neighbour
    return best


# ---------------------------------------------------------------------------
# Damage pipeline (matching legacy integer behavior)
# ---------------------------------------------------------------------------


def _effective_mitigation(mitigation_stat: float, pen_flat: float, pen_pct: float) -> float:
    """Target mitigation stat after attacker's penetration."""
    after_pct = mitigation_stat * (1.0 - pen_pct)
    return max(0.0, after_pct - pen_flat)


def _mitigated_damage(
    raw: float,
    mitigation_stat: float,
    damage_type: str,
    pen_flat: float,
    pen_pct: float,
) -> int:
    """Bounded mitigation; final integer damage clamped to at least 1."""
    if damage_type == DMG_TRUE:
        final = raw
    else:
        effective = _effective_mitigation(mitigation_stat, pen_flat, pen_pct)
        reduction = effective / (effective + MITIGATION_CONSTANT)
        final = raw * (1.0 - reduction)
    return max(1, round(final))


def _apply_hit(
    attacker: Piece,
    target: Piece,
    str_coeff: float,
    int_coeff: float,
    damage_type: str,
    can_crit: bool,
) -> tuple[int, bool]:
    """Calculate and apply damage. Returns (damage_amount, is_crit).

    Applies Affinity Clash and mitigation matching legacy behavior.
    """
    strength = attacker.stat("strength")
    intelligence = attacker.stat("intelligence")
    raw = str_coeff * strength + int_coeff * intelligence

    # Affinity Clash — affinity damage triangle
    raw *= damage_modifier(attacker.affinity, target.affinity)

    # Critical strike (deterministic cadence)
    is_crit = False
    if can_crit and attacker.stat("crit_chance") > 0.0:
        attacker.crit_counter += 1
        cadence = max(1, round(1.0 / attacker.stat("crit_chance")))
        if attacker.crit_counter >= cadence:
            is_crit = True
            attacker.crit_counter = 0
    if is_crit:
        raw *= CRIT_MULTIPLIER

    # Mitigation
    if damage_type == DMG_MAGICAL:
        mitigation = target.stat("resistance")
    else:
        mitigation = target.stat("armor")
    pen_flat = attacker.stat("penetration")
    pen_pct = attacker.stat("penetration_pct")
    damage = _mitigated_damage(raw, mitigation, damage_type, pen_flat, pen_pct)

    # Apply damage
    target.hp = max(0.0, target.hp - damage)

    # Kill check
    if target.hp <= 0 and target.alive:
        target.alive = False
        target.hp = 0.0

    return damage, is_crit


# ---------------------------------------------------------------------------
# Movement resolution
# ---------------------------------------------------------------------------


def _resolve_movement(
    piece: Piece,
    pieces: list[Piece],
    tick: int,
    recorder: BattleResultRecorder | None,
) -> None:
    """Resolve a movement trigger for a piece."""
    # Gate: root/frozen blocks movement
    if piece.is_gated(StatusGate.BLOCKS_MOVEMENT):
        piece.movement_energy = ENERGY_THRESHOLD
        return

    enemy_living = _opponents(piece, pieces)
    attack_range = int(piece.stat("attack_range"))

    # Rule 1: in range of any enemy -> hold meter at threshold.
    in_range = any(
        hex_distance(piece.position_q, piece.position_r, e.position_q, e.position_r)
        <= attack_range
        for e in enemy_living
    )
    if in_range or not enemy_living:
        piece.movement_energy = ENERGY_THRESHOLD
        return

    occupied = {
        (p.position_q, p.position_r)
        for p in pieces
        if p.alive and p is not piece
    }
    step = _next_step_toward(piece, enemy_living, occupied)

    # Rule 3: no path -> hold meter at threshold.
    if step is None:
        piece.movement_energy = ENERGY_THRESHOLD
        return

    # Rule 2: step one hex; carry meter overflow.
    piece.position_q, piece.position_r = step
    piece.movement_energy -= ENERGY_THRESHOLD
    if recorder:
        recorder.record_move(piece.id, tick, step[0], step[1])


# ---------------------------------------------------------------------------
# Action resolution (auto-attack / cast)
# ---------------------------------------------------------------------------


def _resolve_action(
    piece: Piece,
    pieces: list[Piece],
    tick: int,
    recorder: BattleResultRecorder | None,
    ctx: CombatContext | None = None,
) -> None:
    """Resolve an action trigger for a piece."""
    living_enemies = _opponents(piece, pieces)
    if not living_enemies:
        piece.action_energy = ENERGY_THRESHOLD
        return

    # Keep current target while it is still a living enemy.
    current: Piece | None = None
    if piece.target_id is not None:
        for enemy in living_enemies:
            if enemy.id == piece.target_id:
                current = enemy
                break

    # Rule 1: cast when mana is full and any valid target exists (legacy fallback).
    # Check if piece has ability slots with full mana AND the ability is NOT in the registry
    # (registered abilities are handled by the ability framework's process_casts)
    from src.game.registries import ABILITY_REGISTRY  # deferred: avoids circular import
    has_unregistered_cast = False
    if piece.actives and not piece.is_gated(StatusGate.BLOCKS_CAST):
        slot = piece.actives[0]
        if slot.current_mana >= slot.cost and slot.ability_id not in ABILITY_REGISTRY:
            has_unregistered_cast = True

    if has_unregistered_cast:
        slot = piece.actives[0]
        target = current if current is not None else _select_target(piece, living_enemies)
        if target is not None and ctx:
            piece.target_id = target.id
            # Use ctx pipeline so on_damage_pre/on_damage_dealt/on_damage_taken fire
            strength = piece.stat("strength")
            intelligence = piece.stat("intelligence")
            raw = ABILITY_STR_COEFF * strength + ABILITY_INT_COEFF * intelligence
            final = ctx.deal_damage(
                piece, target, raw, SourceTag.ABILITY,
                crit=None, damage_type=DMG_MAGICAL,
            )
            if recorder:
                recorder.record_cast(piece.id, target.id, tick, int(final), DMG_MAGICAL, False)
            slot.current_mana = 0.0
            piece.action_energy -= ENERGY_THRESHOLD
            return

    # Rule 2: auto-attack when at least one enemy is in attack range.
    if piece.is_gated(StatusGate.BLOCKS_ATTACK):
        piece.action_energy -= ENERGY_THRESHOLD
        return
    attack_range = int(piece.stat("attack_range"))
    in_range_enemies = [
        e
        for e in living_enemies
        if hex_distance(piece.position_q, piece.position_r, e.position_q, e.position_r)
        <= attack_range
    ]
    if in_range_enemies and ctx:
        if current is not None and any(e is current for e in in_range_enemies):
            target = current
        else:
            target = _select_target(piece, in_range_enemies)
        assert target is not None
        piece.target_id = target.id
        # Use ctx pipeline so on_attack_start/on_attack_landed and damage hooks fire
        ctx.trigger_basic_attack(piece, target)
        piece.action_energy -= ENERGY_THRESHOLD
        return

    # Rule 3: idle-hold meter at threshold (no overflow accumulation).
    piece.action_energy = ENERGY_THRESHOLD


# ---------------------------------------------------------------------------
# Deterministic ordering
# ---------------------------------------------------------------------------


def _event_sort_key(entry: tuple[Piece, str]) -> tuple[float, float, int, int]:
    """Deterministic same-tick total ordering (plan section 3.5)."""
    piece, kind = entry
    as_val = piece.stat("attack_speed")
    return (
        -as_val,
        -as_val,
        piece.speed_tiebreaker,
        0 if kind == _KIND_MOVEMENT else 1,
    )


# ---------------------------------------------------------------------------
# Status processing
# ---------------------------------------------------------------------------


def process_statuses(ctx: CombatContext, pieces: list[Piece]) -> None:
    """Process status effects each tick: expire, DOT, decay."""
    for piece in pieces:
        if not piece.alive:
            continue
        expired = []
        for i, status in enumerate(piece.statuses):
            status.remaining_ticks -= 1
            if status.remaining_ticks <= 0:
                expired.append(i)
                continue
            # DOT processing
            status_def = STATUS_DEFS.get(status.status_id)
            if status_def and status_def.dot_per_tick > 0:
                dot_amount = status_def.dot_per_tick
                if status_def.dot_scales_with_stacks:
                    dot_amount *= status.stacks
                attacker = piece
                if status.source_id:
                    for p in ctx.all_pieces():
                        if p.id == status.source_id and p.alive:
                            attacker = p
                            break
                if status_def.dot_true_damage:
                    ctx.deal_damage(attacker, piece, dot_amount, SourceTag.TRUE)
                else:
                    ctx.deal_damage(attacker, piece, dot_amount, SourceTag.DOT, damage_type="magical")
                # Decay stacks after DOT
                if status_def.decay_stacks_per_tick and status.stacks > 0:
                    status.stacks -= 1
                    if status.stacks == 0:
                        expired.append(i)

        # Remove expired statuses (in reverse order to maintain indices)
        for i in reversed(expired):
            status_inst = piece.statuses[i]
            piece.statuses.pop(i)
            from src.game.events import StatusEvent
            event = StatusEvent(target=piece, status_id=status_inst.status_id)
            ctx.bus.fire("on_status_expired", event, ctx=ctx)


# ---------------------------------------------------------------------------
# Modifier expiry
# ---------------------------------------------------------------------------


def expire_modifiers(ctx: CombatContext, pieces: list[Piece]) -> None:
    """Remove TIMED modifiers that have expired."""
    tick = ctx.current_tick
    for piece in pieces:
        piece.modifiers = [
            m for m in piece.modifiers
            if not (m.lifetime == Lifetime.TIMED and m.expires_at_tick is not None and tick >= m.expires_at_tick)
        ]


# ---------------------------------------------------------------------------
# Cast resolution (ability framework)
# ---------------------------------------------------------------------------


def process_casts(ctx: CombatContext, piece: Piece) -> None:
    """Check if any ability slots are ready to cast. Multi-slot support."""
    from src.game.registries import ABILITY_REGISTRY

    if piece.is_gated(StatusGate.BLOCKS_CAST):
        return
    if not piece.alive:
        return

    # Iterate slots by descending priority
    sorted_indices = sorted(
        range(len(piece.actives)),
        key=lambda i: -piece.actives[i].priority,
    )
    for slot_idx in sorted_indices:
        slot = piece.actives[slot_idx]
        if slot.current_mana < slot.cost:
            continue
        # Skip unregistered abilities without spending mana
        if slot.ability_id not in ABILITY_REGISTRY:
            continue
        # Spend mana and cast
        slot.current_mana = 0.0
        ctx.cast_ability(piece, slot_idx=slot_idx)
        # If piece got silenced or killed by the cast/hooks, stop
        if piece.is_gated(StatusGate.BLOCKS_CAST) or not piece.alive:
            return


# ---------------------------------------------------------------------------
# Board-state processing (map effects output)
# ---------------------------------------------------------------------------


def _process_board_state(ctx: CombatContext, pieces: list[Piece]) -> None:
    """Apply board-state effects to living pieces each tick."""
    board = ctx.board_state
    if not board.slow_cells:
        return
    for piece in pieces:
        if not piece.alive:
            continue
        pos = (piece.position_q, piece.position_r)
        if board.is_slow(*pos):
            ctx.apply_status(piece, "slow", duration_ticks=3)


# ---------------------------------------------------------------------------
# Spawn assignment
# ---------------------------------------------------------------------------


@dataclass
class _FormationEnemy:
    """Shim for feeding Piece enemies into plan_enemy_formation."""
    piece_id: str
    tier: int
    speed_tiebreaker: int


def assign_spawns(pieces: list[Piece]) -> None:
    """Team to left columns, enemies via role-aware formation planner (T24)."""
    team_index = 0
    enemies: list[Piece] = []
    for piece in pieces:
        if not piece.is_enemy:
            piece.position_q = team_index // BOARD_HEIGHT
            piece.position_r = team_index % BOARD_HEIGHT
            team_index += 1
            continue
        enemies.append(piece)

    if not enemies:
        return

    boss_positions = {boss.id: boss.spawn_position for boss in BOSS_DEFS.values()}
    formation_input: list[_FormationEnemy] = []
    boss_position: tuple[int, int] | None = None

    for enemy in enemies:
        if enemy.id in boss_positions:
            tier = 10
            if boss_position is None:
                boss_position = boss_positions[enemy.id]
        else:
            enemy_def = ENEMY_DEF_BY_ID.get(enemy.id)
            tier = enemy_def.tier if enemy_def is not None else 1
        formation_input.append(
            _FormationEnemy(
                piece_id=enemy.id,
                tier=tier,
                speed_tiebreaker=enemy.speed_tiebreaker,
            )
        )

    formation = plan_enemy_formation(
        formation_input,
        ENEMY_DEF_BY_ID,
        boss_position=boss_position,
    )
    for enemy_index, enemy in enumerate(enemies):
        if enemy.speed_tiebreaker in formation:
            enemy.position_q, enemy.position_r = formation[enemy.speed_tiebreaker]
        else:
            enemy.position_q = BOARD_WIDTH - 1 - (enemy_index // BOARD_HEIGHT)
            enemy.position_r = enemy_index % BOARD_HEIGHT


# ---------------------------------------------------------------------------
# Main tick loop
# ---------------------------------------------------------------------------


def run(ctx: CombatContext, recorder: BattleResultRecorder | None = None) -> str:
    """Run the combat loop. Returns winner: 'team', 'enemy', or 'draw'.

    If a recorder is provided, records all events for BattleResult construction.
    """
    pieces = ctx.all_pieces()

    # Fire on_combat_start
    ctx.bus.fire("on_combat_start", CombatStartEvent(), ctx=ctx)

    if not _both_sides_alive(pieces):
        # Immediate resolution
        team_alive = any(p.alive and not p.is_enemy for p in pieces)
        winner = "team" if team_alive else "enemy"
        if recorder:
            recorder.set_duration(0)
        ctx.end_combat(winner)
        return winner

    duration = 0
    timed_out = False
    ended_early = False

    for tick in range(1, HARD_CAP_TICKS + 1):
        ctx.current_tick = tick
        duration = tick

        if ctx.combat_ended:
            ended_early = True
            break

        # Fire on_tick (for hooks/abilities listening to tick events)
        ctx.bus.fire("on_tick", TickEvent(tick=tick), ctx=ctx)

        # Sudden death: apply escalating DOT to all living pieces once MAX_TICKS is passed
        if tick >= SUDDEN_DEATH_TICK_START:
            for piece in pieces:
                if piece.alive:
                    ctx.apply_status(piece, "sudden_death", 3)

        # Process map effects (board-cell modifiers: slow tiles etc.)
        _process_board_state(ctx, pieces)

        # Process statuses (expire, DOT)
        process_statuses(ctx, pieces)

        # Expire timed modifiers
        expire_modifiers(ctx, pieces)

        if not _both_sides_alive(pieces):
            ended_early = True
            break

        # Step 1: advance every living meter.
        for piece in pieces:
            if not piece.alive:
                continue
            # Gates: stun blocks all meter advancement
            if piece.is_gated(StatusGate.BLOCKS_ACTION):
                continue

            as_val = int(piece.stat("attack_speed"))
            ms_val = int(piece.stat("move_speed"))
            mr_val = int(piece.stat("mana_regen"))

            piece.action_energy += as_val
            piece.movement_energy += ms_val

            # Mana regen — to all ability slots
            if mr_val > 0:
                for slot in piece.actives:
                    slot.current_mana = min(slot.cost, slot.current_mana + mr_val)

        # Step 2: collect triggered meters.
        triggered: list[tuple[Piece, str]] = []
        for piece in pieces:
            if not piece.alive:
                continue
            if piece.movement_energy >= ENERGY_THRESHOLD:
                triggered.append((piece, _KIND_MOVEMENT))
            if piece.action_energy >= ENERGY_THRESHOLD:
                triggered.append((piece, _KIND_ACTION))

        # Step 3: resolve in deterministic order.
        triggered.sort(key=_event_sort_key)
        for piece, kind in triggered:
            if not piece.alive:
                continue
            if kind == _KIND_MOVEMENT:
                _resolve_movement(piece, pieces, tick, recorder)
            else:
                _resolve_action(piece, pieces, tick, recorder, ctx)
            if not _both_sides_alive(pieces):
                ended_early = True
                break
        if ended_early:
            break

        # Cast resolution for registered abilities (T20 ability framework)
        for piece in pieces:
            if not piece.alive:
                continue
            process_casts(ctx, piece)
            if not _both_sides_alive(pieces):
                ended_early = True
                break

        if ended_early:
            break

    if not ended_early:
        timed_out = True
        duration = HARD_CAP_TICKS
    elif duration >= SUDDEN_DEATH_TICK_START:
        # Combat resolved by sudden-death DOT — still counts as timed out
        timed_out = True

    if recorder:
        recorder.set_duration(duration, timed_out)

    # Determine winner
    if ctx.combat_ended:
        return ctx.winner or "draw"

    team_alive = any(p.alive and not p.is_enemy for p in pieces)
    enemy_alive = any(p.alive and p.is_enemy for p in pieces)

    if team_alive and not enemy_alive:
        winner = "team"
    elif enemy_alive and not team_alive:
        winner = "enemy"
    else:
        winner = "draw"

    ctx.end_combat(winner)
    return winner
