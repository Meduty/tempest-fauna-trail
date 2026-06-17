# Items

> **Status: LIVING** — must match `src/game/items/`. Audited by `/check`.
> **Scope:** pointer — item content lives in code + the system doc. **Reconciled:** 2026-06-16 (T.29a-d).
>
> ✅ **SHIPPED (T.29a-d)** — the item engine is built: 8 components + 16 core +
> 20 combined + 6 emblems = **50** in `ITEM_REGISTRY`, plus **5** special
> run-actions in `RUN_ACTION_REGISTRY`. Mana primitive (V.48) + multi-slot (V.49)
> landed in T.29c/d.

This content doc is a thin pointer; the real material lives in:

- **How the engine works** → [`docs/live/systems/items.md`](../systems/items.md)
  (package layout, components, recipes, equip, reward drops, mana items).
- **The data** → `src/game/items/` (`base.py`, `combined.py`, `emblems.py`,
  `special.py`, `recipes.py`); ids/counts are `/check`-verified against
  `ITEM_REGISTRY` / `RUN_ACTION_REGISTRY`.
- **As-designed lore + intent** (frozen) → `docs/design/content/item_catalog.md`.
- **Build rationale** (frozen) → `docs/design/tasks/t29_item_engine_plan.md`.
