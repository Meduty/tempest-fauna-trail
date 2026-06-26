"""Stat-pack helpers + the `define_trait` registration shorthand (T.28a).

T.28a implements the **declarative stat-pack** portion of every trait ladder.
Mechanic riders (kiting, revive, second-wind, HoT, echo, spawns, …) layer onto
these same trait ids in T.28b/T.28c. Every rung here does *something* statwise so
no breakpoint is a no-op.

Magnitudes are first-pass percentages (`mul` modifiers, so they scale across
tiers) — to be retuned by a T.25 sim sweep. Convention: `source_id` =
`trait:<id>@<count>`.
"""

from __future__ import annotations

from typing import Union

from src.game.effects import EffectBundle, Lifetime, Modifier
from src.game.piece import Piece
from src.game.registries import register_trait

from .types import DynamicThreshold, TraitBreakpoint, TraitScope


def stat_pack_bundle(
    source_id: str,
    muls: dict[str, float] | None = None,
    adds: dict[str, float] | None = None,
) -> EffectBundle:
    """Build an `EffectBundle` of percentage (`mul`) and flat (`add`) stat mods.

    A `mul` of `0.08` means +8% (applied as `×1.08`). An `attack_speed` mul now
    moves tie-order on its own (T.29-pre, V.34): `attack_speed` is a float and the
    sort key derives from `round(attack_speed×1000)`, so cadence and order scale
    together — no separate `milli_AS` rider needed.
    """
    mods: list[Modifier] = []
    muls = muls or {}
    adds = adds or {}
    for stat, pct in muls.items():
        mods.append(Modifier(stat, "mul", 1.0 + pct, Lifetime.COMBAT, source_id))
    for stat, amount in adds.items():
        mods.append(Modifier(stat, "add", amount, Lifetime.COMBAT, source_id))
    return EffectBundle(modifiers=mods)


# A rung spec: (count, scope, muls[, adds[, hook_builders]]).
#   hook_builders: list[Callable[[Piece, str], list[Hook]]] — mechanic riders
#   (T.28b/c) that add event hooks to the rung's bundle, given (owner, source_id).
Rung = tuple


# trait_id -> [(rung label, muls, adds), …] — the raw stat packs per breakpoint,
# captured at registration so the description layer (T.41b, `describe.render_trait`)
# can derive each rung's stat line from the *same* numbers the bundle applies
# (V.79 — the shown stat can't drift from combat). Label is the int breakpoint or
# "full" for the dynamic apex (mirrors `source_id`).
TRAIT_STAT_PACKS: dict[str, list[tuple[object, dict[str, float], dict[str, float]]]] = {}


def define_trait(trait_id: str, *rungs: Rung) -> None:
    """Register a trait. Each rung is `(count, scope, muls[, adds[, hooks]])`.

    `count` is an int or `DynamicThreshold`. `hooks` is an optional list of
    builders `(owner, source_id) -> list[Hook]` for mechanic riders. The bundle
    for a rung is built once per target piece.
    """
    breakpoints: list[TraitBreakpoint] = []
    stat_packs: list[tuple[object, dict[str, float], dict[str, float]]] = []
    for rung in rungs:
        count: Union[int, DynamicThreshold] = rung[0]
        scope: TraitScope = rung[1]
        muls: dict[str, float] = rung[2]
        adds: dict[str, float] = rung[3] if len(rung) > 3 else {}
        hook_builders = rung[4] if len(rung) > 4 else []
        label = count if isinstance(count, int) else "full"
        source_id = f"trait:{trait_id}@{label}"
        stat_packs.append((label, muls, adds))

        # Bind loop vars via defaults so each factory captures its own rung.
        def _factory(piece: Piece, _sid=source_id, _m=muls, _a=adds, _hb=hook_builders) -> EffectBundle:
            bundle = stat_pack_bundle(_sid, _m, _a)
            for build in _hb:
                bundle.hooks.extend(build(piece, _sid))
            return bundle

        breakpoints.append(TraitBreakpoint(count=count, scope=scope, bundle_factory=_factory))

    TRAIT_STAT_PACKS[trait_id] = stat_packs
    register_trait(trait_id)(lambda _bps=breakpoints: _bps)
