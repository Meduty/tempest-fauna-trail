# Items — engine, components, combined, equip, reward drops

> **Status: LIVING** — must match `src/game/items/`, `src/game/loadout.py`,
> `src/game/models.py`, `src/game/encounter.py`, `src/game/registries.py`.
> Audited by `/check`. **Last reconciled: 2026-06-13** (T.29a complete).
>
> Design rationale (frozen): `docs/design/tasks/t29_item_engine_plan.md`.
> Content roster (frozen): `docs/design/content/item_catalog.md`.

## Package layout

```
src/game/items/
  __init__.py     — re-exports BASE_COMPONENTS, SPIRIT_GEM, RECIPE_MAP, combine;
                    importing this module triggers all @register_item side-effects
  base.py         — BASE_COMPONENTS: frozenset[str] (8 component IDs), SPIRIT_GEM
  recipes.py      — RECIPE_MAP: dict[frozenset[str], str] (36 entries), combine()
  combined.py     — @register_item factories for 8 raw components + 16 core items
```

`ITEM_REGISTRY` (in `src/game/registries.py`) maps `item_id → Callable[[Piece], EffectBundle]`.

## Data structures

### Champion.items (models.py)

```python
@dataclass
class Champion:
    items: list[str] = field(default_factory=list)   # ≤3 item IDs, validated
```

Invariants (V.23):
- Length ≤ 3 (validated in `Champion.__post_init__`).
- Every string is non-empty.
- Items persist across combats on the `Champion`; each combat rebuilds from scratch.

### RECIPE_MAP (recipes.py)

A `dict[frozenset[str], str]` mapping a pair (or singleton, for same-component
recipes) of component IDs to the combined item ID.

- 36 entries total (8×8 upper triangle + diagonal).
- Same-component recipes use a **single-element frozenset** because
  `frozenset({"fang", "fang"}) == frozenset({"fang"})`.
- `spirit_gem` sits in `BASE_COMPONENTS` but its outbound recipes are stubbed
  `None` (T.29b).

```python
def combine(a: str, b: str) -> str | None:
```
Returns the combined item ID or `None` if no recipe exists.

## Equip pipeline

`compile_loadout` (loadout.py) applies items at **step 2.5** — after weather
modifiers (step 2) but before trait resolution (step 3).

```
step 1: compose_stats
step 2: weather modifiers
step 2.5: item bundles      ← NEW (T.29a)
step 3: trait resolution
...
```

Flow:
1. `piece_from_champion` copies `champion.items → piece.items` (Piece.items is a
   `list[str]`; defaults to `[]`).
2. At step 2.5, `compile_loadout` imports `src.game.items` (triggers registry
   population) then iterates `piece.items`; for each item ID calls
   `ITEM_REGISTRY[item_id](piece)` → `EffectBundle`, then `apply_bundle(piece, bundle)`.
3. Modifiers from item bundles use `Lifetime.COMBAT` (pieces are rebuilt each
   combat — no cross-combat accumulation).

Enemies carry **no items**; `piece_from_enemy` is unchanged.

## Item factories (@register_item)

Each factory in `combined.py` is a `Callable[[Piece], EffectBundle]` registered
via `@register_item(item_id)`. A factory returns an `EffectBundle` containing:
- **`modifiers`**: flat stat deltas (`Modifier(stat, delta, Lifetime.COMBAT)`).
- **`hooks`**: `{event_name: [hook_fn]}` — closures capturing `owner: Piece` for
  per-instance state (one-shot flags, cadence counters).

### Raw components (8)

| ID | Grants |
|---|---|
| `fang` | +12% STR (multiply) |
| `keen_claw` | +15% crit chance (additive) |
| `talon` | +12% AS (`attack_speed` + `milli_AS` paired) |
| `wardpelt` | +14% MR |
| `stoneplate` | +14% Armor |
| `old_hide` | +12% HP |
| `heartseed` | +12% INT |
| `springtear` | `on_combat_start` hook: +200 starting mana, −10% cast cost (`slot.cost *= 0.9`) |

`springtear` uses `on_combat_start` (not a stat modifier) because mana lives on
`ActiveSlot.cost`, not in `Piece.base_stats`.

