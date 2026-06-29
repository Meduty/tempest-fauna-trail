"""Combat Piece and ActiveSlot dataclasses (T20).

These are the runtime combat representations. The Piece here is the
combat-time piece that carries modifiers, statuses, and ability slots.
It is built from Champion/Enemy models by the loadout compiler.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.game.effects import Modifier, compute_stat
from src.game.models import WeatherState
from src.game.status import StatusGate, StatusInstance


@dataclass
class ActiveSlot:
    """One ability slot on a piece. Mana is per-slot (separate pools).

    Mana primitive (T.29c, V.48): `mana_cost` is the cast threshold + amount
    deducted per cast (base authored on the ability def via `ABILITY_MANA`).
    `max_mana` is the universal pool cap (regen/start/grant clamp to it);
    defaults to `2 * mana_cost` when authored as `0`/unset (overload headroom).
    `start_mana` seeds `current_mana` at combat start (clamped to `max_mana`).
    `priority` is the unified rank — drives both the weighted-rank charge cycle
    and the <=1-cast-per-window cast pick; normalized to >=1.
    """
    ability_id: str
    mana_cost: int
    max_mana: int = 0  # 0 ⇒ normalized to 2 * mana_cost in __post_init__
    start_mana: int = 0
    current_mana: float = 0.0  # runtime pool; seeded from start_mana at combat start
    priority: int = 1  # unified rank (V.48); >=1, higher casts first

    def __post_init__(self) -> None:
        if self.priority < 1:
            self.priority = 1
        if self.max_mana <= 0:
            self.max_mana = 2 * self.mana_cost


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
    role: str = ""  # display-only identity (V.82) — surfaced on PieceView for the combat infocard; never read by combat math
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
    formation_index: int = 0  # input-order index → enemy formation-position key (T.24)
    load_order: int = 0  # seeded side-independent permutation → final tie-break (V.34)
    action_energy: int = 0
    movement_energy: int = 0
    # Weighted-rank mana charge cursor (T.29c, V.48): advances once per regen
    # tick; selects which slot receives the full mana_regen this tick. Cycle
    # length = sum(slot.priority); deterministic cadence, RNG-free (V.2/V.14).
    mana_charge_cursor: int = 0

    # Trait movement/targeting behaviour flags (T.28b) — set by trait hooks at
    # on_combat_start; read by the engine. Pieces are rebuilt per combat so these
    # reset to False unless a cleared trait re-arms them.
    is_kiter: bool = False  # Skyborn: retreat-kite melee threats (engine §_kite_step)
    seeks_backline: bool = False  # Stalker: path/target toward the enemy backline
    cc_immune: bool = False  # Scaled @5+: hard-CC (gate-bearing statuses) skip this piece (T.28d)
    pierces_hexproof: bool = False  # Spirit @8: single-target acquisition ignores HEXPROOF (T.28d, V.40)
    weather_favored: bool = False  # Scaled @8: always gets the favorable weather pack (T.28d)

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
