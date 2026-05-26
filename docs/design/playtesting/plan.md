# Playtesting Plan

## 1. Problem

The engine is feature-complete through T.21 / T.24 / T.26 (unified combat,
abilities, statuses, encounter gen, bosses, map effects, weather cache, role-
aware enemy formation). The UI is still a placeholder counter. Devs cannot
today:

- See a full fight play out tick-by-tick outside of a unit test.
- Twiddle team / enemy / weather / seed without writing pytest.
- Walk a full 50-node run end-to-end.
- Render a generated encounter (fight / reward / challenge / boss) before its
  view exists.
- Inspect a champion or enemy at any `(tier, level)` with computed stats.

Unit tests prove correctness; they don't surface feel. T.25 covers batch
balance sweeps but is offline and statistical. We need an **interactive,
qualitative, dev-facing surface** that runs before the Flet UI catches up.

## 2. Goals & Non-goals

### Goals

- Run any combat from the command line with explicit team / enemy / weather /
  seed.
- Render a human-readable tick trace with HP deltas for every fight.
- Generate any node (FIGHT, REWARD, CHALLENGE, BOSS) by `(stage, node_index,
  run_seed)` and resolve it.
- Walk a full 50-node run with a stub team, collect per-node outcomes to CSV.
- Inspect rosters: champions / enemies at any `(tier, level)` with computed
  stats and weather-favor modifiers.

### Non-goals

- Production UI work (theme, layout, animation) — T.8–T.13 own that.
- Batch matchup sweeps and Bradley-Terry ratings — T.25 owns that.
- Writing new game logic. Tools are pure consumers of existing pure functions.

## 3. Engine Status (post-T.26)

`resolve_combat(team, enemies, weather, *, node_id="") -> BattleResult` is the
single public combat entry point. It composes `compile_loadout → CombatContext
→ loop_new.run` internally and uses the `BattleResultRecorder` to produce a
fully-populated `BattleResult.events`. See [engine_split.md](engine_split.md)
for the history of the resolved engine split.

One asymmetry the playtest layer must respect: `resolve_combat` does **not**
accept a `map_effect_id`. Boss fights need that map effect attached. The
playtest layer composes the primitives manually for BOSS nodes:

```python
pieces, bus = compile_loadout(team, encounter.all_enemies, weather)
for i, p in enumerate(pieces):
    p.speed_tiebreaker = i
boss_pos = next((b.spawn_position for b in BOSS_DEFS.values() if b.id == encounter.boss_enemy.id), None)
assign_spawns(pieces)   # T24 formation
recorder = BattleResultRecorder(pieces, weather, node_id)
recorder.register(bus)
ctx = CombatContext(pieces, bus, weather, seed=run_seed)
attach_map_effect(encounter.map_effect_id, ctx, seed=run_seed)
winner = loop_new.run(ctx, recorder)
result = recorder.build_result(winner)
```

This is exposed as a helper `resolve_boss_combat(...)` in `_common.py` so
sim_node and sim_run can call it without duplicating the wiring.

## 4. Confirmed API Surface

