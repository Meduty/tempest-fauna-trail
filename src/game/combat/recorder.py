"""BattleResultRecorder — subscribes to EventBus and builds BattleResult (T26).

Subscribes to combat events (attacks, damage, deaths, casts, heals, spawns,
statuses, combat end) and reconstructs a BattleResult with a full event stream.
"""

from __future__ import annotations

from typing import Any

from src.game.effects import EventBus, Hook, HookScope, SourceTag
from src.game.events import (
    AttackEvent,
    CastEvent,
    CombatEndEvent,
    DamageEvent,
    DeathEvent,
    DespawnEvent,
    HealEvent,
    SpawnEvent,
    StatusEvent,
)
from src.game.models import (
    BattleEvent,
    BattleResult,
    CombatOutcome,
    ManaProfile,
    PieceSnapshot,
    WeatherState,
)
from src.game.piece import Piece


# Event type constants — the BattleEvent.event_type vocabulary
EVENT_MOVE = "move"
EVENT_ATTACK = "attack"
EVENT_CAST = "cast"               # ability *activation* marker (amount=0)
EVENT_ABILITY = "ability"         # ability *damage* (one per target hit; amount = final post-mitigation)
EVENT_DEATH = "death"
EVENT_HEAL = "heal"
EVENT_DOT = "dot"
EVENT_STATUS = "status"            # status applied
EVENT_STATUS_EXPIRE = "status_expire"
EVENT_SPAWN = "spawn"
EVENT_DESPAWN = "despawn"          # summon expired (NOT a death)

ROUND_TICKS = 600

DMG_PHYSICAL = "physical"
DMG_DOT = "dot"


def _snapshot_piece(piece: Piece, spawn_tick: int) -> PieceSnapshot:
    """Capture a piece's identity + board state for the combat view (T.37a)."""
    mana: ManaProfile | None = None
    if piece.actives:
        mana = ManaProfile(
            mana_regen=int(piece.stat("mana_regen")),
            slots=[
                (s.mana_cost, s.max_mana, s.priority, s.start_mana)
                for s in piece.actives
            ],
        )
    return PieceSnapshot(
        id=piece.id,
        is_enemy=piece.is_enemy,
        affinity=piece.affinity,
        q=piece.position_q,
        r=piece.position_r,
        max_hp=int(piece.max_hp),
        mana=mana,
        summon=piece.summon,
        spawn_tick=spawn_tick,
    )


