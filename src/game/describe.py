"""Shared description render-layer (T.41) — pure, no Flet, no I/O (V.1/V.80).

One render path for player-facing entry descriptions (items now, traits in
T.41b), mirroring `ability_text.render_for` but for **champion-independent**
content: items and trait stat-packs grant fixed percentages, so there is no
caster source and no `Magnitude` machinery — just an authored name + blurb and a
**stat line derived from the live numbers** (introspected, never re-typed, V.78).

`RenderedEntry` is the shared shape every UI panel consumes. `render_item` reads
the item's `ITEM_META` (name + blurb) and derives the stat line by introspecting
the registered `EffectBundle` factory's modifiers — so the displayed number is
exactly the number combat applies and cannot drift (V.78). Rendering has **no
side effect** on combat state (V.80): the factory is built with a null owner and
only its declarative modifiers are read.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.game.registries import _short


@dataclass(frozen=True)
class ItemMeta:
    """Authored presentation metadata for one item id (transcribed from
    `docs/design/content/item_catalog.md`). The stat line is **not** stored here —
    it is derived from the item's `EffectBundle` at render time (V.78)."""

    name: str
    blurb: str


@dataclass(frozen=True)
class TraitMeta:
    """Authored presentation metadata for one trait (transcribed from
    `docs/design/content/trait_catalog.md`). `rungs` maps each breakpoint count
    (int, or ``"full"`` for the dynamic apex) → its effect description. Stat lines
    are derived from `_packs.TRAIT_STAT_PACKS`, not stored here (V.79)."""

    name: str
    blurb: str
    rungs: dict[object, str]


@dataclass(frozen=True)
class RenderedRung:
    """One rendered trait breakpoint — count label + effect text + derived stats."""

    count: object                   # int breakpoint, or "full" (dynamic apex)
    text: str
    stat_line: str = ""


@dataclass(frozen=True)
class RenderedTrait:
    """A rendered trait description — name + blurb + per-breakpoint rungs."""

    name: str
    blurb: str
    rungs: tuple[RenderedRung, ...] = ()


@dataclass(frozen=True)
class RenderedEntry:
    """A rendered description — pure data, no UI dependency. Shared by every
    description domain (items, traits, augments) and UI panel."""

    name: str
    text: str                       # authored blurb (flavor / effect prose)
    stat_line: str = ""             # derived "+12% STR" line (empty if none)
    tags: tuple[str, ...] = ()


# Fractional "add" stats that read as a percentage rather than a flat amount.
_PCT_ADD_STATS: frozenset[str] = frozenset({"crit_chance", "penetration_pct"})


def stat_line(
    muls: dict[str, float] | None = None,
    adds: dict[str, float] | None = None,
) -> str:
    """Render a stat delta line from **fractional** muls + flat adds.

    ``muls`` is ``{stat: fraction}`` where ``0.08`` ⇒ ``+8%`` (the trait/`_packs`
    convention). ``adds`` is ``{stat: amount}`` flat, except crit/pen% which read
    as a percentage. Labels use the canonical `registries._short` map so item,
    trait, and ability stat labels match. Deterministic, no RNG (V.2).
    """
    parts: list[str] = []
    for stat, frac in (muls or {}).items():
        parts.append(f"{frac * 100:+.0f}% {_short(stat)}")
    for stat, amount in (adds or {}).items():
        if stat in _PCT_ADD_STATS:
            parts.append(f"{amount * 100:+.0f}% {_short(stat)}")
        else:
            parts.append(f"{amount:+g} {_short(stat)}")
    return ", ".join(parts)


def _bundle_stat_line(item_id: str) -> str:
    """Derive an item's stat line by introspecting its registered `EffectBundle`.

    Builds the factory with a **null owner** (V.80 — no side effect; every item
    factory builds its declarative modifiers without dereferencing the owner) and
    reads `Modifier(stat, op, value)`: ``mul`` 1.12 ⇒ +12%, ``add`` flat. Hook
    riders carry no stat delta, so their effect comes from the blurb instead.
    """
    from src.game.registries import ITEM_REGISTRY

    factory = ITEM_REGISTRY.get(item_id)
    if factory is None:
        return ""
    bundle = factory(None)
    muls: dict[str, float] = {}
    adds: dict[str, float] = {}
    for mod in getattr(bundle, "modifiers", []):
        if mod.op == "mul":
            muls[mod.stat] = mod.value - 1.0
        elif mod.op == "add":
            adds[mod.stat] = adds.get(mod.stat, 0.0) + mod.value
        # "set" ops carry no readable delta — left to the blurb.
    return stat_line(muls, adds)


def render_item(item_id: str, *, derive_stats: bool = True) -> RenderedEntry | None:
    """Render one item id → `RenderedEntry` (name + blurb + derived stat line),
    or ``None`` if the id has no `ITEM_META`. Pure (V.1/V.80)."""
    from src.game.items.meta import ITEM_META

    meta = ITEM_META.get(item_id)
    if meta is None:
        return None
    line = _bundle_stat_line(item_id) if derive_stats else ""
    return RenderedEntry(name=meta.name, text=meta.blurb, stat_line=line)


def render_trait(trait_id: str) -> RenderedTrait | None:
    """Render one trait id → `RenderedTrait` (name + blurb + per-breakpoint rungs),
    or ``None`` if the trait has no `TRAIT_META`. Each rung's stat line is derived
    from `_packs.TRAIT_STAT_PACKS` (the same muls/adds the bundle applies, V.79).
    Pure (V.1/V.80)."""
    from src.game.traits.meta import TRAIT_META
    from src.game.traits._packs import TRAIT_STAT_PACKS

    meta = TRAIT_META.get(trait_id)
    if meta is None:
        return None
    packs = {label: (muls, adds) for label, muls, adds in TRAIT_STAT_PACKS.get(trait_id, [])}
    rungs: list[RenderedRung] = []
    for count, text in meta.rungs.items():
        muls, adds = packs.get(count, ({}, {}))
        rungs.append(RenderedRung(count=count, text=text, stat_line=stat_line(muls, adds)))
    return RenderedTrait(name=meta.name, blurb=meta.blurb, rungs=tuple(rungs))