All modifiers use `"mul"` (multiplicative) or `"add"` (additive) operation via
`Modifier(stat, op, delta, Lifetime.COMBAT, source)`. The multipliers in the
factories represent the scale factor (e.g. `1.12` = ×1.12 the base stat).

### Combined items (16-core cut)

| ID | Components | Key effects |
|---|---|---|
| `apex_fang` | fang + fang | ×1.24 STR; on-hit +STR×0.25 bonus damage every 3 autos (cadence counter) |
| `tempest_talons` | fang + talon | ×1.12 STR + ×1.12 AS; on-kill reset attack timer |
| `deepwell` | keen_claw + springtear | ×1.12 INT; `slot.cost -= 20` + fill starting mana to 300 |
| `mammoth_hide` | old_hide + stoneplate | ×1.24 HP, ×1.28 Armor; once/combat barrier at 50% HP |
| `bramble_carapace` | wardpelt + stoneplate | ×1.28 Armor, ×1.14 MR; reflects 25% melee damage (ITEM_PROC) |
| `mistward_shroud` | wardpelt + wardpelt | ×1.28 MR; sets `piece.hexproof = True` on `on_combat_start` |
| `perfect_predator` | fang + wardpelt | +30% crit chance; on-kill temp STR buff (3-tick decay via Modifier) |
| `bloodthorn_briar` | talon + old_hide | ×1.12 AS, ×1.12 HP; on-hit lifesteal (5% of max HP) |
| `wildfury_lash` | talon + talon | ×1.12 AS, ×1.12 INT; every 4th auto deals +50% bonus damage |
| `everbloom_staff` | heartseed + springtear | ×1.12 INT; +200 mana; `on_cast` AoE heals all allies (INT×0.4) |
| `witherbloom_censer` | keen_claw + wardpelt | ×1.12 INT, ×1.14 MR; `on_cast` applies FRAIL to one target |
| `stormglass_totem` | stoneplate + springtear | ×1.14 Armor; `on_combat_start` reduces all enemy MR by 10 (flat) |
| `spellfang_crown` | heartseed + keen_claw | ×1.12 INT, +15% crit chance; `on_combat_start` sets `owner.ability_can_crit = True` |
| `splitwind_talons` | talon + wardpelt | ×1.12 AS, ×1.14 MR; `on_attack_landed`: second-hit on nearest other enemy (50% damage) |
| `worldroot_bloom` | heartseed + old_hide | ×1.30 INT; `on_tick` HoT (INT×0.1) + extra pulse every 5 ticks |
| `living_bulwark` | old_hide + wardpelt | ×1.12 HP, ×1.14 MR; no hooks |

**Hook guards:** `on_damage_dealt` hooks check `ev.tag == SourceTag.ITEM_PROC` to
avoid triggering on bonus damage from the same item (preventing infinite loops).

**`ability_can_crit`** is set in an `on_combat_start` hook (matching the
`ability_crit()` idiom in `traits/mechanics.py:268–273`).

**`milli_AS`** pairing: every item that modifies `attack_speed` also modifies
`milli_AS` (V.34 / sort-order invariant).

## REWARD-node drops (encounter.py)

```python
CH_REWARD: Final[int] = 8   # seed channel for reward loot

@dataclass
class RewardLoot:
    items: list[str]

def generate_reward_loot(run_seed: int, node_index: int) -> RewardLoot:
```

Deterministic drop table (derives from `(run_seed, node_index, CH_REWARD)`):

| Roll | Probability | Outcome |
|---|---|---|
| < 0.60 | 60% | 1 base component |
| < 0.85 | 25% | 1 core combined item |
| else | 15% | 2 base components |

All item IDs returned are guaranteed members of `BASE_COMPONENTS ∪ ITEM_REGISTRY`.

## T.29b stubs (not yet implemented)

- `spirit_gem` outbound recipes (`combine("spirit_gem", x)`) return `None`.
- Emblems (`granted_traits`) — T.29b.
- `RUN_ACTION_REGISTRY` special items — T.29b.
- Remaining 20 combined items — T.29b.
