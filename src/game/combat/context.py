"""CombatContext — the mutator API (T20).

Content interacts with the world ONLY through CombatContext methods.
This is the single point of mutation for all combat state.
Direct mutation architecture — no Effect-as-data, no reducer.
"""

from __future__ import annotations

from typing import Any, Iterable

from src.game.board import BoardState
from src.game.effects import (
    EffectBundle,
    EventBus,
    Hook,
    Modifier,
    Lifetime,
    SourceTag,
    compute_stat,
)
from src.game.events import (
    AttackEvent,
    CastEvent,
    CombatEndEvent,
    CombatStartEvent,
    DamageEvent,
    DeathEvent,
    HealEvent,
    KillEvent,
    ManaEvent,
    PhaseEvent,
    SpawnEvent,
    StatusEvent,
    TickEvent,
)
from src.game.models import WeatherState
from src.game.piece import ActiveSlot, BarrierSegment, Piece
from src.game.rng import SeededRng
from src.game.status import (
    STATUS_DEFS,
    StackBehaviour,
    StatusGate,
    StatusInstance,
)
from src.game.weather_effects import damage_modifier


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TICK_MS = 10
MITIGATION_CONSTANT = 100
CRIT_MULTIPLIER = 1.5

# Action-impairing gates = "hard CC". Scaled cc_immune pieces ignore statuses
# carrying any of these (slow has no gate → soft CC, still lands). (T.28d)
_HARD_CC_GATES = (
    StatusGate.BLOCKS_ACTION,
    StatusGate.BLOCKS_CAST,
    StatusGate.BLOCKS_ATTACK,
    StatusGate.BLOCKS_MOVEMENT,
)

# Board dimensions
BOARD_WIDTH = 10
BOARD_HEIGHT = 7

# Hex directions (axial)
HEX_DIRECTIONS: tuple[tuple[int, int], ...] = (
    (1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1),
)


def hex_distance(q1: int, r1: int, q2: int, r2: int) -> int:
    """Axial hex distance between two cells."""
    dq = q1 - q2
    dr = r1 - r2
    return (abs(dq) + abs(dr) + abs(dq + dr)) // 2


# ---------------------------------------------------------------------------
# CombatContext
# ---------------------------------------------------------------------------


