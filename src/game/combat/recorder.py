"""BattleResultRecorder — subscribes to EventBus and builds BattleResult (T26).

Subscribes to combat events (attacks, damage, deaths, casts, heals, spawns,
statuses, combat end) and reconstructs a BattleResult with a full event stream.
"""

from __future__ import annotations

from typing import Any

from src.game.effects import EventBus, Hook, HookScope
from src.game.events import (
    AttackEvent,
    CastEvent,
    CombatEndEvent,
    DamageEvent,
    DeathEvent,
    HealEvent,
    SpawnEvent,
    StatusEvent,
)
from src.game.models import BattleEvent, BattleResult, CombatOutcome, WeatherState
from src.game.piece import Piece


# Event type constants — the BattleEvent.event_type vocabulary
EVENT_MOVE = "move"
EVENT_ATTACK = "attack"
EVENT_CAST = "cast"
EVENT_DEATH = "death"
EVENT_HEAL = "heal"
EVENT_STATUS = "status"
EVENT_SPAWN = "spawn"

ROUND_TICKS = 600

DMG_PHYSICAL = "physical"


class BattleResultRecorder:
    """Records combat events and builds a BattleResult."""

    def __init__(self, pieces: list[Piece], weather: WeatherState, node_id: str = "") -> None:
        self._pieces = pieces
        self._weather = weather
        self._node_id = node_id
        self._events: list[BattleEvent] = []
        self._damage_dealt: dict[str, int] = {p.id: 0 for p in pieces}
        self._damage_taken: dict[str, int] = {p.id: 0 for p in pieces}
        self._duration_ticks: int = 0
        self._timed_out: bool = False
        self._outcome: CombatOutcome | None = None
        self._current_tick: int = 0

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

    def record_move(self, piece_id: str, tick: int, dest_q: int, dest_r: int) -> None:
        """Record a movement event (called directly by the loop, not via bus)."""
        self._events.append(BattleEvent(
            tick=tick,
            actor_id=piece_id,
            target_id=None,
            event_type=EVENT_MOVE,
            note=f"{dest_q},{dest_r}",
        ))

    def record_cast(self, actor_id: str, target_id: str, tick: int, amount: int, damage_type: str, is_crit: bool = False) -> None:
        """Record a cast event (called by the engine for cast recording).

        Note: damage stats are tracked via _on_damage_dealt from the bus.
        """
        self._events.append(BattleEvent(
            tick=tick,
            actor_id=actor_id,
            target_id=target_id,
            event_type=EVENT_CAST,
            amount=amount,
            note=damage_type,
            is_crit=is_crit,
        ))

    def record_attack(self, actor_id: str, target_id: str, tick: int, amount: int, damage_type: str, is_crit: bool = False) -> None:
        """Record an attack event (called by the engine for attack recording).

        Note: damage stats are tracked via _on_damage_dealt from the bus.
        """
        self._events.append(BattleEvent(
            tick=tick,
            actor_id=actor_id,
            target_id=target_id,
            event_type=EVENT_ATTACK,
            amount=amount,
            note=damage_type,
            is_crit=is_crit,
        ))

    def set_duration(self, ticks: int, timed_out: bool = False) -> None:
        """Set the combat duration."""
        self._duration_ticks = ticks
        self._timed_out = timed_out

    def _on_attack_landed(self, ctx: Any, event: AttackEvent) -> None:
        """Record attack event (for bus-driven basic attacks from ability framework)."""
        tick = ctx.current_tick if ctx else 0
        amount = int(event.amount) if event.amount else 0
        self._events.append(BattleEvent(
            tick=tick,
            actor_id=event.attacker.id,
            target_id=event.target.id,
            event_type=EVENT_ATTACK,
            amount=amount,
            note=DMG_PHYSICAL,
        ))

    def _on_damage_dealt(self, ctx: Any, event: DamageEvent) -> None:
        """Track damage for ability-driven damage not recorded elsewhere."""
        amount = int(event.amount) if event.amount else 0
        self._damage_dealt[event.attacker.id] = self._damage_dealt.get(event.attacker.id, 0) + amount
        self._damage_taken[event.target.id] = self._damage_taken.get(event.target.id, 0) + amount

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
        """Record ability cast event (for bus-driven casts from ability framework)."""
        # Cast recording for ability-framework casts will be extended
        # when abilities produce damage through their own handlers
        pass

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
        )
