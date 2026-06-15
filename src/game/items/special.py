"""Special-item run-actions (T.29b §3.6 / effect_systems_design §8.4).

Special items never enter combat (V.24) — they have no `EffectBundle` and act on
`Run` state (inventory / bench / roster / amber). Registered in
`RUN_ACTION_REGISTRY`, never referenced from `game/combat/`.

Six special items: five run-actions here + **Spirit Gem**, which is the
emblem-maker handled inline by `recipes.combine()` (crafting, not a run-action).

Determinism (V.2/V.14): no RNG — choices are deterministic (sorted order).
"""

from __future__ import annotations

from typing import Any

from src.game.items.base import BASE_COMPONENTS, SPIRIT_GEM, KINSHIP_OF
from src.game.items.recipes import RECIPE_MAP, combine
from src.game.registries import register_run_action

HEARTWOOD_PREFIX = "heartwood:"   # Glimmerdust-upgraded item id (D.21 MVP ×1.5)
SALVAGE_VALUE = 10                # Amber per base component (Reclaimer's Cache)

# Reverse recipe: combined item id -> the two component ids that craft it.
_REVERSE_RECIPE: dict[str, tuple[str, ...]] = {
    item_id: tuple(sorted(components)) for components, item_id in RECIPE_MAP.items()
}
# Emblem item id -> the component that (with a Spirit Gem) crafts it.
_EMBLEM_COMPONENT: dict[str, str] = {
    f"{kin.lower()}_emblem": comp for comp, kin in KINSHIP_OF.items()
}


# --- inventory helpers -------------------------------------------------------

def _inv_add(run: Any, item_id: str, n: int = 1) -> None:
    run.inventory[item_id] = run.inventory.get(item_id, 0) + n


def _inv_remove(run: Any, item_id: str, n: int = 1) -> bool:
    """Remove n of item_id from inventory; return False if not enough."""
    have = run.inventory.get(item_id, 0)
    if have < n:
        return False
    if have == n:
        del run.inventory[item_id]
    else:
        run.inventory[item_id] = have - n
    return True


def decompose(item_id: str) -> list[str]:
    """Break an item back into base components (for unbinding/reforge).

    base component → itself; combined → its two components; emblem →
    [spirit_gem, flavour-component]; heartwood-wrapped → decompose the base.
    """
    if item_id.startswith(HEARTWOOD_PREFIX):
        return decompose(item_id[len(HEARTWOOD_PREFIX):])
    if item_id in BASE_COMPONENTS:
        return [item_id]
    if item_id in _REVERSE_RECIPE:
        return list(_REVERSE_RECIPE[item_id])
    if item_id in _EMBLEM_COMPONENT:
        return [SPIRIT_GEM, _EMBLEM_COMPONENT[item_id]]
    return []


# --- run-actions -------------------------------------------------------------

@register_run_action("reforger")
def reforger(run: Any, item_id: str) -> None:
    """Wildwood Reforging Stone — swap one component of a combined item for a
    different one (deterministic: the lexicographically-next base component) and
    recombine. No-op if the item isn't a recombinable combined item in inventory.
    Same-component recipes (1-element tuple, e.g. apex_fang) have no second
    component to keep, so they are treated as non-reforgeable (no-op)."""
    comps = _REVERSE_RECIPE.get(item_id)
    if comps is None or len(comps) < 2 or run.inventory.get(item_id, 0) <= 0:
        return
    keep = comps[1]                       # keep the second, reforge the first
    ordered = sorted(BASE_COMPONENTS)
    old = comps[0]
    nxt = ordered[(ordered.index(old) + 1) % len(ordered)]
    if nxt == keep:                       # avoid same-pair collision
        nxt = ordered[(ordered.index(nxt) + 1) % len(ordered)]
    new_item = combine(keep, nxt)
    if new_item is None:
        return
    _inv_remove(run, item_id)
    _inv_add(run, new_item)


@register_run_action("unbinding_totem")
def unbinding_totem(run: Any, piece_id: str) -> None:
    """Unbinding Totem — strip every item off the champion and return them to the
    bench (inventory), decomposed to base components."""
    champ = next((c for c in (*run.roster, *run.bench) if c.id == piece_id), None)
    if champ is None:
        return
    for item_id in list(champ.items):
        for comp in decompose(item_id):
            _inv_add(run, comp)
    champ.items = []


@register_run_action("echo_acorn")
def echo_acorn(run: Any, champion_id: str) -> None:
    """Echo Acorn — add a fresh copy of the champion to the bench (feeds T.22
    levelling via champion_copies)."""
    from src.game.content import get_champion
    try:
        copy = get_champion(champion_id)
    except (KeyError, ValueError):
        return
    run.bench.append(copy)
    run.champion_copies[champion_id] = run.champion_copies.get(champion_id, 0) + 1


@register_run_action("glimmerdust")
def glimmerdust(run: Any, item_id: str) -> None:
    """Glimmerdust — upgrade a finished item into its Heartwood version (D.21 MVP:
    a generic ×1.5 on the item's modifiers, applied at equip via the
    `heartwood:` prefix). No-op on raw components or already-upgraded items."""
    if item_id.startswith(HEARTWOOD_PREFIX) or item_id in BASE_COMPONENTS:
        return
    if not _inv_remove(run, item_id):
        return
    _inv_add(run, HEARTWOOD_PREFIX + item_id)


@register_run_action("reclaimers_cache")
def reclaimers_cache(run: Any, component_ids: list[str]) -> None:
    """Reclaimer's Cache — salvage spare base components into Amber."""
    for comp in component_ids:
        if comp in BASE_COMPONENTS and _inv_remove(run, comp):
            run.amber += SALVAGE_VALUE
