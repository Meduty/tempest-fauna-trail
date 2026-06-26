"""Synergy trait layer (T.28a).

Resolves trait breakpoints from the fielded board and applies their bundles in
`compile_loadout`. Counting is by **unique champion id** (V.21); enemies never
light up (V.22). Affinity traits are **derived** from each piece's `affinity`
(V.6), never from live weather. Pure + RNG-free → replay-stable.

The `affinities`/`kinships`/`callings` imports below register all 24 traits into
`TRAIT_REGISTRY` as a side effect (mirrors how `loadout` imports `abilities`).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from src.game.models import WeatherState
from src.game.piece import Piece
from src.game.registries import TRAIT_REGISTRY

from .types import DynamicThreshold, TraitBreakpoint, TraitScope

# Register all trait factories (import for side effect).
from . import affinities as _affinities  # noqa: F401,E402
from . import kinships as _kinships  # noqa: F401,E402
from . import callings as _callings  # noqa: F401,E402

__all__ = [
    "TraitScope",
    "TraitBreakpoint",
    "DynamicThreshold",
    "TraitPreview",
    "affinity_trait",
    "resolve_and_apply_traits",
    "mark_weather_overrides",
    "preview_team_traits",
]

# Scaled @8 — the rung count whose apex grants the full favorable weather override.
_SCALED_WEATHER_OVERRIDE_RUNG = 8

# Affinity → derived affinity-trait tag (V.6 stays one field; no node weather).
_AFFINITY_TRAIT: dict[WeatherState, str] = {
    WeatherState.CLEAR: "Sunlit",
    WeatherState.CLOUDY: "Overcast",
    WeatherState.MIST: "Shrouded",
    WeatherState.RAIN: "Stormfed",
    WeatherState.SNOW: "Frostbound",
    WeatherState.THUNDER: "Galvanized",
}


def affinity_trait(affinity: WeatherState) -> str:
    """The synthetic affinity-trait tag for a piece's affinity."""
    return _AFFINITY_TRAIT[affinity]


def _piece_tags(piece: Piece) -> set[str]:
    """All trait tags a piece contributes: authored Kinship/Calling + derived affinity."""
    tags = set(piece.traits)
    tags.add(affinity_trait(piece.affinity))
    return tags


def _resolve_traits(
    team_pieces: list[Piece], board_cap: int,
    bonus_counts: dict[str, int] | None = None,
) -> dict[str, tuple[TraitBreakpoint, int, int]]:
    """Map each cleared trait → (breakpoint, unique-carrier count, threshold).

    Counts unique champion ids (V.21). Highest cleared rung wins. Dynamic
    thresholds are resolved against `(team_pieces, board_cap)`. `bonus_counts`
    (augment Crest/Crown/Worldroot, T.31) adds virtual carriers to a tag's count
    before breakpoint selection — deterministic, RNG-free (V.2/V.14).
    """
    bonus_counts = bonus_counts or {}
    carriers: dict[str, set[str]] = defaultdict(set)
    for piece in team_pieces:
        for tag in _piece_tags(piece):
            carriers[tag].add(piece.id)
    # Augment trait bonuses can light up a tag with zero native carriers.
    for tag in bonus_counts:
        carriers.setdefault(tag, set())

    cleared: dict[str, tuple[TraitBreakpoint, int, int]] = {}
    for tag, ids in carriers.items():
        factory = TRAIT_REGISTRY.get(tag)
        if factory is None:
            continue
        count = len(ids) + bonus_counts.get(tag, 0)
        best: TraitBreakpoint | None = None
        best_thr = -1
        for bp in factory():
            thr = bp.count(team_pieces, board_cap) if callable(bp.count) else bp.count
            if count >= thr and thr > best_thr:
                best, best_thr = bp, thr
        if best is not None:
            cleared[tag] = (best, count, best_thr)
    return cleared


@dataclass(frozen=True)
class TraitPreview:
    """Pre-combat tally of one trait the player team carries (UI read-only)."""

    trait: str
    count: int               # unique carriers (V.21)
    threshold: int           # highest cleared breakpoint (0 = below the first rung)
    next_threshold: int | None  # next rung to clear, or None at the top rung


