"""Item equip seam (T.23b) — move items between `Run.inventory` and a champion.

Pure game logic (V.1, no Flet, no I/O): the Prep view equips/unequips through
**these** functions only — it never mutates `Champion.items` / `Run.inventory`
inline (V.63). Equipping **auto-combines on double-equip**: if the champion
already holds a component that pairs with the incoming item into a recipe
(`items.combine`), the two fuse into the combined item in a single slot;
otherwise the item takes a free slot (≤3, the `Champion` cap). Deterministic —
the combine partner is the **first** held item that pairs (no RNG, V.2).
"""

from __future__ import annotations

from src.game.items import combine
from src.game.models import Champion, Run

MAX_ITEMS = 3  # mirrors the Champion.items invariant (models.py:163, V.23)


def _inv_take(run: Run, item_id: str) -> bool:
    """Remove one `item_id` from inventory; False if none held."""
    have = run.inventory.get(item_id, 0)
    if have <= 0:
        return False
    if have == 1:
        del run.inventory[item_id]
    else:
        run.inventory[item_id] = have - 1
    return True


def _inv_give(run: Run, item_id: str) -> None:
    run.inventory[item_id] = run.inventory.get(item_id, 0) + 1


def equip_item(run: Run, champion: Champion, item_id: str) -> bool:
    """Equip one `item_id` from ``run.inventory`` onto ``champion`` (T.23b).

    Auto-combines on double-equip (the new item + a held component that form a
    recipe → the combined item, one slot). Otherwise fills a free slot (≤3).
    Consumes the inventory entry. Returns ``False`` (no mutation) if the item
    isn't in inventory or there's no room and no combine.
    """
    if run.inventory.get(item_id, 0) <= 0:
        return False
    # Auto-combine with the first held item that pairs into a recipe.
    for i, held in enumerate(champion.items):
        combined = combine(held, item_id)
        if combined is not None:
            champion.items[i] = combined
            _inv_take(run, item_id)
            return True
    # Plain equip into a free slot.
    if len(champion.items) >= MAX_ITEMS:
        return False
    champion.items.append(item_id)
    _inv_take(run, item_id)
    return True


def unequip_item(run: Run, champion: Champion, item_id: str) -> bool:
    """Unequip one `item_id` from ``champion`` back into ``run.inventory``.

    Combined items return whole (no de-combine). Returns ``False`` if the
    champion isn't holding ``item_id``.
    """
    if item_id not in champion.items:
        return False
    champion.items.remove(item_id)
    _inv_give(run, item_id)
    return True
