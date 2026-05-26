"""Tick-based auto-resolved combat engine (T3 MVP).

`resolve_combat` is a pure, deterministic function: identical inputs always
produce a byte-equal `BattleResult`. Weather Favor is applied once at init
via `weather_effects.apply_weather`; Affinity Clash (the affinity damage triangle) is
resolved per hit during damage application.
"""

from __future__ import annotations

from collections import deque

from src.game.models import (
    BattleEvent,
    BattleResult,
    Champion,
    CombatOutcome,
    CombatPieceState,
    Enemy,
    WeatherState,
)
from src.game.weather_effects import apply_weather, damage_modifier

# --- Engine constants (T3 MVP lock, plan section 3.1) ---
TICK_MS = 10
ROUND_TICKS = 600
ENERGY_THRESHOLD = 60_000
MAX_TICKS = 7_200

# --- Board (plan section 4) ---
BOARD_WIDTH = 10
BOARD_HEIGHT = 7

# Axial hex neighbour offsets in a fixed order — drives deterministic pathing.
HEX_DIRECTIONS: tuple[tuple[int, int], ...] = (
    (1, 0),
    (1, -1),
    (0, -1),
    (-1, 0),
    (-1, 1),
    (0, 1),
)

# --- Damage model (plan section 3.6) ---
AUTO_STR_COEFF = 1.0
AUTO_INT_COEFF = 0.2
ABILITY_STR_COEFF = 0.2
ABILITY_INT_COEFF = 4.2
MITIGATION_CONSTANT = 100

DMG_PHYSICAL = "physical"
DMG_MAGICAL = "magical"
DMG_TRUE = "true"

CRIT_MULTIPLIER: float = 1.5


# --- Event log types ---
EVENT_MOVE = "move"
EVENT_ATTACK = "attack"
EVENT_CAST = "cast"
EVENT_DEATH = "death"

# Internal meter kinds.
_KIND_MOVEMENT = "movement"
_KIND_ACTION = "action"


# --- Effective stat helpers (plan section 3.3) -------------------------------
# Integer-only. Kept as functions so future status effects can gate meter
# gains without touching the tick loop.


def effective_as(piece: CombatPieceState) -> int:
    """Action-energy gained per tick."""
    return piece.attack_speed


def effective_ms(piece: CombatPieceState) -> int:
    """Movement-energy gained per tick."""
    return piece.move_speed


def effective_mr_tick(piece: CombatPieceState) -> int:
    """Mana gained per tick (mana_regen is units per tick, plan 3.1b)."""
    return piece.mana_regen


# --- Hex geometry ------------------------------------------------------------


def hex_distance(q1: int, r1: int, q2: int, r2: int) -> int:
    """Axial hex distance between two cells."""
    return (abs(q1 - q2) + abs(r1 - r2) + abs(q1 + r1 - q2 - r2)) // 2


def _on_board(q: int, r: int) -> bool:
    return 0 <= q < BOARD_WIDTH and 0 <= r < BOARD_HEIGHT


# --- Initialization ----------------------------------------------------------


