"""Status effect definitions (T20).

Status effects are ID-based. Each status has:
- An identity (id, display_name)
- Stacking behaviour (refresh = reapply resets duration)
- Gate flags (what the piece is prevented from doing)
- DOT info (for burn/poison etc.)

Per user decision: stun uses REFRESH behaviour (reapply resets duration).
Different statuses handle stacking differently:
- Most CC: refresh (reset duration on reapply)
- Poison: stack intensity, decay once per tick
- Slow: stack to intensify
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class StackBehaviour(str, Enum):
    """How multiple applications of the same status interact."""
    REFRESH = "refresh"  # Reapply resets duration to the new value
    STACK = "stack"  # Stacks increase; each stack has own duration or shared decay


class StatusGate(str, Enum):
    """What a status prevents."""
    BLOCKS_ACTION = "blocks_action"  # Skip all meter updates (stun, frozen)
    BLOCKS_CAST = "blocks_cast"  # Block ability cast (silence)
    BLOCKS_ATTACK = "blocks_attack"  # Block auto-attack (disarm)
    BLOCKS_MOVEMENT = "blocks_movement"  # Block hex movement (root, frozen)


@dataclass(frozen=True)
class StatusDef:
    """Static definition of a status effect type."""
    id: str
    display_name: str
    stack_behaviour: StackBehaviour = StackBehaviour.REFRESH
    gates: tuple[StatusGate, ...] = ()
    dot_per_tick: float = 0.0  # Damage per tick (burn, poison)
    dot_scales_with_stacks: bool = False  # Poison: damage * stacks
    decay_stacks_per_tick: bool = False  # Poison: each tick removes one stack
    dot_true_damage: bool = False  # True: DOT bypasses all mitigation (sudden death)


# ---------------------------------------------------------------------------
# Core status definitions
# ---------------------------------------------------------------------------

STATUS_DEFS: dict[str, StatusDef] = {}


def _register(s: StatusDef) -> StatusDef:
    STATUS_DEFS[s.id] = s
    return s


STUN = _register(StatusDef(
    id="stun",
    display_name="Stun",
    stack_behaviour=StackBehaviour.REFRESH,
    gates=(StatusGate.BLOCKS_ACTION,),
))

SILENCE = _register(StatusDef(
    id="silence",
    display_name="Silence",
    stack_behaviour=StackBehaviour.REFRESH,
    gates=(StatusGate.BLOCKS_CAST,),
))

DISARM = _register(StatusDef(
    id="disarm",
    display_name="Disarm",
    stack_behaviour=StackBehaviour.REFRESH,
    gates=(StatusGate.BLOCKS_ATTACK,),
))

ROOT = _register(StatusDef(
    id="root",
    display_name="Root",
    stack_behaviour=StackBehaviour.REFRESH,
    gates=(StatusGate.BLOCKS_MOVEMENT,),
))

BURN = _register(StatusDef(
    id="burn",
    display_name="Burn",
    stack_behaviour=StackBehaviour.REFRESH,
    dot_per_tick=2.0,
    dot_scales_with_stacks=False,
))

POISON = _register(StatusDef(
    id="poison",
    display_name="Poison",
    stack_behaviour=StackBehaviour.STACK,
    dot_per_tick=1.5,
    dot_scales_with_stacks=True,
    decay_stacks_per_tick=True,  # One stack removed per tick after DOT is applied
))

SLOW = _register(StatusDef(
    id="slow",
    display_name="Slow",
    stack_behaviour=StackBehaviour.STACK,  # Stacks intensify the slow
))

CHARGED = _register(StatusDef(
    id="charged",
    display_name="Charged",
    stack_behaviour=StackBehaviour.REFRESH,
))

SOAKED = _register(StatusDef(
    id="soaked",
    display_name="Soaked",
    stack_behaviour=StackBehaviour.REFRESH,
))

FROZEN = _register(StatusDef(
    id="frozen",
    display_name="Frozen",
    stack_behaviour=StackBehaviour.REFRESH,
    gates=(StatusGate.BLOCKS_ACTION, StatusGate.BLOCKS_MOVEMENT),
))

FEAR = _register(StatusDef(
    id="fear",
    display_name="Fear",
    stack_behaviour=StackBehaviour.REFRESH,
    gates=(StatusGate.BLOCKS_ACTION,),
))

# Sudden Death DOT — escalating damage per tick (combat timeout fallback)
SUDDEN_DEATH = _register(StatusDef(
    id="sudden_death",
    display_name="Sudden Death",
    stack_behaviour=StackBehaviour.STACK,  # Stacks escalate each tick
    dot_per_tick=5.0,
    dot_scales_with_stacks=True,
    dot_true_damage=True,  # Bypasses all mitigation — unstoppable timeout mechanic
))


# ---------------------------------------------------------------------------
# StatusInstance — runtime instance on a piece
# ---------------------------------------------------------------------------


@dataclass
class StatusInstance:
    """A live status effect on a piece."""
    status_id: str
    remaining_ticks: int
    stacks: int = 1
    source_id: str = ""

    @property
    def definition(self) -> StatusDef:
        return STATUS_DEFS[self.status_id]

    def has_gate(self, gate: StatusGate) -> bool:
        return gate in self.definition.gates