| API | File | Signature |
|---|---|---|
| `resolve_combat` | `combat/legacy.py:447` | `(team, enemies, weather, *, node_id="") -> BattleResult` |
| `compile_loadout` | `loadout.py:196` | `(team, enemies, weather, seed=42) -> (pieces, bus)` |
| `assign_spawns` | `combat/loop_new.py:510` | `(pieces) -> None` (T.24 formation) |
| `CombatContext` | `combat/context.py:77` | `(pieces, bus, weather, seed=0, board_state=None)` |
| `loop_new.run` | `combat/loop_new.py:563` | `(ctx, recorder=None) -> "team"\|"enemy"\|"draw"` |
| `attach_map_effect` | `loadout.py:141` | `(effect_id, ctx, seed) -> MapEffect` |
| `BattleResultRecorder` | `combat/recorder.py:41` | `(pieces, weather, node_id="")` |
| `format_combat_log` | `combat_log.py:77` | `(result, *, team=None, enemies=None) -> list[str]` |
| `generate_fight` | `encounter.py:446` | `(run_seed, node_index, stage, dc=1.0) -> list[Enemy]` |
| `generate_reward` | `encounter.py:465` | `(run_seed, node_index, stage, dc=1.0) -> list[Enemy]` |
| `generate_challenge` | `encounter.py:735` | `(run_seed, node_index, stage, live_weather, dc) -> (squad, ChallengeReward)` |
| `generate_boss_encounter` | `encounter.py:779` | `(run_seed, node_index, stage) -> BossEncounterResult` |
| `get_champion` / `get_enemy` | `content.py:536/540` | `(id) -> Champion / Enemy` |
| `champions_by_affinity` / `enemies_by_affinity` | `content.py:544/548` | `(weather) -> list[...]` |
| `STAGES`, `CITIES`, `stage_of`, `build_route` | `route.py:42/231/365/338` | route catalog + index helpers |
| `power` / `stat_multiplier` | `scaling.py:50/74` | `(tier, level) -> float` |

## 5. Layers

Two layers in scope. A third is mentioned for context but is not built here.

### Layer 1 — `tools/playtest/` CLI

Argparse scripts, plain Python, stdout output, optional CSV/JSON dump. No
Flet dependency. Imports only `src/game/`.

| Script | Purpose |
|---|---|
| `sim_fight.py` | One-shot fight from `--team`, `--enemies`, `--weather`, `--seed`. Renders `format_combat_log` to stdout with HP trace. |
| `sim_node.py` | `--stage N --node-index K --run-seed S`. Generates the matching encounter (FIGHT / REWARD / CHALLENGE / BOSS) and resolves it with `--team` (or `default_team`). |
| `sim_run.py` | Walks all 50 nodes with a `--team`. Per-node outcome row → CSV. Final summary: clears, where the run died, total damage. |
| `inspect.py` | Roster browser: `--kind champion|enemy --affinity rain --tier 3 --level 2`. Prints aligned stat table; optionally shows weather-favor modifiers via `combat_modifier`. |
| `inspect_node.py` | Generate any node without resolving combat. Print enemy squad with stats, expected DC, reward payload (for CHALLENGE). |
| `_common.py` | id parsing, table formatter, `default_team(stage_index)` helper, `resolve_boss_combat` wrapper. |

All scripts share invocation pattern: `python -m tools.playtest.<name> ...`.

### Layer 2 — scuffed admin Flet view (deferred)

Single `/admin` route wired into `src/main.py` behind an env-var flag, with
one `ft.Tabs` per panel (encounter probe, roster browser, run stepper,
map-effect tester). Reuses Layer 1 functions verbatim. Not built in this
iteration — Layer 1 unblocks balance work on its own.

### Layer 3 — tick-replay visualizer (future, T.12 prototype)

Already enabled by T.26's `BattleResultRecorder`; T.12 will consume the same
`BattleResult.events` the CLI renders today.

## 6. File Layout

```
tools/                                  # new top-level dir (also seeded by T.25)
  __init__.py
  playtest/
    __init__.py
    _common.py                          # parsing, formatting, default_team, resolve_boss_combat
    sim_fight.py                        # CLI: single fight
    sim_node.py                         # CLI: single generated node
    sim_run.py                          # CLI: full 50-node run
    inspect.py                          # CLI: roster stats table
    inspect_node.py                     # CLI: encounter preview (no resolve)

tests/tools/
  __init__.py
  test_playtest_common.py               # _common helpers
  test_playtest_smoke.py                # end-to-end smoke for each CLI

docs/design/playtesting/
  README.md                             # this index
  plan.md                               # this doc
  engine_split.md                       # historical note (post-T.26)
```

`tools/playtest/` and `tools/simulation/` (T.25, planned) are siblings. Both
can import freely from `src/game/`; neither imports `src/ui/`.

## 7. CLI Sketches

### `sim_fight.py`