class CombatContext:
    """The mutator API — all combat mutations flow through here.

    Content handlers receive a ctx and call mutators. The event bus fires
    hooks synchronously inside those mutators. Reentrancy is the Python
    call stack.
    """

    def __init__(
        self,
        pieces: list[Piece],
        bus: EventBus,
        weather: WeatherState,
        seed: int = 0,
        board_state: BoardState | None = None,
    ) -> None:
        self._pieces = pieces
        self._bus = bus
        self._weather = weather
        self._rng = SeededRng(seed)
        self._tick = 0
        self._cast_id_counter = 0
        self._hit_id_counter = 0
        self._current_cast_id: int | None = None
        self._combat_ended = False
        self._winner: str | None = None
        # Board dimensions (read by map effects; not used by engine directly yet)
        self._board_width: int = BOARD_WIDTH
        self._board_height: int = BOARD_HEIGHT
        # Board state (map effects write cell modifiers; targeting reads fog_range)
        self._board_state: BoardState = board_state if board_state is not None else BoardState()
        # Live liveness counts — maintained incrementally by kill/spawn/expire_summon
        # so the per-tick / per-action "both sides alive?" check is O(1) instead of
        # rescanning the whole roster (see both_sides_alive). Mutated only here.
        self._alive_team: int = sum(1 for p in pieces if p.alive and not p.is_enemy)
        self._alive_enemy: int = sum(1 for p in pieces if p.alive and p.is_enemy)

    # --- Read-only queries ---

    @property
    def current_tick(self) -> int:
        return self._tick

    @current_tick.setter
    def current_tick(self, value: int) -> None:
        self._tick = value

    @property
    def current_cast_id(self) -> int | None:
        return self._current_cast_id

    @property
    def weather(self) -> WeatherState:
        return self._weather

    @property
    def rng(self) -> SeededRng:
        return self._rng

    @property
    def bus(self) -> EventBus:
        return self._bus

    @property
    def board_state(self) -> BoardState:
        """Live board-cell modifier state. Written by map effects; read by targeting."""
        return self._board_state

    @property
    def combat_ended(self) -> bool:
        return self._combat_ended

    @property
    def winner(self) -> str | None:
        return self._winner

    def enemies_of(self, piece: Piece) -> Iterable[Piece]:
        """All living enemies of the given piece."""
        return [p for p in self._pieces if p.alive and p.is_enemy != piece.is_enemy]

    def allies_of(self, piece: Piece) -> Iterable[Piece]:
        """All living allies of the given piece (including itself)."""
        return [p for p in self._pieces if p.alive and p.is_enemy == piece.is_enemy]

    def all_pieces(self) -> list[Piece]:
        """All pieces (alive or dead)."""
        return self._pieces

    def both_sides_alive(self) -> bool:
        """O(1) — at least one living piece on each side. Counts are maintained
        incrementally by kill / spawn / expire_summon."""
        return self._alive_team > 0 and self._alive_enemy > 0

    def living_pieces(self) -> list[Piece]:
        """All currently alive pieces."""
        return [p for p in self._pieces if p.alive]

    def is_enemy(self, a: Piece, b: Piece) -> bool:
        """Check if two pieces are on opposing teams."""
        return a.is_enemy != b.is_enemy

    def is_alive(self, piece: Piece) -> bool:
        return piece.alive

    # --- Mutators ---

    def deal_damage(
        self,
        attacker: Piece,
        target: Piece,
        amount: float,
        tag: SourceTag,
        *,
        crit: bool | None = None,
        damage_type: str = "magical",
    ) -> float:
        """Deal damage. Returns final amount dealt after mitigation.

        Pipeline:
          raw → × weather_modifier → × crit → fire on_damage_pre → mitigate
          → apply → fire on_damage_dealt → fire on_damage_taken → kill check
        """
        if not target.alive:
            return 0.0

        raw = amount

        # Reduced-potency echo (Spirit @8, T.28d): a recast in flight scales its
        # damage by ctx._echo_potency (default 1.0 outside a recast). Heals/shields
        # are unaffected by design (damage-only). Deterministic call-stack flag.
        raw *= getattr(self, "_echo_potency", 1.0)

        # Weather affinity clash modifier. Environmental damage (hazard tiles,
        # map effects) has no attacker — skip the clash (B.x: NoneType.affinity).
        if attacker is not None:
            raw *= damage_modifier(attacker.affinity, target.affinity)

        # Critical strike. Attacker-less (environmental) damage cannot crit.
        is_crit = False
        if crit is True:
            is_crit = True
        elif crit is None and attacker is not None:
            crit_chance = attacker.stat("crit_chance") if hasattr(attacker, "stat") else 0.0
            can_crit = (tag == SourceTag.BASIC_ATTACK) or attacker.ability_can_crit
            if can_crit and crit_chance > 0.0:
                attacker.crit_counter += 1
                cadence = max(1, round(1.0 / crit_chance))
                if attacker.crit_counter >= cadence:
                    is_crit = True
                    attacker.crit_counter = 0

        if is_crit:
            raw *= CRIT_MULTIPLIER

        # Fire on_damage_pre (reducing hook)
        self._hit_id_counter += 1
        hit_id = self._hit_id_counter
        pre_event = DamageEvent(
            attacker=attacker, target=target, amount=raw,
            tag=tag.value, cast_id=self._current_cast_id, hit_id=hit_id,
            is_crit=is_crit,
        )
        raw = self._bus.fire_reducing("on_damage_pre", pre_event, raw, cast_id=self._current_cast_id, ctx=self)

        # Mitigation
        if tag == SourceTag.TRUE:
            final = raw
        else:
            pen_flat = attacker.stat("penetration") if hasattr(attacker, "stat") else 0.0
            pen_pct = attacker.stat("penetration_pct") if hasattr(attacker, "stat") else 0.0
            if damage_type == "magical":
                mit_stat = target.stat("resistance") if hasattr(target, "stat") else 0.0
            else:
                mit_stat = target.stat("armor") if hasattr(target, "stat") else 0.0

            # Apply penetration
            after_pct = mit_stat * (1.0 - pen_pct)
            effective_mit = max(0.0, after_pct - pen_flat)
            reduction = effective_mit / (effective_mit + MITIGATION_CONSTANT)
            final = raw * (1.0 - reduction)

        final = max(1.0, final)

        # Barrier soaks damage before HP (temp pool, not counted in hp/max_hp)
        to_hp = target.absorb_with_barrier(final)

        # Apply damage
        target.hp = max(0.0, target.hp - to_hp)

        # Fire on_damage_dealt (attacker view)
        dealt_event = DamageEvent(
            attacker=attacker, target=target, amount=final,
            tag=tag.value, cast_id=self._current_cast_id, hit_id=hit_id,
            is_crit=is_crit,
        )
        self._bus.fire("on_damage_dealt", dealt_event, cast_id=self._current_cast_id, ctx=self)

        # Fire on_damage_taken (target view)
        self._bus.fire("on_damage_taken", dealt_event, cast_id=self._current_cast_id, ctx=self)

        # Fire on_ability_damage if from an ability
        if tag == SourceTag.ABILITY:
            self._bus.fire("on_ability_damage", dealt_event, cast_id=self._current_cast_id, ctx=self)

        # Kill check
        if target.hp <= 0 and target.alive:
            self.kill(target, attacker)

        return final

    def heal(self, source: Piece, target: Piece, amount: float) -> float:
        """Heal a target. Returns actual amount healed.

        Antiheal (V): a `grievous` target receives reduced healing
        (GRIEVOUS_HEAL_MULT) — the grievous-wounds primitive (Bramble/Witherbloom).
        """
        if not target.alive:
            return 0.0
        if target.has_status("grievous"):
            from src.game.status import GRIEVOUS_HEAL_MULT
            amount *= GRIEVOUS_HEAL_MULT
        actual = min(amount, target.max_hp - target.hp)
        target.hp += actual
        event = HealEvent(source=source, target=target, amount=actual)
        self._bus.fire("on_heal", event, ctx=self)
        return actual

    def grant_barrier(self, target: Piece, amount: float, duration_ticks: int = 0) -> None:
        """Grant a barrier — temp damage-absorb pool consumed before HP.

        duration_ticks <= 0 means the barrier lasts until fully consumed.
        Multiple grants stack as independent segments (consumed FIFO).
        """
        if not target.alive or amount <= 0.0:
            return
        expires = self.current_tick + duration_ticks if duration_ticks > 0 else None
        target.barriers.append(BarrierSegment(amount=amount, expires_at_tick=expires))

    def apply_status(
        self, target: Piece, status_id: str, duration_ticks: int, stacks: int = 1,
        source_id: str = "", potency: float = 0.0,
    ) -> None:
        """Apply a status effect to a target.

        Status identity is status_id only — one instance per status per piece
        (Option 1 / TFT-style). Re-application by a different source merges into
        the single instance; the DOT clock (ticks_to_next_dot) is NOT reset so it
        free-runs regardless of reapply spam. `potency` overrides per-DOT-tick
        damage; on merge the STRONGER potency wins and takes damage credit.
        """
        if not target.alive:
            return

        if status_id not in STATUS_DEFS:
            raise ValueError(f"Unknown status_id {status_id!r} — not found in STATUS_DEFS")

        status_def = STATUS_DEFS.get(status_id)

        # Scaled CC-immunity (T.28d): a cc_immune piece ignores hard-CC — any
        # status carrying an action-impairing gate. Soft CC (slow), DoTs, and
        # markers (hexproof/taunt/soaked) still land.
        if target.cc_immune and status_def is not None and any(
            g in status_def.gates for g in _HARD_CC_GATES
        ):
            return

        existing = target.get_status(status_id)

        if existing is not None:
            if status_def and status_def.stack_behaviour == StackBehaviour.REFRESH:
                # Refresh: reset duration
                existing.remaining_ticks = duration_ticks
                existing.stacks = max(existing.stacks, stacks)
            else:
                # Stack: add stacks, refresh duration
                existing.stacks += stacks
                existing.remaining_ticks = max(existing.remaining_ticks, duration_ticks)
            # Strongest-wins: a higher-potency reapply takes over magnitude + credit.
            if potency > existing.potency:
                existing.potency = potency
                existing.source_id = source_id or existing.source_id
        else:
            interval = status_def.dot_interval_ticks if status_def else 100
            target.statuses.append(StatusInstance(
                status_id=status_id,
                remaining_ticks=duration_ticks,
                stacks=stacks,
                source_id=source_id,
                potency=potency,
                ticks_to_next_dot=interval,
            ))

        event = StatusEvent(target=target, status_id=status_id,
                           duration_ticks=duration_ticks, stacks=stacks)
        self._bus.fire("on_status_applied", event, ctx=self)

    def remove_status(self, target: Piece, status_id: str) -> None:
        """Remove a status from a target."""
        for i, s in enumerate(target.statuses):
            if s.status_id == status_id:
                target.statuses.pop(i)
                event = StatusEvent(target=target, status_id=status_id)
                self._bus.fire("on_status_expired", event, ctx=self)
                return

    def apply_modifier(self, target: Piece, modifier: Modifier) -> None:
        """Apply a modifier to a target's modifier list."""
        target.modifiers.append(modifier)

    def trigger_basic_attack(self, attacker: Piece, target: Piece, mult: float = 1.0) -> None:
        """Resolve a basic attack: fires events, generates mana, etc."""
        if not attacker.alive or not target.alive:
            return

        # Fire on_attack_start
        start_event = AttackEvent(attacker=attacker, target=target)
        self._bus.fire("on_attack_start", start_event, ctx=self)

        # Calculate auto damage
        str_val = attacker.stat("strength")
        int_val = attacker.stat("intelligence")
        raw = (1.0 * str_val + 0.2 * int_val) * mult

        # Deal damage
        final = self.deal_damage(attacker, target, raw, SourceTag.BASIC_ATTACK, damage_type="physical")

        # Fire on_attack_landed
        landed_event = AttackEvent(attacker=attacker, target=target, amount=final)
        self._bus.fire("on_attack_landed", landed_event, cast_id=self._current_cast_id, ctx=self)

    def cast_ability(self, actor: Piece, slot_idx: int = 0) -> None:
        """Cast an active ability from the given slot."""
        from src.game.registries import ABILITY_REGISTRY

        if not actor.alive:
            return
        if slot_idx >= len(actor.actives):
            return

        slot = actor.actives[slot_idx]
        ability_id = slot.ability_id
        handler = ABILITY_REGISTRY.get(ability_id)
        if handler is None:
            return

        # Set up cast context
        self._cast_id_counter += 1
        cast_id = self._cast_id_counter
        old_cast_id = self._current_cast_id
        self._current_cast_id = cast_id

        # Fire on_cast
        cast_event = CastEvent(caster=actor, ability_id=ability_id, cast_id=cast_id)
        self._bus.fire("on_cast", cast_event, cast_id=cast_id, ctx=self)

        # Resolve targets and execute handler
        targets = list(self.enemies_of(actor))
        handler(self, actor, targets)

        # Fire on_cast_complete
        self._bus.fire("on_cast_complete", cast_event, cast_id=cast_id, ctx=self)

        # Clean up cast dedup
        self._bus.clear_cast(cast_id)
        self._current_cast_id = old_cast_id

    def gain_mana(self, actor: Piece, amount: float) -> None:
        """Add mana to ALL of actor's active slots (separate pools).

        Clamps to `max_mana` (the universal cap, V.48) so granted mana can bank
        into the overload headroom, not just to `mana_cost`."""
        for slot in actor.actives:
            slot.current_mana = min(float(slot.max_mana), slot.current_mana + amount)

    def teleport(self, actor: Piece, dest_q: int, dest_r: int) -> None:
        """Move piece to destination instantly."""
        actor.position_q = dest_q
        actor.position_r = dest_r

    def spawn(self, piece: Piece, position_q: int, position_r: int) -> None:
        """Spawn a new piece mid-combat."""
        piece.position_q = position_q
        piece.position_r = position_r
        piece.alive = True
        if piece.is_enemy:
            self._alive_enemy += 1
        else:
            self._alive_team += 1
        self._pieces.append(piece)
        event = SpawnEvent(piece=piece, position=(position_q, position_r))
        self._bus.fire("on_spawn", event, ctx=self)

    def expire_summon(self, piece: Piece) -> None:
        """Remove an expired summon WITHOUT firing on_death (G6 lifecycle).

        Mirrors the inline despawn the loop used to do, but keeps the O(1)
        liveness counts correct."""
        if not piece.alive:
            return
        piece.alive = False
        piece.hp = 0.0
        if piece.is_enemy:
            self._alive_enemy -= 1
        else:
            self._alive_team -= 1

    def kill(self, target: Piece, killer: Piece | None = None) -> None:
        """Kill a piece. Fires on_kill and on_death."""
        if not target.alive:
            return
        target.alive = False
        target.hp = 0.0
        if target.is_enemy:
            self._alive_enemy -= 1
        else:
            self._alive_team -= 1

        if killer:
            kill_event = KillEvent(killer=killer, victim=target)
            self._bus.fire("on_kill", kill_event, ctx=self)

        death_event = DeathEvent(victim=target, killer=killer)
        self._bus.fire("on_death", death_event, ctx=self)

    def revive(self, target: Piece, hp_frac: float = 0.3) -> bool:
        """Bring a dead piece back at a fraction of max HP (Mender @6, T.28b).

        Death-path reversal: callers fire this from an `on_death` hook (the victim
        is already `alive=False`, count already decremented). Restores liveness +
        the O(1) count, clears stale barriers, and starts the piece at
        `max(1, hp_frac*max_hp)`. Returns False if the target was already alive.
        Deterministic — caller owns the once-per-combat guard (V.37)."""
        if target.alive:
            return False
        target.alive = True
        target.hp = max(1.0, target.max_hp * hp_frac)
        target.barriers = []
        if target.is_enemy:
            self._alive_enemy += 1
        else:
            self._alive_team += 1
        return True

    def end_combat(self, winner: str) -> None:
        """End combat with the given winner."""
        self._combat_ended = True
        self._winner = winner
        event = CombatEndEvent(winner=winner)
        self._bus.fire("on_combat_end", event, ctx=self)

    def register_bundle(self, owner: Piece, bundle: EffectBundle) -> None:
        """Register an EffectBundle mid-combat (e.g., boss phase hook)."""
        from src.game.loadout import apply_bundle
        apply_bundle(owner, bundle, self._bus, ctx=self)

    def fire(self, event_name: str, event: Any) -> None:
        """Fire an arbitrary event on the bus (for phase hooks etc.)."""
        self._bus.fire(event_name, event, cast_id=self._current_cast_id, ctx=self)
