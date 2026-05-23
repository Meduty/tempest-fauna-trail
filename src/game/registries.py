"""Registries — @register decorators and registry dicts (T20).

Content modules decorate their factories with @register_active, @register_passive,
etc. Importing the content package triggers all decorators. The engine and
loadout compiler look up abilities by string id from these dicts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from src.game.effects import EffectBundle, SourceTag


# ---------------------------------------------------------------------------
# Ability registries
# ---------------------------------------------------------------------------

# Active abilities: id -> handler(ctx, actor, targets) -> None
ABILITY_REGISTRY: dict[str, Callable] = {}

# Passive abilities: id -> factory(owner) -> EffectBundle
PASSIVE_REGISTRY: dict[str, Callable] = {}

# Item factories: id -> factory(owner) -> EffectBundle
ITEM_REGISTRY: dict[str, Callable] = {}

# Trait factories: id -> factory() -> list[TraitBreakpoint]
TRAIT_REGISTRY: dict[str, Callable] = {}

# Augment registry: id -> Augment
AUGMENT_REGISTRY: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------


def register_active(ability_id: str) -> Callable:
    """Decorator to register an active ability handler.

    Usage:
        @register_active("storm_surge")
        def storm_surge(ctx, actor, targets):
            ...
    """
    def decorator(fn: Callable) -> Callable:
        ABILITY_REGISTRY[ability_id] = fn
        return fn
    return decorator


def register_passive(passive_id: str) -> Callable:
    """Decorator to register a passive ability factory.

    Usage:
        @register_passive("static_buildup")
        def static_buildup(owner):
            ...  # returns EffectBundle
    """
    def decorator(fn: Callable) -> Callable:
        PASSIVE_REGISTRY[passive_id] = fn
        return fn
    return decorator


def register_item(item_id: str) -> Callable:
    """Decorator to register an item factory."""
    def decorator(fn: Callable) -> Callable:
        ITEM_REGISTRY[item_id] = fn
        return fn
    return decorator


def register_trait(trait_id: str) -> Callable:
    """Decorator to register a trait factory."""
    def decorator(fn: Callable) -> Callable:
        TRAIT_REGISTRY[trait_id] = fn
        return fn
    return decorator


# ---------------------------------------------------------------------------
# SimpleActive — declarative ability registration
# ---------------------------------------------------------------------------


@dataclass
class SimpleActive:
    """Declarative simple ability definition.

    For "deal X damage to primary target" style abilities.
    """
    target: str = "primary"  # TargetSelector key
    damage: float = 0.0
    scaling: str = ""  # e.g. "str*1.5" or "int*2.0"
    tag: SourceTag = SourceTag.ABILITY
    heal_amount: float = 0.0
    heal_scaling: str = ""
    heal_target: str = ""  # "lowest_hp_ally" etc.


def register_active_simple(ability_id: str, spec: SimpleActive) -> None:
    """Register a declarative simple ability. Synthesises a handler."""

    def handler(ctx: Any, actor: Any, targets: list) -> None:
        from src.game.targeting import resolve_targets

        actual_targets = resolve_targets(spec.target, actor, ctx)
        if not actual_targets:
            return

        if spec.damage > 0 or spec.scaling:
            amount = _eval_scaling(spec.damage, spec.scaling, actor)
            for t in actual_targets:
                ctx.deal_damage(actor, t, amount, spec.tag)

        if spec.heal_amount > 0 or spec.heal_scaling:
            heal_targets = resolve_targets(spec.heal_target, actor, ctx) if spec.heal_target else []
            amount = _eval_scaling(spec.heal_amount, spec.heal_scaling, actor)
            for t in heal_targets:
                ctx.heal(actor, t, amount)

    ABILITY_REGISTRY[ability_id] = handler


def _eval_scaling(base: float, scaling: str, actor: Any) -> float:
    """Evaluate a scaling expression like 'str*1.5' or 'int*2.0+100'."""
    if not scaling:
        return base

    total = base
    parts = scaling.replace("-", "+-").split("+")
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if "*" in part:
            stat_name, coeff = part.split("*", 1)
            stat_name = stat_name.strip()
            coeff_val = float(coeff.strip())
            stat_val = actor.stat(stat_name) if hasattr(actor, "stat") else 0.0
            total += stat_val * coeff_val
        else:
            try:
                total += float(part)
            except ValueError:
                pass

    return total
