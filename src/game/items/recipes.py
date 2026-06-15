"""Item recipe map (T.29a).

RECIPE_MAP holds all 36 pairings (8 same-component + 28 cross-component) keyed
by a frozenset of two component IDs.  Same-component recipes use a single-element
frozenset because ``frozenset({"fang","fang"}) == frozenset({"fang"})``.

combine(a, b) is the public API:
  - Returns the combined-item id for two components, or None if unknown.
  - Spirit-Gem + base component → that component's Kinship emblem (T.29b).
"""

from __future__ import annotations

from src.game.items.base import BASE_COMPONENTS, SPIRIT_GEM, kinship_of

# ---------------------------------------------------------------------------
# Full 8×8 recipe matrix — 36 entries
# ---------------------------------------------------------------------------

#: frozenset({component_a, component_b}) -> combined_item_id
RECIPE_MAP: dict[frozenset[str], str] = {
    # --- Same-component recipes (8, single-element frozensets) ---
    frozenset({"fang"}):        "apex_fang",
    frozenset({"talon"}):       "tempest_talons",
    frozenset({"heartseed"}):   "worldroot_bloom",
    frozenset({"springtear"}):  "deepwell",
    frozenset({"old_hide"}):    "mammoth_hide",
    frozenset({"stoneplate"}):  "bramble_carapace",
    frozenset({"wardpelt"}):    "mistward_shroud",
    frozenset({"keen_claw"}):   "perfect_predator",

    # --- Cross-component recipes (28) ---
    frozenset({"fang", "talon"}):       "huntress_talon",
    frozenset({"fang", "heartseed"}):   "bloodthorn_briar",
    frozenset({"fang", "springtear"}):  "relentless_spear",
    frozenset({"fang", "old_hide"}):    "titanbone_charm",
    frozenset({"fang", "stoneplate"}):  "beastheart_gauntlet",
    frozenset({"fang", "wardpelt"}):    "twinclaw_pact",
    frozenset({"fang", "keen_claw"}):   "giantsbane",

    frozenset({"talon", "heartseed"}):  "wildfury_lash",
    frozenset({"talon", "springtear"}): "stormscale_quiver",
    frozenset({"talon", "old_hide"}):   "quickpelt_harness",
    frozenset({"talon", "stoneplate"}): "sundertalon",
    frozenset({"talon", "wardpelt"}):   "splitwind_talons",
    frozenset({"talon", "keen_claw"}):  "stalkerclaw",

    frozenset({"heartseed", "springtear"}): "everbloom_staff",
    frozenset({"heartseed", "old_hide"}):   "witherbloom_censer",
    frozenset({"heartseed", "stoneplate"}): "stoneward_idol",
    frozenset({"heartseed", "wardpelt"}):   "stormglass_totem",
    frozenset({"heartseed", "keen_claw"}):  "spellfang_crown",

    frozenset({"springtear", "old_hide"}):    "sapwood_aegis",
    frozenset({"springtear", "stoneplate"}):  "wardens_dewstone",
    frozenset({"springtear", "wardpelt"}):    "seasonward_charm",
    frozenset({"springtear", "keen_claw"}):   "dewclaw_fetish",

    frozenset({"old_hide", "stoneplate"}): "living_bulwark",
    frozenset({"old_hide", "wardpelt"}):   "spiritbark_hide",
    frozenset({"old_hide", "keen_claw"}):  "gorehide_wrap",

    frozenset({"stoneplate", "wardpelt"}): "greatward_carapace",
    frozenset({"stoneplate", "keen_claw"}): "edge_of_stone",

    frozenset({"wardpelt", "keen_claw"}):  "hexward_claw",
}


def combine(a: str, b: str) -> str | None:
    """Return the combined-item id for two components, or None if unknown.

    Same-component pairs (a == b) resolve via the single-element frozenset
    key. A Spirit Gem paired with a base component returns that component's
    Kinship emblem (T.29b).
    """
    if SPIRIT_GEM in (a, b):
        # T.29b: Spirit-Gem + base component → that component's Kinship emblem.
        other = b if a == SPIRIT_GEM else a
        kinship = kinship_of(other)
        return f"{kinship.lower()}_emblem" if kinship else None

    # Check both inputs are base components (unknown inputs → None)
    if a not in BASE_COMPONENTS or b not in BASE_COMPONENTS:
        return None

    return RECIPE_MAP.get(frozenset({a, b}))