class BattleResultRecorder:
    """Records combat events and builds a BattleResult."""

    def __init__(
        self,
        pieces: list[Piece],
        weather: WeatherState,
        node_id: str = "",
        trait_activations: list[tuple[str, int, int]] | None = None,
    ) -> None:
        self._pieces = pieces
        self._weather = weather
        self._node_id = node_id
        self._trait_activations = list(trait_activations or [])
        self._events: list[BattleEvent] = []
        self._damage_dealt: dict[str, int] = {p.id: 0 for p in pieces}
        self._damage_taken: dict[str, int] = {p.id: 0 for p in pieces}
        self._duration_ticks: int = 0
        self._timed_out: bool = False
        self._outcome: CombatOutcome | None = None
        self._current_tick: int = 0
        # Statuses currently held per piece — a `status` beat fires only on the
        # transition INTO a status (acquisition), not on re-applies/refreshes
        # (V.54: kills sudden-death + poison-restack spam).
        self._active_statuses: set[tuple[str, str]] = set()
        # Board layout snapshot (T.37a). Positions are final here — assign_spawns
        # ran before the recorder is constructed in every resolve path. Summons
        # are appended by `_on_spawn` at their spawn tick. Board dims via deferred
        # import (avoids a context↔recorder import cycle).
        from src.game.combat.context import BOARD_HEIGHT, BOARD_WIDTH
        self._board_width = BOARD_WIDTH
        self._board_height = BOARD_HEIGHT
        self._initial_pieces: list[PieceSnapshot] = [
            _snapshot_piece(p, spawn_tick=0) for p in pieces
        ]

    def register(self, bus: EventBus) -> None:
        """Subscribe to all relevant events on the bus."""
        bus.subscribe(Hook(
            event="on_attack_landed",
            handler=self._on_attack_landed,
            priority=-1000,  # Low priority — record after all hooks modify
            scope=HookScope.PER_HIT,
        ))
        bus.subscribe(Hook(
            event="on_damage_dealt",
            handler=self._on_damage_dealt,
            priority=-1000,
            scope=HookScope.PER_HIT,
        ))
        bus.subscribe(Hook(
            event="on_death",
            handler=self._on_death,
            priority=-1000,
            scope=HookScope.PER_HIT,
        ))
        bus.subscribe(Hook(
            event="on_cast",
            handler=self._on_cast,
            priority=-1000,
            scope=HookScope.PER_HIT,
        ))
        bus.subscribe(Hook(
            event="on_combat_end",
            handler=self._on_combat_end,
            priority=-1000,
            scope=HookScope.ONCE_PER_COMBAT,
        ))
        # T.37a — the previously-dropped beats (heals/statuses/summons) the
        # combat view needs. All observer-only at lowest priority (V.54).
        bus.subscribe(Hook(
            event="on_heal",
            handler=self._on_heal,
            priority=-1000,
            scope=HookScope.PER_HIT,
        ))
        bus.subscribe(Hook(
            event="on_status_applied",
            handler=self._on_status_applied,
            priority=-1000,
            scope=HookScope.PER_HIT,
        ))
        bus.subscribe(Hook(
            event="on_status_expired",
            handler=self._on_status_expired,
            priority=-1000,
            scope=HookScope.PER_HIT,
        ))
        bus.subscribe(Hook(
            event="on_spawn",
            handler=self._on_spawn,
            priority=-1000,
            scope=HookScope.PER_HIT,
        ))
        bus.subscribe(Hook(
            event="on_despawn",
            handler=self._on_despawn,
            priority=-1000,
            scope=HookScope.PER_HIT,
        ))

    def record_move(self, piece_id: str, tick: int, dest_q: int, dest_r: int) -> None:
        """Record a movement event (called directly by the loop, not via bus).

        Destination travels in structured `dest_q`/`dest_r` int fields (T.37c),
        not a parsed `note` string (B.28)."""
        self._events.append(BattleEvent(
            tick=tick,
            actor_id=piece_id,
            target_id=None,
            event_type=EVENT_MOVE,
            dest_q=dest_q,
            dest_r=dest_r,
        ))

    def record_cast(self, actor_id: str, target_id: str, tick: int, amount: int, damage_type: str, is_crit: bool = False,
                    slot_idx: int = -1, mana_spent: int = 0, mana_after: int = 0,
                    hp_after: int = -1, barrier_after: int = 0) -> None:
        """Record a cast event (engine's unregistered-ability fallback path only).

        Registered casts emit their activation via `_on_cast`; this path is the
        single producer for *unregistered* fallback casts (V.50 — the two never
        both fire). Damage totals are tracked via `_on_damage_dealt`; `hp_after`/
        `barrier_after` carry the single target's post-hit resource truth (T.37a).
        """
        self._events.append(BattleEvent(
            tick=tick,
            actor_id=actor_id,
            target_id=target_id,
            event_type=EVENT_CAST,
            amount=amount,
            note=damage_type,
            is_crit=is_crit,
            slot_idx=slot_idx,
            mana_spent=mana_spent,
            mana_after=mana_after,
            hp_after=hp_after,
            barrier_after=barrier_after,
        ))

    def set_duration(self, ticks: int, timed_out: bool = False) -> None:
        """Set the combat duration."""
        self._duration_ticks = ticks
        self._timed_out = timed_out

    def _on_attack_landed(self, ctx: Any, event: AttackEvent) -> None:
        """Record the single attack beat (every basic attack flows through here —
        `ctx.trigger_basic_attack` fires `on_attack_landed` *after* applying
        damage, so `target.hp`/barrier are post-hit truth, T.37a)."""
        tick = ctx.current_tick if ctx else 0
        amount = int(event.amount) if event.amount else 0
        self._events.append(BattleEvent(
            tick=tick,
            actor_id=event.attacker.id,
            target_id=event.target.id,
            event_type=EVENT_ATTACK,
            amount=amount,
            note=DMG_PHYSICAL,
            hp_after=int(event.target.hp),
            barrier_after=int(event.target.barrier_total),
        ))

    def _on_damage_dealt(self, ctx: Any, event: DamageEvent) -> None:
        """Track damage totals + emit a `dot` beat for damage-over-time ticks.

        Fires for *all* damage (post-HP-apply). Attack/ability hits already get
        their beat (`_on_attack_landed` / `_on_cast`); DOT ticks had no beat at
        all (B.27) → emit one here so a view shows the bleed + HP drop. No
        double-count: only `tag == dot` produces an event."""
        amount = int(event.amount) if event.amount else 0
        # Environmental damage (hazard tiles, map effects) has no attacker — it
        # is not attributed to any dealer, but is still counted as taken.
        if event.attacker is not None:
            self._damage_dealt[event.attacker.id] = self._damage_dealt.get(event.attacker.id, 0) + amount
        self._damage_taken[event.target.id] = self._damage_taken.get(event.target.id, 0) + amount

        if event.tag == SourceTag.DOT.value:
            tick = ctx.current_tick if ctx else 0
            self._events.append(BattleEvent(
                tick=tick,
                actor_id=event.attacker.id if event.attacker is not None else "",
                target_id=event.target.id,
                event_type=EVENT_DOT,
                amount=amount,
                note=DMG_DOT,
                is_crit=event.is_crit,
                hp_after=int(event.target.hp),
                barrier_after=int(event.target.barrier_total),
            ))
        elif event.tag == SourceTag.ABILITY.value:
            # Ability *damage* beat (T.37) — separate from the `cast` activation
            # marker (`_on_cast`, amount=0). One per target hit; `amount` is the
            # final post-mitigation figure `deal_damage` already computed, so the
            # view's floating number is post-mitigation by construction. Carries
            # `damage_type` for colour. Excluded from `turns` (V.54) ⇒ byte-identical.
            tick = ctx.current_tick if ctx else 0
            self._events.append(BattleEvent(
                tick=tick,
                actor_id=event.attacker.id if event.attacker is not None else "",
                target_id=event.target.id,
                event_type=EVENT_ABILITY,
                amount=amount,
                note=event.damage_type,
                is_crit=event.is_crit,
                hp_after=int(event.target.hp),
                barrier_after=int(event.target.barrier_total),
            ))

    def _on_death(self, ctx: Any, event: DeathEvent) -> None:
        """Record death event."""
        tick = ctx.current_tick if ctx else 0
        killer_id = event.killer.id if event.killer else None
        self._events.append(BattleEvent(
            tick=tick,
            actor_id=event.victim.id,
            target_id=killer_id,
            event_type=EVENT_DEATH,
        ))

    def _on_cast(self, ctx: Any, event: CastEvent) -> None:
        """Record an ability-framework cast (T.29c fix).

        Fires on `on_cast` from `ctx.cast_ability`, so registered abilities now
        appear in the event stream (previously a no-op → registered casts were
        invisible, B.21). The cast's damage/heal is attributed separately via
        `_on_damage_dealt`/heal totals; this event marks the activation. Target
        is the caster's current target (may be None for self/AoE casts)."""
        tick = ctx.current_tick if ctx else 0
        caster = event.caster
        self._events.append(BattleEvent(
            tick=tick,
            actor_id=caster.id,
            target_id=getattr(caster, "target_id", None),
            event_type=EVENT_CAST,
            amount=0,
            note=event.ability_id,
            slot_idx=event.slot_idx,
            mana_spent=int(event.mana_cost),
            mana_after=int(event.mana_after),
        ))

    def _on_heal(self, ctx: Any, event: HealEvent) -> None:
        """Record a heal beat (`ctx.heal` fires `on_heal` after applying, so
        `target.hp` is post-heal truth — T.37a). `amount` is the actual amount
        healed (post-`grievous` reduction, V.51)."""
        amount = int(event.amount) if event.amount else 0
        if amount <= 0:
            return  # no-op heal (dead/at-cap/0) — not a visible beat
        tick = ctx.current_tick if ctx else 0
        self._events.append(BattleEvent(
            tick=tick,
            actor_id=event.source.id,
            target_id=event.target.id,
            event_type=EVENT_HEAL,
            amount=amount,
            hp_after=int(event.target.hp),
            barrier_after=int(event.target.barrier_total),
        ))

    def _on_status_applied(self, ctx: Any, event: StatusEvent) -> None:
        """Record a status-applied beat (icon appears) — once per *acquisition*,
        not per re-apply/refresh (V.54). `amount` = stacks at acquisition."""
        key = (event.target.id, event.status_id)
        if key in self._active_statuses:
            return  # already held — a stack/refresh, not a new acquisition
        self._active_statuses.add(key)
        tick = ctx.current_tick if ctx else 0
        self._events.append(BattleEvent(
            tick=tick,
            actor_id=event.target.id,
            target_id=None,
            event_type=EVENT_STATUS,
            amount=int(event.stacks),
            note=event.status_id,
        ))

    def _on_status_expired(self, ctx: Any, event: StatusEvent) -> None:
        """Record a status-expired beat (icon clears). Clears the acquisition
        guard so a later re-application beats again (V.54)."""
        self._active_statuses.discard((event.target.id, event.status_id))
        tick = ctx.current_tick if ctx else 0
        self._events.append(BattleEvent(
            tick=tick,
            actor_id=event.target.id,
            target_id=None,
            event_type=EVENT_STATUS_EXPIRE,
            note=event.status_id,
        ))

    def _on_spawn(self, ctx: Any, event: SpawnEvent) -> None:
        """Record a summon entering the board (T.37a): a `spawn` beat (tick +
        position) for the timeline, plus the summon's `PieceSnapshot` (identity +
        spawn position + mana profile) so the view can render the new piece."""
        tick = ctx.current_tick if ctx else 0
        q, r = event.position
        self._events.append(BattleEvent(
            tick=tick,
            actor_id=event.piece.id,
            target_id=None,
            event_type=EVENT_SPAWN,
            dest_q=q,
            dest_r=r,
        ))
        self._initial_pieces.append(_snapshot_piece(event.piece, spawn_tick=tick))

    def _on_despawn(self, ctx: Any, event: DespawnEvent) -> None:
        """Record a summon leaving the board (expiry, not death — T.37a, B.26)."""
        tick = ctx.current_tick if ctx else 0
        self._events.append(BattleEvent(
            tick=tick,
            actor_id=event.piece.id,
            target_id=None,
            event_type=EVENT_DESPAWN,
        ))

    def _on_combat_end(self, ctx: Any, event: CombatEndEvent) -> None:
        """Record combat end."""
        pass

    def build_result(self, winner: str) -> BattleResult:
        """Build the final BattleResult from recorded data."""
        if winner == "team":
            outcome = CombatOutcome.WIN
        elif winner == "enemy":
            outcome = CombatOutcome.LOSS
        else:
            outcome = CombatOutcome.DRAW

        if self._timed_out:
            outcome = CombatOutcome.DRAW

        rounds = (self._duration_ticks + ROUND_TICKS - 1) // ROUND_TICKS if self._duration_ticks > 0 else 0
        turns = sum(1 for e in self._events if e.event_type in (EVENT_ATTACK, EVENT_CAST))

        return BattleResult(
            node_id=self._node_id,
            weather=self._weather,
            outcome=outcome,
            rounds=rounds,
            turns=turns,
            duration_ticks=self._duration_ticks,
            team_damage_dealt=dict(self._damage_dealt),
            team_damage_taken=dict(self._damage_taken),
            surviving_team_ids=[p.id for p in self._pieces if p.alive and not p.is_enemy],
            surviving_enemy_ids=[p.id for p in self._pieces if p.alive and p.is_enemy],
            timed_out=self._timed_out,
            events=self._events,
            piece_max_hp={p.id: int(p.max_hp) for p in self._pieces},
            trait_activations=list(self._trait_activations),
            initial_pieces=list(self._initial_pieces),
            board_width=self._board_width,
            board_height=self._board_height,
        )
