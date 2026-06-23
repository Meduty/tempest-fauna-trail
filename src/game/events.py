"""Event payload dataclasses for the combat event bus (T20).

Each event type corresponds to one entry in the event taxonomy
(effect_systems_design.md §4.6). Payloads are plain dataclasses —
no logic, no methods beyond __init__.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class CombatStartEvent:
    """Fires once after all bundles applied, before the first tick."""
    pass


@dataclass(slots=True)
class CombatEndEvent:
    """Fires once at combat resolution."""
    winner: str  # "team" | "enemy" | "draw"


@dataclass(slots=True)
class TickEvent:
    """Fires every tick. Use sparingly."""
    tick: int


@dataclass(slots=True)
class CastEvent:
    """Fires on on_cast and on_cast_complete."""
    caster: Any  # Piece
    ability_id: str
    cast_id: int
    # Mana telemetry (T.36b) — which slot cast, the cost spent, and the slot's
    # current mana *after* the spend. Surfaced to the combat log for the mana-bar
    # UI + cast-cadence instrumentation.
    slot_idx: int = 0
    mana_cost: int = 0
    mana_after: float = 0.0


@dataclass(slots=True)
class AttackEvent:
    """Fires on on_attack_start and on_attack_landed."""
    attacker: Any  # Piece
    target: Any  # Piece
    amount: float = 0.0


@dataclass(slots=True)
class DamageEvent:
    """Fires on on_damage_pre, on_damage_dealt, on_damage_taken, on_ability_damage."""
    attacker: Any  # Piece
    target: Any  # Piece
    amount: float
    tag: str  # SourceTag value
    cast_id: int | None = None
    hit_id: int | None = None
    is_crit: bool = False
    damage_type: str = "magical"  # physical | magical | true — for the `ability` beat colour (T.37)


@dataclass(slots=True)
class HealEvent:
    """Fires on on_heal."""
    source: Any  # Piece
    target: Any  # Piece
    amount: float


@dataclass(slots=True)
class StatusEvent:
    """Fires on on_status_applied and on_status_expired."""
    target: Any  # Piece
    status_id: str
    duration_ticks: int = 0
    stacks: int = 1


@dataclass(slots=True)
class KillEvent:
    """Fires on on_kill (killer's perspective)."""
    killer: Any  # Piece
    victim: Any  # Piece


@dataclass(slots=True)
class DeathEvent:
    """Fires on on_death (victim's perspective, before removal)."""
    victim: Any  # Piece
    killer: Any | None  # Piece or None


@dataclass(slots=True)
class ManaEvent:
    """Fires on on_mana_full."""
    actor: Any  # Piece
    slot_idx: int


@dataclass(slots=True)
class PhaseEvent:
    """Fires on on_phase_change."""
    piece: Any  # Piece
    new_phase: int


@dataclass(slots=True)
class SpawnEvent:
    """Fires on on_spawn."""
    piece: Any  # Piece
    position: tuple[int, int]


@dataclass(slots=True)
class DespawnEvent:
    """Fires on on_despawn — a summon expiring (G6 lifecycle, NOT a death)."""
    piece: Any  # Piece