def _assign_spawns(pieces: list[CombatPieceState]) -> None:
    """Team to left columns, enemies to right columns; stable by input index."""
    team_index = 0
    enemy_index = 0
    for piece in pieces:
        if piece.is_enemy:
            piece.position_q = BOARD_WIDTH - 1 - (enemy_index // BOARD_HEIGHT)
            piece.position_r = enemy_index % BOARD_HEIGHT
            enemy_index += 1
        else:
            piece.position_q = team_index // BOARD_HEIGHT
            piece.position_r = team_index % BOARD_HEIGHT
            team_index += 1


# --- Queries -----------------------------------------------------------------


def _opponents(piece: CombatPieceState, pieces: list[CombatPieceState]) -> list[CombatPieceState]:
    return [p for p in pieces if p.alive and p.is_enemy != piece.is_enemy]


def _both_sides_alive(pieces: list[CombatPieceState]) -> bool:
    team = any(p.alive and not p.is_enemy for p in pieces)
    enemy = any(p.alive and p.is_enemy for p in pieces)
    return team and enemy


def _select_target(
    piece: CombatPieceState, candidates: list[CombatPieceState]
) -> CombatPieceState | None:
    """Deterministic target priority (plan section 3.4)."""
    if not candidates:
        return None

    def key(target: CombatPieceState) -> tuple[int, int, float, int, str]:
        distance = hex_distance(
            piece.position_q, piece.position_r, target.position_q, target.position_r
        )
        hp_pct = target.hp / target.max_hp
        return (-target.threat, distance, hp_pct, target.hp, target.piece_id)

    return min(candidates, key=key)


# --- Pathing (plan section 4 + step 6) ---------------------------------------


def _next_step_toward(
    piece: CombatPieceState,
    enemy_living: list[CombatPieceState],
    occupied: set[tuple[int, int]],
) -> tuple[int, int] | None:
    """One BFS step toward the nearest cell in attack range of any enemy.

    Returns the next cell to move into, or `None` when no path exists.
    """
    # Goal cells: free, on-board cells within attack range of a living enemy.
    goals: list[tuple[int, int]] = []
    for q in range(BOARD_WIDTH):
        for r in range(BOARD_HEIGHT):
            if (q, r) in occupied:
                continue
            for enemy in enemy_living:
                if (
                    hex_distance(q, r, enemy.position_q, enemy.position_r)
                    <= piece.attack_range
                ):
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


# --- Damage ------------------------------------------------------------------


def _effective_mitigation(mitigation_stat: int, pen_flat: int, pen_pct: float) -> int:
    """Target mitigation stat after the attacker's penetration.

    Percent penetration applies first, then flat — `round(stat × (1 − pct)) −
    flat` — and the result is clamped at 0. Order is documented in
    `combat_system_proposal.md` §4.4.
    """
    after_pct = mitigation_stat * (1.0 - pen_pct)
    return max(0, round(after_pct) - pen_flat)


def _mitigated_damage(
    raw: float,
    mitigation_stat: int,
    damage_type: str,
    pen_flat: int,
    pen_pct: float,
) -> int:
    """Bounded mitigation; final integer damage clamped to at least 1.

    `pen_flat` / `pen_pct` are the attacker's penetration — they erode the
    target's mitigation stat before reduction is computed. `true` damage
    ignores mitigation and therefore penetration too.
    """
    if damage_type == DMG_TRUE:
        final = raw
    else:
        effective = _effective_mitigation(mitigation_stat, pen_flat, pen_pct)
        reduction = effective / (effective + MITIGATION_CONSTANT)
        final = raw * (1.0 - reduction)
    return max(1, round(final))


def _apply_hit(
    attacker: CombatPieceState,
    target: CombatPieceState,
    str_coeff: float,
    int_coeff: float,
    damage_type: str,
    event_type: str,
    tick: int,
    events: list[BattleEvent],
    damage_dealt: dict[str, int],
    damage_taken: dict[str, int],
    can_crit: bool,
) -> None:
    raw = str_coeff * attacker.strength + int_coeff * attacker.intelligence
    # Affinity Clash — affinity damage triangle, applied before mitigation.
    raw *= damage_modifier(attacker.affinity, target.affinity)
    is_crit = False
    if can_crit and attacker.crit_chance > 0.0:
        attacker.crit_counter += 1
        if attacker.crit_counter >= round(1.0 / attacker.crit_chance):
            is_crit = True
            attacker.crit_counter = 0
    if is_crit:
        raw *= CRIT_MULTIPLIER
    mitigation = target.resistance if damage_type == DMG_MAGICAL else target.armor
    damage = _mitigated_damage(
        raw, mitigation, damage_type, attacker.penetration, attacker.penetration_pct
    )

    target.hp = max(0, target.hp - damage)
    damage_dealt[attacker.piece_id] += damage
    damage_taken[target.piece_id] += damage
    events.append(
        BattleEvent(
            tick=tick,
            actor_id=attacker.piece_id,
            target_id=target.piece_id,
            event_type=event_type,
            amount=damage,
            note=damage_type,
            is_crit=is_crit,
        )
    )

    if target.hp == 0 and target.alive:
        target.alive = False
        events.append(
            BattleEvent(
                tick=tick,
                actor_id=target.piece_id,
                target_id=attacker.piece_id,
                event_type=EVENT_DEATH,
            )
        )


# --- Resolution --------------------------------------------------------------


def _resolve_movement(
    piece: CombatPieceState,
    pieces: list[CombatPieceState],
    events: list[BattleEvent],
    tick: int,
) -> None:
    enemy_living = _opponents(piece, pieces)

    # Rule 1: in range of any enemy -> hold meter at threshold.
    in_range = any(
        hex_distance(piece.position_q, piece.position_r, e.position_q, e.position_r)
        <= piece.attack_range
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
    events.append(
        BattleEvent(
            tick=tick,
            actor_id=piece.piece_id,
            target_id=None,
            event_type=EVENT_MOVE,
            note=f"{step[0]},{step[1]}",
        )
    )


def _resolve_action(
    piece: CombatPieceState,
    pieces: list[CombatPieceState],
    events: list[BattleEvent],
    tick: int,
    damage_dealt: dict[str, int],
    damage_taken: dict[str, int],
) -> None:
    living_enemies = _opponents(piece, pieces)
    if not living_enemies:
        piece.action_energy = ENERGY_THRESHOLD
        return

    # Keep current target while it is still a living enemy.
    current: CombatPieceState | None = None
    if piece.target_piece_id is not None:
        for enemy in living_enemies:
            if enemy.piece_id == piece.target_piece_id:
                current = enemy
                break

    # Rule 1: cast when mana is full and any valid target exists.
    if piece.mana >= piece.ability_cost:
        target = current if current is not None else _select_target(piece, living_enemies)
        if target is not None:
            piece.target_piece_id = target.piece_id
            _apply_hit(
                piece, target, ABILITY_STR_COEFF, ABILITY_INT_COEFF, DMG_MAGICAL,
                EVENT_CAST, tick, events, damage_dealt, damage_taken,
                can_crit=piece.ability_can_crit,
            )
            piece.mana = 0
            piece.action_energy -= ENERGY_THRESHOLD
            return

    # Rule 2: auto-attack when at least one enemy is in attack range.
    in_range_enemies = [
        e
        for e in living_enemies
        if hex_distance(piece.position_q, piece.position_r, e.position_q, e.position_r)
        <= piece.attack_range
    ]
    if in_range_enemies:
        if current is not None and any(e is current for e in in_range_enemies):
            target = current
        else:
            target = _select_target(piece, in_range_enemies)
        assert target is not None  # in_range_enemies is non-empty
        piece.target_piece_id = target.piece_id
        _apply_hit(
            piece, target, AUTO_STR_COEFF, AUTO_INT_COEFF, DMG_PHYSICAL,
            EVENT_ATTACK, tick, events, damage_dealt, damage_taken,
            can_crit=True,
        )
        piece.action_energy -= ENERGY_THRESHOLD
        return

    # Rule 3: idle-hold meter at threshold (no overflow accumulation).
    piece.action_energy = ENERGY_THRESHOLD


def _event_sort_key(entry: tuple[CombatPieceState, str]) -> tuple[int, int, int, int]:
    """Deterministic same-tick total ordering (plan section 3.5)."""
    piece, kind = entry
    return (
        -effective_as(piece),
        -piece.attack_speed,
        piece.speed_tiebreaker,
        0 if kind == _KIND_MOVEMENT else 1,
    )


# --- Public entry point ------------------------------------------------------


def resolve_combat(
    team: list[Champion],
    enemies: list[Enemy],
    weather: WeatherState,
    *,
    node_id: str = "",
) -> BattleResult:
    """Resolve one battle from start to finish; pure and deterministic.

    Delegates to the unified combat engine (T26): compile_loadout builds
    weather-modified Pieces, the new loop runs the tick simulation, and
    BattleResultRecorder reconstructs the legacy BattleResult format.
    """
    from src.game.combat.context import CombatContext
    from src.game.combat.loop_new import run as run_combat, assign_spawns
    from src.game.combat.recorder import BattleResultRecorder
    from src.game.loadout import compile_loadout

    # Build pieces with weather favor applied
    pieces, bus = compile_loadout(team, enemies, weather, seed=42)

    # Assign speed tiebreakers (stable input ordering)
    for index, piece in enumerate(pieces):
        piece.speed_tiebreaker = index

    # Assign spawn positions
    assign_spawns(pieces)

    # Create recorder
    recorder = BattleResultRecorder(pieces, weather, node_id)
    recorder.register(bus)

    # Build context and run
    ctx = CombatContext(pieces, bus, weather, seed=42)
    winner = run_combat(ctx, recorder)

    return recorder.build_result(winner)
