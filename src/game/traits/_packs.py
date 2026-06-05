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

    A `mul` of `0.08` means +8% (applied as `×1.08`). An `attack_speed` mul also
    rides `milli_AS` (the sub-integer tie-order field, V.34) so ordering stays
    exact after the buff — mirroring how weather scales both.
    """
    mods: list[Modifier] = []
    muls = muls or {}
    adds = adds or {}
    for stat, pct in muls.items():
        mods.append(Modifier(stat, "mul", 1.0 + pct, Lifetime.COMBAT, source_id))
        if stat == "attack_speed":
            mods.append(Modifier("milli_AS", "mul", 1.0 + pct, Lifetime.COMBAT, source_id))
    for stat, amount in adds.items():
        mods.append(Modifier(stat, "add", amount, Lifetime.COMBAT, source_id))
    return EffectBundle(modifiers=mods)


# A rung spec: (count, scope, muls, adds). `adds` optional.
Rung = tuple


def define_trait(trait_id: str, *rungs: Rung) -> None:
    """Register a trait whose every rung is a declarative stat pack.

    Each rung is `(count, scope, muls[, adds])`; `count` is an int or a
    `DynamicThreshold`. The bundle for a rung is built once per target piece.
    """
    breakpoints: list[TraitBreakpoint] = []
    for rung in rungs:
        count: Union[int, DynamicThreshold] = rung[0]
        scope: TraitScope = rung[1]
        muls: dict[str, float] = rung[2]
        adds: dict[str, float] = rung[3] if len(rung) > 3 else {}
        label = count if isinstance(count, int) else "full"
        source_id = f"trait:{trait_id}@{label}"
        # Bind loop vars via defaults so each factory captures its own rung.
        def _factory(piece: Piece, _sid=source_id, _m=muls, _a=adds) -> EffectBundle:
            return stat_pack_bundle(_sid, _m, _a)

        breakpoints.append(TraitBreakpoint(count=count, scope=scope, bundle_factory=_factory))

    register_trait(trait_id)(lambda _bps=breakpoints: _bps)
