"""Combat Piece and ActiveSlot dataclasses (T20).

These are the runtime combat representations. The Piece here is the
combat-time piece that carries modifiers, statuses, and ability slots.
It is built from Champion/Enemy models by the loadout compiler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.game.effects import Modifier, compute_stat
from src.game.models import WeatherState
from src.game.status import StatusGate, StatusInstance, STATUS_DEFS, StackBehaviour


@dataclass
class ActiveSlot:
    """One ability slot on a piece. Mana is per-slot (separate pools)."""
    ability_id: str
    cost: int
    current_mana: float = 0.0  # 0 starting mana by default
    priority: int = 0  # Higher priority casts first when multiple slots ready


@dataclass
class BarrierSegment:
    """One barrier grant — temporary damage-absorb pool, consumed before HP.

    Distinct from "shield" abilities (which buff armor/resistance): a barrier
    soaks raw incoming damage and never counts toward hp / max_hp.
    """
    amount: float
    expires_at_tick: int | None = None  # None = lasts until consumed


@dataclass
class Piece:
    """Runtime combat piece — the live entity during combat.

    Built from Champion/Enemy by the loadout compiler. Carries modifiers,
    statuses, and ability slots.
    """
    id: str
    base_stats: dict[str, float] = field(default_factory=dict)
    level: int = 1  # In-tier level (1-3) carried from the source model; read by level-scaling passives
    affinity: WeatherState = WeatherState.CLEAR
    traits: list[str] = field(default_factory=list)
    is_enemy: bool = False
    actives: list[ActiveSlot] = field(default_factory=list)
    passives: list[str] = field(default_factory=list)
    modifiers: list[Modifier] = field(default_factory=list)
    statuses: list[StatusInstance] = field(default_factory=list)
    items: list[str] = field(default_factory=list)

    # Combat state
    hp: float = 0.0
    max_hp: float = 0.0
    position_q: int = 0
    position_r: int = 0
    alive: bool = True
    target_id: str | None = None
    speed_tiebreaker: int = 0
    action_energy: int = 0
    movement_energy: int = 0

    # Crit state
    crit_counter: int = 0
    ability_can_crit: bool = False

    # Summon state (G6 — summons are full Piece objects with these flags)
    summon: bool = False
    summon_owner_id: str = ""
    summon_expires_tick: int = 0  # 0 means no expiry

    # Barrier state — temporary absorb pools, consumed before HP (FIFO)
    barriers: list[BarrierSegment] = field(default_factory=list)

    def stat(self, stat_name: str) -> float:
        """Get computed stat value including all modifiers."""
        return compute_stat(self, stat_name)

    @property
    def barrier_total(self) -> float:
        """Sum of all active barrier segments."""
        return sum(b.amount for b in self.barriers)

    def absorb_with_barrier(self, amount: float) -> float:
        """Soak incoming damage with barrier segments (FIFO).

        Mutates segments in place, drops depleted ones, and returns the
        remainder that should still be applied to HP.
        """
        remaining = amount
        for seg in self.barriers:
            if remaining <= 0.0:
                break
            soaked = min(seg.amount, remaining)
            seg.amount -= soaked
            remaining -= soaked
        self.barriers = [b for b in self.barriers if b.amount > 1e-9]
        return remaining

    def has_status(self, status_id: str) -> bool:
        """Check if piece has an active instance of the given status."""
        return any(s.status_id == status_id for s in self.statuses)

    def get_status(self, status_id: str) -> StatusInstance | None:
        """Get the status instance if present."""
        for s in self.statuses:
            if s.status_id == status_id:
                return s
        return None

    def status_stacks(self, status_id: str) -> int:
        """Get total stacks of a status (0 if not present)."""
        inst = self.get_status(status_id)
        return inst.stacks if inst else 0

    def is_gated(self, gate: StatusGate) -> bool:
        """Check if any active status blocks the given action."""
        return any(s.has_gate(gate) for s in self.statuses)

    @property
    def hp_pct(self) -> float:
        """Current HP as a fraction of max HP."""
        if self.max_hp <= 0:
            return 0.0
        return self.hp / self.max_hp
