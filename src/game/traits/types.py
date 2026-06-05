"""Trait framework types (T.28a).

A *trait* is a synergy tag (Kinship / Affinity / Calling) whose breakpoints grant
`EffectBundle`s when enough tag-sharing champions are fielded. See
`docs/design/content/trait_catalog.md` (v2.1) for the design.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Union

from src.game.effects import EffectBundle
from src.game.piece import Piece


class TraitScope(str, Enum):
    """Who a cleared breakpoint's bundle applies to."""

    PER_TRAIT_PIECE = "per_trait_piece"  # only pieces carrying the trait
    TEAM_WIDE = "team_wide"  # all player pieces


# A dynamic breakpoint threshold: resolved at loadout against the fielded board.
# Used by Packmate `@full-board` (threshold == number of champions fielded).
DynamicThreshold = Callable[[list[Piece], int], int]


@dataclass(frozen=True)
class TraitBreakpoint:
    """One rung of a trait ladder.

    `count` is the minimum unique-carrier count to clear the rung — an `int`, or a
    `DynamicThreshold` resolved against `(team_pieces, board_cap)` at loadout.
    `bundle_factory(piece)` builds the effect applied to each target piece.
    """

    count: Union[int, DynamicThreshold]
    scope: TraitScope
    bundle_factory: Callable[[Piece], EffectBundle]
