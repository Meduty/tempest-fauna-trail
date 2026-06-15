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

# Component → Kinship granted when crafted with a Spirit Gem into an emblem
# (T.29b §3.5). Six of the eight components map (one per Kinship); the small stat
# the emblem grants is flavoured by that component. `wardpelt`/`keen_claw` craft
# no emblem (combine → None). The crafted item id is f"{kinship.lower()}_emblem".
KINSHIP_OF: dict[str, str] = {
    "fang": "Beast",
    "talon": "Skyborn",
    "stoneplate": "Scaled",
    "springtear": "Tidekin",
    "old_hide": "Swarm",
    "heartseed": "Spirit",
}


def kinship_of(component: str) -> str | None:
    """Kinship an emblem grants when `component` is fused with a Spirit Gem."""
    return KINSHIP_OF.get(component)