def preview_team_traits(
    team: list[Any], board_cap: int | None = None
) -> list[TraitPreview]:
    """Pure pre-combat trait tally for the UI — every registered trait the team
    carries, with carrier count + cleared/next breakpoints (V.1, RNG-free V.2).

    ``team`` is the player's fielded units — ``Champion`` or ``Piece`` (only
    ``.id``/``.traits``/``.affinity`` are read, via ``_piece_tags``). Mirrors the
    `_resolve_traits` roll-up (V.21) but exposes **partial** progress too (count
    below the first rung), so the panel can grey unfilled traits like TFT.
    ``board_cap`` defaults to the fielded size (the combat convention) for dynamic
    thresholds. Sorted cleared-first, then by trait name."""
    cap = board_cap if board_cap is not None else len(team)
    carriers: dict[str, set[str]] = defaultdict(set)
    for piece in team:
        for tag in _piece_tags(piece):
            carriers[tag].add(piece.id)
    out: list[TraitPreview] = []
    for tag, ids in carriers.items():
        factory = TRAIT_REGISTRY.get(tag)
        if factory is None:
            continue
        count = len(ids)
        thresholds = sorted(
            bp.count(team, cap) if callable(bp.count) else bp.count for bp in factory()
        )
        cleared = max((t for t in thresholds if count >= t), default=0)
        nxt = next((t for t in thresholds if t > count), None)
        out.append(TraitPreview(tag, count, cleared, nxt))
    out.sort(key=lambda p: (p.threshold == 0, p.trait))
    return out


def mark_weather_overrides(pieces: list[Piece]) -> None:
    """Set `Piece.weather_favored` on Scaled @8 carriers BEFORE weather is applied.

    Scaled @8 (T.28d) grants the favorable weather pack regardless of affinity.
    Weather is folded into `base_stats` at loadout step 2, *before* trait bundles
    apply (step 3) — so the flag must be resolved up front. This runs the same pure,
    RNG-free `_resolve_traits` roll-up (V.21) and marks carriers; the loadout's
    `_apply_weather_to_piece` reads the flag. Player team only (V.22)."""
    team = [p for p in pieces if not p.is_enemy]
    cleared = _resolve_traits(team, len(team))
    scaled = cleared.get("Scaled")
    if scaled is None or scaled[2] < _SCALED_WEATHER_OVERRIDE_RUNG:
        return
    for piece in team:
        if "Scaled" in _piece_tags(piece):
            piece.weather_favored = True


def resolve_and_apply_traits(
    pieces: list[Piece], bus, bonus_counts: dict[str, int] | None = None
) -> list[tuple[str, int, int]]:
    """Resolve + apply trait bundles to the player team; return activations.

    Player team only (enemies never light up — V.22). `board_cap` for dynamic
    thresholds is the fielded team size. `bonus_counts` carries augment Crest/Crown
    virtual carriers (T.31). Returns a sorted
    `[(trait_id, count, threshold), …]` for the `BattleResult` record.
    """
    from src.game.loadout import apply_bundle  # deferred: loadout imports this module

    team = [p for p in pieces if not p.is_enemy]
    board_cap = len(team)
    cleared = _resolve_traits(team, board_cap, bonus_counts)

    activations: list[tuple[str, int, int]] = []
    for tag in sorted(cleared):
        bp, count, thr = cleared[tag]
        if bp.scope is TraitScope.TEAM_WIDE:
            targets = team
        else:
            targets = [p for p in team if tag in _piece_tags(p)]
        for piece in targets:
            apply_bundle(piece, bp.bundle_factory(piece), bus)
        activations.append((tag, count, thr))

    # Re-sync HP: the engine reads `piece.max_hp`/`hp` as cached fields (not via
    # compute_stat), so an `hp` mul modifier only bites if we recompute here.
    # Pieces start each combat at full HP (matches weather behaviour).
    for piece in team:
        new_hp = piece.stat("hp")
        piece.max_hp = new_hp
        piece.hp = new_hp

    return activations
