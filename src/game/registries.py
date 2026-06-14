"""Registries — @register decorators and registry dicts (T20).

Content modules decorate their factories with @register_active, @register_passive,
etc. Importing the content package triggers all decorators. The engine and
loadout compiler look up abilities by string id from these dicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable

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


# Short-hand → canonical stat name mapping (shared by _eval_scaling + _short).
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

# Canonical stat name -> short UPPER label for formula pretty-printing (V.46;
# moved here from ability_text so each Magnitude self-renders without a cycle).
_STAT_SHORT: dict[str, str] = {
    "strength": "STR",
    "intelligence": "INT",
    "attack_speed": "AS",
    "move_speed": "MS",
    "mana_regen": "MR",
    "armor": "ARM",
    "resistance": "RES",
    "penetration": "PEN",
    "penetration_pct": "PEN%",
    "max_hp": "HP",
    "attack_range": "RNG",
    "crit_chance": "CRIT",
}


def _short(stat_name: str) -> str:
    canon = _STAT_ALIASES.get(stat_name, stat_name)
    return _STAT_SHORT.get(canon, canon.upper())


def _eval_scaling(base: float, scaling: str, actor: Any) -> float:
    """Evaluate a scaling expression like 'strength*1.5' or 'intelligence*2.0+100'.

    Stat name aliases are supported for convenience (e.g. 'str' → 'strength',
    'int' → 'intelligence').  Unknown stat names produce a zero contribution so
    that typos are silent no-ops rather than exceptions; they will be flagged as
    a ValueError if strict validation is ever required.
    """
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


@runtime_checkable
class Magnitude(Protocol):
    """A single stat-scaled numeric outlet, GAS-modeled (V.46).

    The **closed** family — ``ScalingTerm`` (linear), ``PctResource``
    (%-of-resource), ``MaxOfTerm`` (max-of-stats), ``SetByCaller`` (runtime
    value) — shares this Protocol so a handler reads the number via
    ``eval(...)`` and the tooltip renders the *same* object (source-of-truth B,
    V.38): the two can never drift. Every kind is pure + RNG-free (V.2/V.14) and
    **self-describing** so ``ability_text.render`` is pure per-kind dispatch.
    """

    label: str
    def eval(self, source: Any, target: Any = None, caller: Any = None) -> float: ...
    def render_formula(self, source: Any) -> str: ...
    def render_inline(self, source: Any) -> str: ...
    def render_token(self, source: Any) -> str: ...   # the {label} substitution string


def _parse_scaling(scaling: str, source: Any) -> list[tuple[str, float, float]]:
    """Decompose a linear expr into ``(short, coeff, value)`` per stat term.

    Mirrors ``_eval_scaling``'s grammar (split on ``+``, ``*`` per part) — shared
    by ``ScalingTerm``'s formula + inline renderers so both read the same coeffs.
    """
    scales: list[tuple[str, float, float]] = []
    expr = scaling.replace("-", "+-") if scaling else ""
    for part in expr.split("+"):
        part = part.strip()
        if not part or "*" not in part:
            continue
        stat_name, coeff = part.split("*", 1)
        stat_name = stat_name.strip()
        short = _short(stat_name)
        canon = _STAT_ALIASES.get(stat_name, stat_name)
        val = source.stat(canon) if hasattr(source, "stat") else 0.0
        scales.append((short, float(coeff.strip()), float(val)))
    return scales


@dataclass(frozen=True)
class ScalingTerm:
    """A linear outlet: ``base [+ stat*coeff ...]`` (GAS AttributeBased+ScalableFloat).

    ``label`` is the ``{token}`` it fills in an ``AbilityMeta.blurb`` / clause
    template. ``eval`` reuses the engine's ``_eval_scaling`` so the rendered
    number equals the number the handler computes. ``target``/``caller`` are
    accepted (Protocol parity) but unused — keeps the linear kind byte-identical.
    """

    label: str          # "damage" | "heal" | "shield" | "bonus" ...
    base: float         # the literal the handler used (e.g. 40.0)
    scaling: str = ""   # _eval_scaling expr, e.g. "intelligence*2.5"
    note: str = ""      # optional ("per hit", "to each enemy in radius 2")

    def eval(self, source: Any, target: Any = None, caller: Any = None) -> float:
        return _eval_scaling(self.base, self.scaling, source)

    def render_formula(self, source: Any) -> str:
        scales = _parse_scaling(self.scaling, source)
        pieces: list[str] = []
        stat_notes: list[str] = []
        if self.base:
            pieces.append(f"{self.base:g}")
        for short, coeff, val in scales:
            pieces.append(f"{coeff * 100:g}% {short}")
            stat_notes.append(f"{short} {coeff:g}×{val:g}")
        rhs = " + ".join(pieces) if pieces else "0"
        note = f"  ({', '.join(stat_notes)})" if stat_notes else ""
        return f"{round(self.eval(source))} = {rhs}{note}"

    def render_inline(self, source: Any) -> str:
        scales = _parse_scaling(self.scaling, source)
        if not scales:
            return ""
        parts = [f"{self.base:g}"] if self.base else []
        parts += [f"+{coeff * 100:g}% {short}" for short, coeff, _val in scales]
        return " ".join(parts)

    def render_token(self, source: Any) -> str:
        return str(round(self.eval(source)))


@dataclass(frozen=True)
class PctResource:
    """A ``%-of-resource`` outlet (GAS AttributeBased, resource-typed).

    Reads ``.max_hp`` (or another resource attribute) **directly** — not via
    ``.stat()`` — because ``Piece.stat("max_hp")`` is ``0`` in combat (max_hp is a
    Piece attribute, not a ``base_stats`` key; see ``effects.compute_stat``).
    ``of="target"`` reads the target's resource (cross-entity); falls back to
    ``source`` when no target is supplied (render time).
    """

    label: str
    pct: float                 # 0.08 == 8%
    of: str = "self"           # "self" | "target"
    resource: str = "max_hp"
    note: str = ""

    def _obj(self, source: Any, target: Any) -> Any:
        return target if (self.of == "target" and target is not None) else source

    def eval(self, source: Any, target: Any = None, caller: Any = None) -> float:
        return float(getattr(self._obj(source, target), self.resource, 0.0)) * self.pct

    def render_formula(self, source: Any) -> str:
        who = "target " if self.of == "target" else ""
        base_val = float(getattr(source, self.resource, 0.0))
        return (
            f"{round(self.eval(source))} = {self.pct * 100:g}% {who}"
            f"{_short(self.resource)}  ({_short(self.resource)} {base_val:g})"
        )

    def render_inline(self, source: Any) -> str:
        who = "target " if self.of == "target" else ""
        return f"{self.pct * 100:g}% {who}{_short(self.resource)}"

    def render_token(self, source: Any) -> str:
        return str(round(self.eval(source)))


@dataclass(frozen=True)
class MaxOfTerm:
    """``base + max(stat...) * coeff`` (GAS CustomCalculationClass).

    Non-linear: the grammar of ``ScalingTerm`` (``+``/``*`` only) cannot express
    ``max()``, so this is its own kind.
    """

    label: str
    coeff: float
    stats: tuple[str, ...] = ("strength", "intelligence")
    base: float = 0.0
    note: str = ""

    def _vals(self, source: Any) -> list[float]:
        return [
            float(source.stat(_STAT_ALIASES.get(s, s))) if hasattr(source, "stat") else 0.0
            for s in self.stats
        ]

    def eval(self, source: Any, target: Any = None, caller: Any = None) -> float:
        vals = self._vals(source)
        return self.base + (max(vals) if vals else 0.0) * self.coeff

    def render_formula(self, source: Any) -> str:
        shorts = "/".join(_short(s) for s in self.stats)
        notes = ", ".join(
            f"{_short(s)} {v:g}" for s, v in zip(self.stats, self._vals(source))
        )
        base_p = f"{self.base:g} + " if self.base else ""
        note = f"  ({notes})" if notes else ""
        return f"{round(self.eval(source))} = {base_p}{self.coeff * 100:g}% higher of {shorts}{note}"

    def render_inline(self, source: Any) -> str:
        shorts = "/".join(_short(s) for s in self.stats)
        return f"{self.coeff * 100:g}% higher of {shorts}"

    def render_token(self, source: Any) -> str:
        return str(round(self.eval(source)))


@dataclass(frozen=True)
class SetByCaller:
    """``base + caller[key] * coeff`` — a runtime value the handler injects (GAS SetByCaller).

    The runtime quantity (e.g. a live stack count) has no pre-combat value, so
    the renderer shows the **rate**, not a total. The handler passes
    ``caller={key: n}`` to ``eval``.
    """

    label: str
    base: float = 0.0
    coeff: float = 1.0
    key: str = "stacks"
    note: str = ""

    def eval(self, source: Any, target: Any = None, caller: Any = None) -> float:
        v = float((caller or {}).get(self.key, 0.0))
        return self.base + v * self.coeff

    def render_formula(self, source: Any) -> str:
        base_p = f"{self.base:g} + " if self.base else ""
        return f"{base_p}{self.coeff:g} per {self.key}"

    def render_inline(self, source: Any) -> str:
        base_p = f"{self.base:g} " if self.base else ""
        return f"{base_p}+{self.coeff:g}/{self.key}"

    def render_token(self, source: Any) -> str:
        # Runtime quantity has no pre-combat total — the token shows the rate.
        base_p = f"{self.base:g} + " if self.base else ""
        return f"{base_p}{self.coeff:g}"


@dataclass(frozen=True)
class Clause:
    """A static/conditional prose line — e.g. ``+50% vs targets below 30% HP``.

    Either plain ``text``, **or** a ``{token}`` ``template`` filled live from
    ``terms`` (A1, V.46) so a Tier-B scaler's prose number cannot drift from the
    handler's (the handler reads the same ``terms``).
    """

    text: str = ""
    template: str = ""
    terms: tuple[Magnitude, ...] = ()


@dataclass(frozen=True)
class AbilityMeta:
    """Presentation metadata for one roster ability id.

    ``blurb`` is prose with ``{label}`` slots filled by the matching
    ``Magnitude`` rounded against a render source. ``clauses`` are extra
    sentences (conditionals, cadences, status durations) that may carry their own
    ``terms``. ``tags`` are UI-iconography labels owned by this layer (not the
    trait/role vocab).
    """

    name: str
    kind: str                                   # "active" | "passive"
    blurb: str
    terms: tuple[Magnitude, ...] = ()
    clauses: tuple[Clause, ...] = ()
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class SummonSpec:
    """Declarative summon statline (GAS-style): flat literals + ``Magnitude`` fractions.

    Keeps summon stat-fractions introspectable + drift-safe (they reuse the
    Magnitude family) instead of inline ``actor.stat(...)`` math in the handler.
    ``eval(owner)`` resolves every entry to a concrete ``base_stats`` value.
    """

    stats: dict[str, Any] = field(default_factory=dict)  # key -> number | Magnitude
    note: str = ""

    def eval(self, source: Any) -> dict[str, Any]:
        # Magnitudes resolve against `source`; flat literals pass through verbatim
        # (int stays int) so a built statline is byte-identical to inline (V.2/V.14).
        return {
            k: (v.eval(source) if hasattr(v, "eval") else v)
            for k, v in self.stats.items()
        }


# id -> AbilityMeta, keyed by the same roster ability-id strings as the
# ABILITY_REGISTRY / PASSIVE_REGISTRY dicts.
ABILITY_META: dict[str, AbilityMeta] = {}
