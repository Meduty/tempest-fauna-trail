# Items — engine, components, combined, equip, reward drops

> **Status: LIVING** — must match `src/game/items/`, `src/game/loadout.py`,
> `src/game/models.py`, `src/game/encounter.py`, `src/game/registries.py`.
> Audited by `/check`. **Last reconciled: 2026-06-16** (T.29a-d complete —
> components, combined, emblems, special run-actions, mana primitive, multi-slot).
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
  combined.py     — @register_item factories: 8 raw components + 16 core + 20
                    combined (T.29b) = 44 in ITEM_REGISTRY
  emblems.py      — 6 Kinship emblems (T.29b; ITEM_REGISTRY total = 50)
  special.py      — 5 RUN_ACTION_REGISTRY special items (T.29b, operate on Run)
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
- `spirit_gem` is **not** in `BASE_COMPONENTS`; it is a separate special-item.
  `combine("spirit_gem", c)` returns `c`'s emblem (`base.KINSHIP_OF`) — 6 mapped
  components craft emblems; `wardpelt`/`keen_claw` → `None` (T.29b).

```python
def combine(a: str, b: str) -> str | None:
```
Returns the combined item ID or `None` if no recipe exists.

## Prep equip seam (`game/inventory.py`, T.23b)

The Prep view moves items between `Run.inventory` and `Champion.items` **only**
through `game/inventory.py` (V.63 — never inline):

- `equip_item(run, champion, item_id) -> bool` — consumes one from inventory onto
  the champion. **Auto-combines on double-equip:** if the champion already holds a
  component that pairs with `item_id` into a recipe (`items.combine`), the two fuse
  into the combined item in a single slot (works even at the 3-item cap); otherwise
  the item takes a free slot (≤3, the `Champion` cap). The combine partner is the
  **first** held item that pairs — deterministic, no RNG (V.2).
- `unequip_item(run, champion, item_id) -> bool` — returns the item whole to
  inventory (no de-combine).

## Equip pipeline (combat-side)

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
- **`hooks`**: `list[Hook]` — each `Hook(event_name, fn, scope)` is registered on
  the EventBus; closures capturing `owner: Piece` for
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
| `springtear` | ×1.15 `mana_regen` (Modifier) + `on_combat_start` hook: +100_000 flat starting mana (≈1/3 of default cost, V.48) |

`springtear` grants `mana_regen` (the cast-rate knob) plus `start_mana` via an
`on_combat_start` hook (mana is per-`ActiveSlot`, not in `Piece.base_stats`).
**Mana items NEVER reduce `mana_cost`** (V.48, T.29c — kills negative-cost
stacking, B.21); they grant `mana_regen` or `start_mana` only.

All modifiers use `"mul"` (multiplicative) or `"add"` (additive) operation via
`Modifier(stat, op, delta, Lifetime.COMBAT, source)`. The multipliers in the
factories represent the scale factor (e.g. `1.12` = ×1.12 the base stat).

### Combined items (16-core cut)

| ID | Components | Key effects |
|---|---|---|
| `apex_fang` | fang + fang | ×1.24 STR; on-kill grants +5% of current STR (compounding add) |
| `tempest_talons` | talon + talon | ×1.24 AS; each auto-hit adds +0.5% of current AS (compounding ramp) |
| `worldroot_bloom` | heartseed + heartseed | ×1.30 INT (pure stat stick) |
| `deepwell` | springtear + springtear | ×1.30 `mana_regen` + +200_000 flat starting mana; combat-start barrier (15% holder max HP) on lowest-HP ally (support); after first cast, refunds 50% `mana_cost` (clamp `max_mana`) per cast (V.48) |
| `mammoth_hide` | old_hide + old_hide | ×1.24 HP; every 2 s heals holder + adjacent allies 2% max HP (team regen aura ≈1%/s, ungated) |
| `bramble_carapace` | stoneplate + stoneplate | ×1.28 Armor; flat 80 magic retaliate + `grievous` (halved healing, 2 s) to melee attackers (thorns, flat by design) |
| `mistward_shroud` | wardpelt + wardpelt | ×1.28 RES; regenerates 1% max HP every second (self only) |
| `perfect_predator` | keen_claw + keen_claw | +30% crit chance; critical hits deal +25% bonus damage (ITEM_PROC) |
| `bloodthorn_briar` | fang + heartseed | ×1.12 STR, ×1.12 INT; heals holder for 18% of all damage dealt |
| `wildfury_lash` | talon + heartseed | ×1.12 AS, ×1.12 INT; each auto adds +1% current AS; every 5th auto triggers a free cast |
| `everbloom_staff` | heartseed + springtear | ×1.12 INT, ×1.15 `mana_regen`, +100_000 flat starting mana; INT grows +1% per 2 s while alive (V.48) |
| `witherbloom_censer` | heartseed + old_hide | ×1.12 INT, ×1.12 HP; autos apply burn (3 s) + RES ×0.80 sunder + `grievous` (halved healing) (single refreshing instances) |
| `stormglass_totem` | heartseed + wardpelt | ×1.12 INT, ×1.14 RES; when a nearby enemy casts (radius 5), zaps them for INT×0.50 magic damage |
| `spellfang_crown` | heartseed + keen_claw | ×1.12 INT, +15% crit chance; abilities can crit (`ability_can_crit` set on `on_combat_start`) |
| `living_bulwark` | old_hide + stoneplate | ×1.12 HP, ×1.14 Armor; combat-start +18% Armor aura to adjacent allies (support anchor) |
| `splitwind_talons` | talon + wardpelt | ×1.12 AS, ×1.14 RES; each auto strikes nearest second enemy within range 2 for 50% dmg + applies Slow (soft CC) to both |

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
    item_ids: list[str]

