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
    scaling: str = ""  # e.g. "strength*1.5" or "intelligence*2.0"
    tag: SourceTag = SourceTag.ABILITY
    heal_amount: float = 0.0
    heal_scaling: str = ""  # e.g. "intelligence*0.5"
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
    """Evaluate a scaling expression like 'strength*1.5' or 'intelligence*2.0+100'.

    Stat name aliases are supported for convenience (e.g. 'str' → 'strength',
    'int' → 'intelligence').  Unknown stat names produce a zero contribution so
    that typos are silent no-ops rather than exceptions; they will be flagged as
    a ValueError if strict validation is ever required.
    """
    # Short-hand → canonical stat name mapping
    _STAT_ALIASES: dict[str, str] = {
        "str": "strength",
        "int": "intelligence",
        "atk": "attack_speed",
        "spd": "move_speed",
        "mr": "mana_regen",
        "arm": "armor",
        "res": "resistance",
        "pen": "penetration",
    }

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
            stat_name = _STAT_ALIASES.get(stat_name, stat_name)
            coeff_val = float(coeff.strip())
            stat_val = actor.stat(stat_name) if hasattr(actor, "stat") else 0.0
            total += stat_val * coeff_val
        else:
            try:
                total += float(part)
            except ValueError:
                pass

    return total


# ---------------------------------------------------------------------------
# Ability description metadata (T.34) — parallel registry to ABILITY/PASSIVE
# ---------------------------------------------------------------------------
#
# These types are the *presentation* layer over the ability handlers. A
# ``ScalingTerm`` is the single home of a handler's headline damage/heal number
# (source-of-truth B, V.38): the handler reads it via ``term.eval(actor)`` and
# the tooltip renders the same object, so the two can never drift. ``eval``
# delegates to the same ``_eval_scaling`` the engine has always used, so moving
# a literal into a term is byte-identical to the inline call (V.2/V.14).


@dataclass(frozen=True)
class ScalingTerm:
    """A single damage/heal/shield outlet: ``base [+ stat*coeff ...]``.

    ``label`` is the ``{token}`` it fills in an ``AbilityMeta.blurb``.
    ``eval(source)`` reuses the engine's ``_eval_scaling`` so the rendered
    number equals the number the handler computes.
    """

    label: str          # "damage" | "heal" | "shield" | "bonus" ...
    base: float         # the literal the handler used (e.g. 40.0)
    scaling: str = ""   # _eval_scaling expr, e.g. "intelligence*2.5"
    note: str = ""      # optional ("per hit", "to each enemy in radius 2")

    def eval(self, source: Any) -> float:
        return _eval_scaling(self.base, self.scaling, source)


@dataclass(frozen=True)
class Clause:
    """A static/conditional prose line — e.g. ``+50% vs targets below 30% HP``."""

    text: str


@dataclass(frozen=True)
class AbilityMeta:
    """Presentation metadata for one roster ability id.

    ``blurb`` is prose with ``{label}`` slots filled by the matching
    ``ScalingTerm`` rounded against a render source. ``clauses`` are extra
    sentences (conditionals, cadences, status durations). ``tags`` are
    UI-iconography labels owned by this layer (not the trait/role vocab).
    """

    name: str
    kind: str                                   # "active" | "passive"
    blurb: str
    terms: tuple[ScalingTerm, ...] = ()
    clauses: tuple[Clause, ...] = ()
    tags: tuple[str, ...] = ()


# id -> AbilityMeta, keyed by the same roster ability-id strings as the
# ABILITY_REGISTRY / PASSIVE_REGISTRY dicts.
ABILITY_META: dict[str, AbilityMeta] = {}
