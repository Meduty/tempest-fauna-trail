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

## Descriptions (T.41a) — `game/items/meta.py` + `game/describe.py`

Player-facing item text flows through the shared description render-layer:

- **`items/meta.py::ITEM_META: dict[str, ItemMeta]`** — authored **name + blurb**
  for **all 50** `ITEM_REGISTRY` ids (transcribed from the frozen
  `item_catalog.md`). `set(ITEM_META) == set(ITEM_REGISTRY)` is test-guarded (V.78).
  The blurb is *effect/flavor prose only* — no stat numbers.
- **`describe.render_item(id) -> RenderedEntry(name, text, stat_line)`** — the
  **stat line is derived by introspecting the item's `EffectBundle`** (the
  registered factory built with a null owner; `Modifier` mul→`+12% STR`, add→flat,
  crit/pen%→percentage). The number shown is exactly the number combat applies and
  cannot drift (V.78); rendering has no side effect (V.80).
- **Consumer:** the Prep item chips (`ui/views/prep.py::_item_chip`) show the
  rendered name + a tooltip (name · stat line — blurb · kind/action hint), replacing
  the old Title-case `_item_label` stopgap. (Trait descriptions: T.41b.)
