"""Core effect substrate (T20) — effect_systems_design.md §4.

Modifier, Hook, EffectBundle, EventBus, SourceTag, HookScope, Lifetime.
This module has zero game-specific logic — it is the vocabulary.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Literal


# ---------------------------------------------------------------------------
# Lifetime — determines when a modifier is removed
# ---------------------------------------------------------------------------


class Lifetime(str, Enum):
    PERMANENT = "permanent"  # Survives across combats
    COMBAT = "combat"  # Cleared at on_combat_end (default)
    TIMED = "timed"  # Removed when current_tick >= expires_at_tick


# ---------------------------------------------------------------------------
# SourceTag — damage attribution
# ---------------------------------------------------------------------------


class SourceTag(str, Enum):
    BASIC_ATTACK = "basic_attack"
    ABILITY = "ability"
    ITEM_PROC = "item_proc"
    DOT = "dot"
    STATUS = "status"
    REFLECT = "reflect"
    TRUE = "true"


# ---------------------------------------------------------------------------
# Modifier — declarative stat delta
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Modifier:
    """A declarative stat modification.

    Stat computation: (base + Σ adds) × Π muls. 'set' overrides all; last set wins.
    """

    stat: str
    op: Literal["add", "mul", "set"]
    value: float
    lifetime: Lifetime = Lifetime.COMBAT
    source_id: str = ""
    expires_at_tick: int | None = None


def compute_stat(piece: Any, stat: str) -> float:
    """Compute effective stat value from base + modifiers.

    Order: (base + sum(adds)) * prod(muls). 'set' overrides everything.
    """
    base = piece.base_stats.get(stat, 0.0)
    adds = 0.0
    muls: list[float] = []
    setters: list[float] = []

    for m in piece.modifiers:
        if m.stat != stat:
            continue
        if m.op == "add":
            adds += m.value
        elif m.op == "mul":
            muls.append(m.value)
        elif m.op == "set":
            setters.append(m.value)

    if setters:
        return setters[-1]

    result = base + adds
    for mul in muls:
        result *= mul
    return result


# ---------------------------------------------------------------------------
# HookScope — dedup enforcement
# ---------------------------------------------------------------------------


class HookScope(str, Enum):
    PER_HIT = "per_hit"
    ONCE_PER_CAST = "once_per_cast"
    ONCE_PER_TARGET = "once_per_target"
    ONCE_PER_COMBAT = "once_per_combat"


# ---------------------------------------------------------------------------
# Hook — event subscription
# ---------------------------------------------------------------------------


@dataclass
class Hook:
    """An event subscription. The bus enforces scope dedup."""

    event: str
    handler: Callable
    priority: int = 0
    scope: HookScope = HookScope.PER_HIT
    hook_id: str = ""  # Auto-assigned at subscribe time


# ---------------------------------------------------------------------------
# EffectBundle — registration payload
# ---------------------------------------------------------------------------


@dataclass
class EffectBundle:
    """Registration descriptor — not a runtime value type.

    Handed to apply_bundle() once at loadout time or phase-change time.
    Used identically by items, augments, traits, passives, and boss phase hooks.
    """

    modifiers: list[Modifier] = field(default_factory=list)
    hooks: list[Hook] = field(default_factory=list)
    statuses: list[tuple[str, int]] = field(default_factory=list)
    granted_abilities: list[str] = field(default_factory=list)
    granted_traits: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# EventBus — synchronous event dispatch with scope dedup
# ---------------------------------------------------------------------------


class EventBus:
    """Synchronous event dispatch with priority ordering and scope dedup."""

    def __init__(self) -> None:
        self._hooks: dict[str, list[Hook]] = {}
        self._next_id: int = 0
        self._dedup_ledger: set[tuple] = set()

    def subscribe(self, hook: Hook) -> str:
        """Register a hook and return assigned hook_id."""
        hook_id = f"hook_{self._next_id}"
        self._next_id += 1
        hook.hook_id = hook_id
        if hook.event not in self._hooks:
            self._hooks[hook.event] = []
        self._hooks[hook.event].append(hook)
        # Re-sort by priority (descending), stable
        self._hooks[hook.event].sort(key=lambda h: -h.priority)
        return hook_id

    def unsubscribe(self, hook_id: str) -> None:
        """Remove a hook by its id."""
        for event_name, hooks in self._hooks.items():
            for i, hook in enumerate(hooks):
                if hook.hook_id == hook_id:
                    hooks.pop(i)
                    return

    def fire(self, event_name: str, event: Any, *, cast_id: int | None = None, ctx: Any = None) -> None:
        """Synchronous dispatch — fire all hooks for this event.

        Hooks receive (ctx, event) — ctx is the CombatContext.
        """
        hooks = self._hooks.get(event_name)
        if not hooks:
            return
        for hook in list(hooks):  # copy to allow mid-iteration unsubscribe
            if self._should_dedup(hook, event, cast_id):
                continue
            hook.handler(ctx, event)

    def fire_reducing(
        self, event_name: str, event: Any, value: float, *, cast_id: int | None = None, ctx: Any = None
    ) -> float:
        """For on_damage_pre style hooks that modify a numeric value.

        Hooks receive (ctx, event, value) and return the modified value.
        """
        hooks = self._hooks.get(event_name)
        if not hooks:
            return value
        for hook in list(hooks):
            if self._should_dedup(hook, event, cast_id):
                continue
            result = hook.handler(ctx, event, value)
            if result is not None:
                value = result
        return value

    def reset_combat(self) -> None:
        """Clear ONCE_PER_COMBAT dedup ledger."""
        self._dedup_ledger.clear()

    def clear_cast(self, cast_id: int) -> None:
        """Clear per-cast dedup entries for a finished cast."""
        self._dedup_ledger = {
            key for key in self._dedup_ledger if len(key) < 2 or key[1] != cast_id
        }

    def _should_dedup(self, hook: Hook, event: Any, cast_id: int | None) -> bool:
        """Check scope dedup. Returns True if this hook should be skipped."""
        if hook.scope == HookScope.PER_HIT:
            return False

        if hook.scope == HookScope.ONCE_PER_COMBAT:
            key = ("combat", hook.hook_id)
            if key in self._dedup_ledger:
                return True
            self._dedup_ledger.add(key)
            return False

        if hook.scope == HookScope.ONCE_PER_CAST:
            if cast_id is None:
                return False
            key = ("cast", cast_id, hook.hook_id)
            if key in self._dedup_ledger:
                return True
            self._dedup_ledger.add(key)
            return False

        if hook.scope == HookScope.ONCE_PER_TARGET:
            if cast_id is None:
                return False
            target_id = getattr(event, "target", None)
            if target_id is not None:
                target_id = getattr(target_id, "id", id(target_id))
            key = ("target", cast_id, hook.hook_id, target_id)
            if key in self._dedup_ledger:
                return True
            self._dedup_ledger.add(key)
            return False

        return False
