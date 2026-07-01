# Encounter & board — squad generation, bosses, map effects

> **Status: LIVING** — must match `src/game/encounter.py`, `bosses/data.py`, `map_effects.py`, `board.py`. Audited by `/check`.
> **Scope:** seed-deterministic enemy/boss squad generation, difficulty, and the board-cell state combat reads. **Reconciled:** 2026-07-01.
>
> Citations by symbol, not line. Placement of the generated squad is [formation.md](formation.md). Design rationale (frozen): `docs/design/tasks/t19_*`, `t21_*`.

## Determinism — every roll derives from the seed

All procedural choices come from
`derive_seed(run_seed, node_index, channel) -> int` (V.2/V.14) — same
`(run_seed, node_index, channel)` → identical result. The derivation is
integer-only (no `hash()`, which is per-process salted):

```python
(run_seed * 2654435761 + node_index * 40503 + channel * 97) & 0xFFFFFFFF
```

The RNG is Python `Random` seeded from that derived value; there is no clock,
no global RNG, no external state. Each domain gets its own **channel** so rolls
never collide (e.g. the REWARD loot roll is independent of the squad roll):

| Channel const | # | Used by |
|---|---|---|
| `CH_ENEMIES` | 0 | `generate_fight` / `generate_reward` squad rolls |
| `CH_AUGMENT` | 1 | fresh augment offer (`augment_seed`, `reroll_count==0`) |
| `CH_SUPPLY` | 2 | supply-node champion offer (`supply_seed`) |
| `CH_REROLL` | 3 | first augment/supply reroll (`augment_seed` count `1`, strided for `≥2`) |
| `CH_CHALLENGE` | 4 | `generate_challenge` squad + reward |
| `CH_BOSS` | 5 | `generate_boss_encounter` variable adds |
| `CH_SHOP` | 6 | champion shop offers (`shop_seed`) |
| `CH_ECONOMY` | 7 | per-node Amber win bonus (`economy_seed`) |
| `CH_REWARD` | 8 | REWARD-node loot roll (`generate_reward_loot`) |

Per-domain seed helpers wrap `derive_seed` with the right channel (and, for
rerolls, a stride so successive rerolls stay distinct without colliding across
nodes/visits):

- `augment_seed(run_seed, node_index, reroll_count=0)` — `reroll_count` `0` →
  `CH_AUGMENT`; `1` → `CH_REROLL` (both **byte-identical to the pre-reroll
  channels**, no determinism re-baseline); `≥2` folds
  `node_index * AUGMENT_REROLL_STRIDE + reroll_count` into the node arg on
  `CH_REROLL` for awarded/banked rerolls (T.42a, V.84).
- `supply_seed(run_seed, node_index, rerolled=False)` — `CH_SUPPLY`, or
  `CH_REROLL` when `rerolled`.
- `shop_seed(run_seed, visit_index, reroll_count=0)` — folds
  `visit_index * SHOP_REROLL_STRIDE + reroll_count` into the node arg on
  `CH_SHOP` so each manual reroll within a visit is deterministic + distinct.
- `economy_seed(run_seed, node_index)` — `CH_ECONOMY`.

Both `*_REROLL_STRIDE` constants are `1000` — far above any realistic per-node
reroll count.

## Difficulty

`next_dc(current_dc) -> float` advances the difficulty coefficient (`×DC_STEP`,
`= 1.1`, rounded to 4 dp) from `DEFAULT_DC = 1.0`; `dc_name(dc)` labels it
(`"DC +0"`, `"DC +1"`, … from `round(log(dc)/log(1.1))`). The `dc` multiplier
scales the per-node power **budget** (`STAGE_BASE[stage] * dc * TYPE_MULT[...]`),
so a higher DC buys bigger/higher-level squads, not more of them.

Budget inputs (all `Final` dicts in `encounter.py`):
`STAGE_BASE` (per-stage power floor `3.5 … 65.0`), `TYPE_MULT`
(`fight 1.0` / `reward 0.5` / `challenge 1.3`), `STAGE_MAX_SQUAD`
(`4 … 10` cap), `LEVEL_WEIGHTS` + `PREFERRED_TIERS` (stage→tier/level curve
feeding `_tier_weight` / `_pick_level`).

## Squad generation

- `roll_squad(...)` — the core roller: weighted tier pick (`_tier_weight` by
  stage), level pick (`_pick_level`), affinity slotting (`_affinity_slots` by
  stage affinity), role-composition guard (`_check_composition` over
  `_is_tanky`/`_is_support`/`_is_dps`), via `_weighted_pick` over a
  `filter_pool` of `EnemyDef`s. Builds `Enemy` instances with `_instantiate_enemy`.
- `generate_fight(...)` — a standard fight encounter.
- `generate_reward(...)` — reward-node contents (enemy squad / supplies).
- `generate_reward_loot(run_seed, node_index) -> RewardLoot` — seed-deterministic
  item drop for REWARD nodes; uses channel `CH_REWARD = 8`. 60% one component,
  25% one core item, 15% two components. Added in T.29a. See [items.md](items.md).
