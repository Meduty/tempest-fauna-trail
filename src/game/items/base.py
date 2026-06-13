"""Item base definitions (T.29a).

Defines the component vocabulary: the 8 raw component IDs and the Spirit Gem
special-item ID (emblem-maker, T.29b). All combat-facing item factories live in
combined.py and register via @register_item.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Component vocabulary
# ---------------------------------------------------------------------------

# The 8 base component IDs.  These are equippable raw (pure-modifier bundle)
# and are the inputs to RECIPE_MAP.
BASE_COMPONENTS: frozenset[str] = frozenset({
    "fang",
    "talon",
    "heartseed",
    "springtear",
    "old_hide",
    "stoneplate",
    "wardpelt",
    "keen_claw",
})

# Spirit Gem — special item that combines with a base component to craft an
# emblem (T.29b).  Not a base component itself.
SPIRIT_GEM: str = "spirit_gem"
