# Encounter & board — squad generation, bosses, map effects

> **Status: LIVING** — must match `src/game/encounter.py`, `bosses/data.py`, `map_effects.py`, `board.py`. Audited by `/check`.
> **Scope:** seed-deterministic enemy/boss squad generation, difficulty, and the board-cell state combat reads. **Reconciled:** 2026-06-05.
>
> Citations by symbol, not line. Placement of the generated squad is [formation.md](formation.md). Design rationale (frozen): `docs/design/tasks/t19_*`, `t21_*`.

## Determinism — every roll derives from the seed

All procedural choices come from `derive_seed(run_seed, node_index, channel)`
(V.14) — same `(run_seed, node_index, channel)` → identical squad. Per-domain
seed helpers: `augment_seed`, `supply_seed`, `shop_seed`, `economy_seed`. The
RNG is Python `Random` seeded from that derived value; no global randomness.

## Difficulty

`next_dc(current_dc) -> float` advances the difficulty class along the run;
`dc_name(dc)` labels it. DC feeds tier/level weighting in squad rolling.

## Squad generation

- `roll_squad(...)` — the core roller: weighted tier pick (`_tier_weight` by
  stage), level pick (`_pick_level`), affinity slotting (`_affinity_slots` by
  stage affinity), role-composition guard (`_check_composition` over
  `_is_tanky`/`_is_support`/`_is_dps`), via `_weighted_pick` over a
  `filter_pool` of `EnemyDef`s. Builds `Enemy` instances with `_instantiate_enemy`.
- `generate_fight(...)` — a standard fight encounter.
- `generate_reward(...)` — reward-node contents.
- `generate_challenge(...)` — challenge nodes; can pull champion-derived enemies
  (`_champion_def_to_enemy`) and yields a `ChallengeReward`.
- `generate_boss_encounter(run_seed, node_index, stage) -> BossEncounterResult`
  — the boss squad + its map effect.

## Bosses

`bosses/data.py`: `BossDef` (kit, `BossCastEntry` list, `map_effect_id`,
`spawn_position`), the `BOSS_DEFS` registry, and `BossEncounterResult`
(`.all_enemies` property = boss + adds, `.map_effect_id`). Combat wiring for a
boss fight (attach the map effect before the loop) is
`tools/playtest/_common.py::resolve_boss_combat` — see [combat.md](combat.md).

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
| Seed derivation | `encounter.derive_seed` (+ `augment_seed`/`supply_seed`/`shop_seed`/`economy_seed`) |
| Difficulty | `encounter.next_dc` / `dc_name` |
| Squad roll | `encounter.roll_squad`, `generate_fight`/`generate_reward`/`generate_challenge`/`generate_boss_encounter` |
| Boss data | `bosses/data.py` (`BossDef`, `BOSS_DEFS`, `BossEncounterResult`) |
| Board state | `board.py` (`BoardState`, `CellModifier`) |
| Map effects | `map_effects.py` (`MapEffect`, `MAP_EFFECT_CLASSES`, `build_map_effect`) |
