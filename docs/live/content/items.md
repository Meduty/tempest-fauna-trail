# Items

> **Status: LIVING** — must match `src/game/items/`. Audited by `/check`.
> **Scope:** content pointer — the item **engine** lives in the system doc; this
> doc holds the roster shape + counts + the description layer. **Reconciled:** 2026-07-01.
>
> ✅ **SHIPPED (T.29a–d)** — the item engine is built. `ITEM_REGISTRY` holds
> **50** combat items; `RUN_ACTION_REGISTRY` holds **5** special run-actions.
> Mana primitive (V.48) + multi-slot (V.49) landed in T.29c/d. Descriptions
> (T.41a) flow through the shared render-layer.

## Roster shape + counts (verified 2026-07-01 against the registries)

**`ITEM_REGISTRY` = 50** combat items (`id → Callable[[Piece], EffectBundle]`):

| Group | # | File | IDs |
|---|---|---|---|
| Base components | 8 | `base.py` (`BASE_COMPONENTS`) + factories in `combined.py` | `fang`, `talon`, `heartseed`, `springtear`, `old_hide`, `stoneplate`, `wardpelt`, `keen_claw` |
| Same-component combines | 8 | `combined.py` | e.g. `apex_fang` (fang+fang), `deepwell` (springtear+springtear) |
| Cross-component combines | 28 | `combined.py` | e.g. `bloodthorn_briar` (fang+heartseed), `splitwind_talons` (talon+wardpelt) |
| Kinship emblems | 6 | `emblems.py` | `beast/skyborn/scaled/tidekin/swarm/spirit_emblem` |

So `combined.py` registers **44** (8 raw + 16 core-cut + 20 T.29b combined) and
`emblems.py` adds **6** → 50. The 36 same+cross combines are keyed by
`RECIPE_MAP` (`recipes.py`); the 6 emblems are crafted via `combine(spirit_gem, c)`.

**`RUN_ACTION_REGISTRY` = 5** special run-actions (`special.py`) that never enter
combat (V.24): `reforger`, `unbinding_totem`, `echo_acorn`, `glimmerdust`,
`reclaimers_cache`. The 6th "special", **Spirit Gem** (`SPIRIT_GEM = "spirit_gem"`),
is the emblem-maker handled inline by `combine()` — crafting, not a run-action.

This is a content pointer; the real material lives in:

- **How the engine works** → [`docs/live/systems/items.md`](../systems/items.md)
  (package layout, components, recipes, equip, reward drops, mana items,
  the modifier+hook factory pattern).
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
  **stat line is derived by introspecting the item's `EffectBundle`**
  (`_bundle_stat_line`: the registered factory built with a **null owner**;
  `Modifier` `mul` → `+12% STR`, `add` → flat, crit/pen% → percentage). The number
  shown is exactly the number combat applies and cannot drift (V.78); rendering has
  no side effect (V.80). Hook-only riders carry no stat delta, so their effect
  reads from the blurb.
- **Consumer:** the Prep item chips (`ui/views/prep.py::_item_chip`) show the
  rendered name + a tooltip (name · stat line — blurb · kind/action hint), replacing
  the old Title-case `_item_label` stopgap. (Trait descriptions: T.41b.)