def generate_reward_loot(run_seed: int, node_index: int) -> RewardLoot:
```

Deterministic drop table (derives from `(run_seed, node_index, CH_REWARD)`):

| Roll | Probability | Outcome |
|---|---|---|
| < 0.60 | 60% | 1 base component |
| < 0.85 | 25% | 1 core combined item |
| else | 15% | 2 base components |

All item IDs returned are guaranteed members of `BASE_COMPONENTS ∪ ITEM_REGISTRY`.

## Combined items (remaining 20 — T.29b)

`combined.py` (T.29b block). Hook items use the closure/cadence/`secs()` patterns;
all magnitudes first-pass, judged against combat scale (autos ~5 s, HP 600–1500).

| ID | Components | Key effects |
|---|---|---|
| `huntress_talon` | fang + talon | +12% STR/AS; autos apply stacking poison (3 s) |
| `relentless_spear` | fang + springtear | +12% STR, +15% MR; +30k mana per auto |
| `titanbone_charm` | fang + old_hide | +12% STR/HP; +0.4% STR per attack/hit, barrier (15% HP) at 12 stacks |
| `beastheart_gauntlet` | fang + stoneplate | +12% STR, +14% Armor; barrier (25% HP) first time below 35% |
| `twinclaw_pact` | fang + wardpelt | +12% STR, +14% RES; alternates +50% bonus hit / 30% heal |
| `giantsbane` | fang + keen_claw | +12% STR, +15% Crit; autos +4% target max HP magic (anti-tank) |
| `stormscale_quiver` | talon + springtear | +12% AS, +15% MR; every 4th auto chains lightning to ≤3 enemies |
| `quickpelt_harness` | talon + old_hide | +12% AS/HP; first hard-CC → cleanse + 3 s CC-immune |
| `sundertalon` | talon + stoneplate | +12% AS, +14% Armor; autos shred target Armor ×0.82 (3 s) |
| `stalkerclaw` | talon + keen_claw | +14% AS, +15% Crit (clean crit stat stick) |
| `stoneward_idol` | heartseed + stoneplate | +14% INT, +16% Armor (durable backline caster) |
| `sapwood_aegis` | springtear + old_hide | +15% MR, +12% HP; start shield (20% HP) → INT burst on break |
| `wardens_dewstone` | springtear + stoneplate | +15% MR, +14% Armor; +15% MR aura to adjacent allies |
| `seasonward_charm` | springtear + wardpelt | +15% MR, +14% RES; adaptive +20% Armor/RES vs recent damage type |
| `dewclaw_fetish` | springtear + keen_claw | +15% MR, +15% Crit (cast-cycling crit carry) |
| `spiritbark_hide` | old_hide + wardpelt | +12% HP, +16% RES (anti-magic brick) |
| `gorehide_wrap` | old_hide + keen_claw | +14% HP, +15% Crit (fragile crit carry survivability) |
| `greatward_carapace` | stoneplate + wardpelt | +14% Armor/RES; +4% Armor & RES per living enemy at start |
| `edge_of_stone` | stoneplate + keen_claw | +16% Armor, +15% Crit (bruiser-carry hybrid) |
| `hexward_claw` | wardpelt + keen_claw | +16% RES, +15% Crit (crit that survives magic burst) |

## Emblems (6 — emblems.py, T.29b)

Each carries `granted_traits=["<Kinship>"]` + an 8% flavour stat; applied at the
item step (§10.1 step 2.5) **before** `_resolve_traits`, so the wearer counts
toward that Kinship breakpoint. Crafted via `combine(spirit_gem, component)`.

| Emblem | Kinship | Stat | Crafted from |
|---|---|---|---|
| `beast_emblem` | Beast | +8% STR | spirit_gem + fang |
| `skyborn_emblem` | Skyborn | +8% AS | spirit_gem + talon |
| `scaled_emblem` | Scaled | +8% Armor | spirit_gem + stoneplate |
| `tidekin_emblem` | Tidekin | +8% MR | spirit_gem + springtear |
| `swarm_emblem` | Swarm | +8% HP | spirit_gem + old_hide |
| `spirit_emblem` | Spirit | +8% INT | spirit_gem + heartseed |

## Special items — run-actions (special.py, T.29b)

Never enter combat (V.24) — `RUN_ACTION_REGISTRY`, operate on `Run` only. Spirit
Gem is the 6th special, handled inline by `combine()` (crafting, not a run-action).

| Run-action | id | Effect on `Run` |
|---|---|---|
| Wildwood Reforging Stone | `reforger` | Swap one component of a combined item (deterministic next) + recombine |
| Unbinding Totem | `unbinding_totem` | Strip a champ's items → bench inventory, decomposed to components |
| Echo Acorn | `echo_acorn` | Add a bench copy of a champion (+`champion_copies`, T.22 levelling) |
| Glimmerdust | `glimmerdust` | Upgrade item → `heartwood:` version (D.21 MVP: ×1.5 modifiers at equip) |
| Reclaimer's Cache | `reclaimers_cache` | Salvage base components → 10 Amber each |

Heartwood (`heartwood:<id>`) is scaled at equip by `loadout._heartwood_scale`
(mul/add modifiers ×1.5; hooks/procs untouched — D.21 MVP). `decompose()` reverses
any item to base components (used by unbind/reforge).

**CLI:** `sim_run --interactive` opens a prep shell (`combine`/`equip`/`reforge`/
`unbind`/`echo`/`glimmer`/`salvage`) over a Run before the route walk.
