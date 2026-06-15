"""Item system public API (T.29a).

Importing this package triggers all @register_item decorators in combined.py,
populating ITEM_REGISTRY in src.game.registries.

Public re-exports:
  BASE_COMPONENTS — frozenset of the 8 raw component IDs
  SPIRIT_GEM      — "spirit_gem" special-item ID (emblem-maker, T.29b)
  RECIPE_MAP      — frozenset→item_id dict (36 entries)
  combine         — combine(a, b) -> str | None
"""

from __future__ import annotations

from src.game.items.base import BASE_COMPONENTS, SPIRIT_GEM, KINSHIP_OF, kinship_of
from src.game.items.recipes import RECIPE_MAP, combine
import src.game.items.combined  # noqa: F401 — side-effect: populates ITEM_REGISTRY
import src.game.items.emblems   # noqa: F401 — side-effect: registers 6 emblems
import src.game.items.special   # noqa: F401 — side-effect: registers run-actions

__all__ = [
    "BASE_COMPONENTS",
    "SPIRIT_GEM",
    "KINSHIP_OF",
    "kinship_of",
    "RECIPE_MAP",
    "combine",
]
