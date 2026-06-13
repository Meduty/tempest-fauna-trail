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
| `fang` | +20 STR |
| `keen_claw` | +20 INT |
| `talon` | +8% AS (`milli_AS` paired) |
| `wardpelt` | +30 ARM |
| `stoneplate` | +30 MR |
| `old_hide` | +200 HP |
| `heartseed` | +10 HP regen/tick (via `on_tick` hook) |
| `springtear` | `on_combat_start` hook: `slot.cost -= 10` (mana efficiency) |

`springtear` uses `on_combat_start` (not a stat modifier) because mana lives on
`ActiveSlot.cost`, not in `Piece.base_stats`.

### Combined items (16-core cut)

| ID | Components | Key effects |
|---|---|---|
| `apex_fang` | fang + fang | +50 STR, on-hit bonus STR% damage (cadence every 3 autos) |
| `tempest_talons` | fang + talon | +20 STR, +12% AS; on-kill reset attack timer |
| `deepwell` | keen_claw + springtear | +20 INT; `slot.cost -= 20`, bonus current mana |
| `mammoth_hide` | old_hide + stoneplate | +400 HP, +40 MR; once/combat barrier at 50% HP |
| `bramble_carapace` | wardpelt + stoneplate | +60 ARM, +30 MR; reflects % melee damage |
| `mistward_shroud` | wardpelt + wardpelt | +80 ARM; `hexproof` flag on `on_combat_start` |
| `perfect_predator` | fang + wardpelt | +30 STR, +40 ARM; on-kill +temp STR (3-tick decay) |
| `bloodthorn_briar` | talon + old_hide | +12% AS, +150 HP; on-hit leech (5% max HP) |
| `wildfury_lash` | talon + talon | +24% AS; every 4th auto deals +50% bonus damage |
| `everbloom_staff` | heartseed + keen_claw | +20 INT, +8 HP regen; `on_cast`: AoE heal allies (INT×0.4) |
| `witherbloom_censer` | keen_claw + wardpelt | +30 INT, +30 ARM; `on_cast`: apply FRAIL to one target |
| `stormglass_totem` | stoneplate + springtear | +40 MR; `on_combat_start`: reduce all enemy MR by 10 |
| `spellfang_crown` | heartseed + keen_claw | +20 INT, +8 crit chance; `on_combat_start` sets `owner.ability_can_crit = True` |
| `splitwind_talons` | talon + wardpelt | +10% AS, +20 ARM; `on_damage_dealt` if ITEM_PROC: noop (debuff hook) |
| `worldroot_bloom` | heartseed + old_hide | +300 HP, +12 HP regen; `on_tick` HoT + extra pulse every 5 ticks |
| `living_bulwark` | old_hide + wardpelt | +250 HP, +50 ARM; no hooks |

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
