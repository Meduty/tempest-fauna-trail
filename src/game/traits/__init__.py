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
    "affinity_trait",
    "resolve_and_apply_traits",
]

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
    team_pieces: list[Piece], board_cap: int
) -> dict[str, tuple[TraitBreakpoint, int, int]]:
    """Map each cleared trait → (breakpoint, unique-carrier count, threshold).

    Counts unique champion ids (V.21). Highest cleared rung wins. Dynamic
    thresholds are resolved against `(team_pieces, board_cap)`.
    """
    carriers: dict[str, set[str]] = defaultdict(set)
    for piece in team_pieces:
        for tag in _piece_tags(piece):
            carriers[tag].add(piece.id)

    cleared: dict[str, tuple[TraitBreakpoint, int, int]] = {}
    for tag, ids in carriers.items():
        factory = TRAIT_REGISTRY.get(tag)
        if factory is None:
            continue
        count = len(ids)
        best: TraitBreakpoint | None = None
        best_thr = -1
        for bp in factory():
            thr = bp.count(team_pieces, board_cap) if callable(bp.count) else bp.count
            if count >= thr and thr > best_thr:
                best, best_thr = bp, thr
        if best is not None:
            cleared[tag] = (best, count, best_thr)
    return cleared


def resolve_and_apply_traits(
    pieces: list[Piece], bus
) -> list[tuple[str, int, int]]:
    """Resolve + apply trait bundles to the player team; return activations.

    Player team only (enemies never light up — V.22). `board_cap` for dynamic
    thresholds is the fielded team size. Returns a sorted
    `[(trait_id, count, threshold), …]` for the `BattleResult` record.
    """
    from src.game.loadout import apply_bundle  # deferred: loadout imports this module

    team = [p for p in pieces if not p.is_enemy]
    board_cap = len(team)
    cleared = _resolve_traits(team, board_cap)

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