- `generate_challenge(...)` — challenge nodes; can pull champion-derived enemies
  (`_champion_def_to_enemy`) and yields a `ChallengeReward`.
- `generate_boss_encounter(run_seed, node_index, stage) -> BossEncounterResult`
  — the boss squad + its map effect.
- `generate_node_reward(run_seed, node) -> NodeReward | None` (T.38, V.70) — the
  **single reward-payload source**, type-dispatched (mirrors `node_encounter`):
  **REWARD** → `generate_reward_loot` items; **CHALLENGE** → the
  `generate_challenge` reward (amber `2 × stage_index`, both components,
  `tempest_bonus`, `champion_offer`); **all other types** → `None`. Uses
  `node.weather` (the node's `default_weather`, not live API weather) so the
  payload is byte-identical to the reward `node_encounter` *discards* (the
  fight-build path stays squad-only; the resolve path `economy.apply_node_result`
  owns the reward). `NodeReward` fields → `Run.inventory` / `amber` / tempest /
  pending recruit. Applied **on win only** ⇒ a loss is structurally reward-zeroed.

## Per-node dispatch — one seam, two outputs

Two dataclass-returning entry points dispatch on `node.node_type` (`models.NodeType`)
so the Trail *preview* and the later Prep *fight* read the same seed:

- `node_encounter(run_seed, node, weather=None, dc=DEFAULT_DC) -> NodeEncounter`
  — the **squad** (and boss `map_effect_id`). FIGHT → `generate_fight`, REWARD →
  `generate_reward`, CHALLENGE → `generate_challenge` (squad only; `weather`
  defaults to `node.weather` and only steers CHALLENGE affinity), BOSS_FIGHT →
  `generate_boss_encounter().all_enemies`. **AUGMENT / SUPPLY → empty**
  `NodeEncounter([])` (no fight). Same `(run_seed, node, weather, dc)` ⇒ same
  squad (V.2/V.63) — the previewed squad is byte-identical to the one fought.
- `generate_node_reward(run_seed, node) -> NodeReward | None` (see below).

**Non-combat nodes** (AUGMENT / SUPPLY) never call combat: the node's *pick*
(augment / supply recruit) is applied by the view, then
`economy.resolve_nonfight_node(run)` marks the node CLEARED + advances — **no
income, tempest, Hearts, or `battle_log`** (V.83). See [economy](../../SPEC.md).

## Bosses

`bosses/data.py`: `BossDef` (kit, `BossCastEntry` list, `map_effect_id`,
`spawn_position`), the `BOSS_DEFS` registry, and `BossEncounterResult`
(`.all_enemies` property = boss + adds, `.map_effect_id`). Combat wiring for a
boss fight (attach the map effect before the loop) is
`combat/resolve.py::resolve_boss_combat` (the single src-side entry, V.59; the
`tools/playtest/_common.py` function is a shim that delegates to it) — see
[combat.md](combat.md).

## Board & map effects

`board.py` `BoardState` carries per-cell state the loop reads each tick:
`slow_cells` (+ `is_slow(q, r)`, consumed by `engine._process_board_state`),
`fog_range` (+ `is_in_fog_range(...)`, read by `targeting.py`), and
`CellModifier`. `map_effects.py` defines `MapEffect` (base; `register(bus)`
wires it) and the concrete effects — `SunlitTilesEffect`, `FogEffect`,
`HazardTilesEffect`, `DefensiveLeyEffect`, `FloodLanesEffect`, `SlowTilesEffect`
— keyed in `MAP_EFFECT_CLASSES`; `build_map_effect(effect_id, board, seed)`
constructs one. `loadout.attach_map_effect` (see [combat.md](combat.md)) builds
+ registers it onto a `CombatContext`.

## File map

| Concern | Symbol |
|---|---|
| Seed derivation | `encounter.derive_seed` + `CH_*` channels; helpers `augment_seed`(`reroll_count`)/`supply_seed`/`shop_seed`/`economy_seed`; `AUGMENT_REROLL_STRIDE`/`SHOP_REROLL_STRIDE` |
| Difficulty | `encounter.next_dc` / `dc_name` (`DC_STEP`, `STAGE_BASE`, `TYPE_MULT`) |
| Squad roll | `encounter.roll_squad`, `generate_fight`/`generate_reward`/`generate_challenge`/`generate_boss_encounter` |
| Per-node dispatch | `encounter.node_encounter` → `NodeEncounter`; `generate_node_reward` → `NodeReward` |
| Loot roll | `encounter.generate_reward_loot` → `RewardLoot` (`CH_REWARD`) |
| Boss data | `bosses/data.py` (`BossDef`, `BOSS_DEFS`, `BossEncounterResult`) |
| Board state | `board.py` (`BoardState`, `CellModifier`) |
| Map effects | `map_effects.py` (`MapEffect`, `MAP_EFFECT_CLASSES`, `build_map_effect`) |