```
python -m tools.playtest.sim_fight \
    --team champ_blaze_fox,champ_drift_yak,champ_tide_otter \
    --enemies enemy_frost_drone,enemy_smog_bot \
    --weather rain \
    --seed 42
```

Loads champions / enemies by id (errors fast on unknown id), calls
`resolve_combat`, renders log via `format_combat_log(result, team, enemies)`.

### `sim_node.py`

```
python -m tools.playtest.sim_node \
    --stage 3 --node-index 22 --run-seed 12345 \
    --team champ_storm_eagle,champ_drift_yak,champ_tide_otter \
    --weather thunder
```

Reads `STAGES[stage-1]`, picks the matching generator based on
`stage.node_types[node_position_in_stage]`, resolves with `resolve_combat`
(or `resolve_boss_combat` for BOSS nodes), prints log + result.

### `sim_run.py`

```
python -m tools.playtest.sim_run \
    --run-seed 12345 \
    --team champ_blaze_fox,champ_drift_yak,champ_tide_otter \
    --weather-strategy stage-affinity \
    --csv run_12345.csv
```

Walks all 50 nodes, generates encounter, resolves, advances. Aborts on team
wipe. CSV columns: `node_index, stage, node_type, city_id, weather, outcome,
ticks, survivors, damage_dealt`. Three `--weather-strategy` options:
`stage-affinity` (use stage's authored affinity), `city-default` (use
`CITIES[city_id].default_weather`), `fixed:rain` (force one).

### `inspect.py`

```
python -m tools.playtest.inspect \
    --kind champion \
    --affinity rain \
    --tier 3 --level 2 \
    --show-favor cloudy        # also display Weather Favor under cloudy weather
```

Output: aligned table — `id | name | role | tier/level | hp | str | int | as |
ms | mr | armor | res | range | active | passive`. With `--show-favor`, a
second column block shows favor-modified stats.

### `inspect_node.py`

```
python -m tools.playtest.inspect_node \
    --stage 3 --node-index 22 --run-seed 12345
```

Output: node header (city, weather, type), enemy squad table, computed budget
+ DC, and (for CHALLENGE) the reward payload.

## 8. Phase Order

| Phase | Deliverable | Cost |
|---|---|---|
| **P1** | `_common.py`, `sim_fight.py`. | S |
| **P2** | `inspect.py`, `inspect_node.py`. | S |
| **P3** | `sim_node.py`, `sim_run.py`. | M |
| **P4** | Smoke tests under `tests/tools/`. | S |
| **P5** (later) | `ui/views/admin.py` scuffed Flet view. | M |

P1 returns value alone. Each later phase is independent.

## 9. Invariants the Plan Holds To

- **V.1** — `tools/playtest/` imports from `src/game/` only. Zero Flet.
- **V.2** — Combat remains a pure function. CLIs are read-only consumers.
- **V.3 / V.4** — `sim_run.py` does not hit the OpenWeather API. It uses
  authored stage affinity / city defaults to pick weather. The cache layer
  stays untouched.
- Pure-function determinism — every CLI takes an explicit `--seed` /
  `--run-seed`; no script touches the global RNG.

## 10. Risks & Open Questions

| Risk | Mitigation |
|---|---|
| Default stub team auto-wipes on stage 1 because content balance still drifting. | `_common.default_team(stage_index)` picks `(tier, level)` tuned to budget. Players can override with `--team`. |
| `combat_log` only renders MOVE / ATTACK / CAST / DEATH; status / heal / spawn events from new abilities are silent. | Acceptable for P1. Follow-up task: extend `combat_log._format_event` to handle the rest — separate work, not blocking. |
| Boss path duplicates wiring that should live in one helper. | `_common.resolve_boss_combat` is the single helper; sim_node / sim_run call it for BOSS_FIGHT nodes. |
| `tools/__init__.py` collisions with T.25's planned `tools/simulation/`. | Both live under one `tools/` namespace package. Each subpackage owns its modules; no shared state. |
