# Playtesting Plan

## 1. Problem

The engine is feature-complete through T.21 (combat, abilities, statuses,
encounter gen, bosses, map effects, weather cache). The UI is a placeholder.
Devs cannot today:

- See a full fight play out tick-by-tick outside of a unit test.
- Twiddle team / enemy / weather / seed without writing pytest.
- Walk a full 50-node run end-to-end.
- Inspect tick-level state — board, mana, statuses, modifiers, ability casts.
- Render a generated encounter (fight / reward / challenge / boss) before its
  view exists.

Unit tests prove correctness; they don't surface feel. T.25 covers batch
balance sweeps but is offline and statistical. We need an **interactive,
qualitative, dev-facing surface** that runs before the Flet UI exists.

## 2. Goals & Non-goals

### Goals

- Run any combat (legacy or new engine) from the command line with explicit
  team / enemy / weather / seed.
- Render a human-readable tick trace for **both** engines.
- Generate any node (FIGHT, REWARD, CHALLENGE, BOSS) by `(stage, node_index,
  run_seed)` and resolve it.
- Walk a full 50-node run with a stub team, collect per-node outcomes.
- Inspect rosters: champions / enemies at any `(tier, level)` with computed
  stats.
- Provide a scuffed admin Flet view that wires the above without theme work.

### Non-goals

- Production UI work (theme, layout, animation) — T.8-T.13 own that.
- Batch matchup sweeps and Bradley-Terry ratings — T.25 owns that.
- Replacing the legacy engine or unifying the two engines.
- Writing new game logic. Tools are pure consumers of existing pure functions.

## 3. Reality Check Summary

See [engine_split.md](engine_split.md) for the full note. Headline:

- `resolve_combat()` → `BattleResult` with events, **no abilities/bosses**.
- `compile_loadout` + `CombatContext` + `loop.run` → abilities/bosses, **no
  event stream**. Need `DebugRecorder` to bridge.
- T.25 already designs `tools/simulation/` — playtest tools live in
  `tools/playtest/` to avoid conflict.
- `apply_weather` (Weather Favor) is legacy-only; the new engine currently
  applies Affinity Clash but not Favor. Flagged, out of scope here.

All public APIs the plan depends on are confirmed in code:

| API | File | Signature |
|---|---|---|
| `resolve_combat` | `combat/legacy.py:423` | `(team, enemies, weather, *, node_id="") -> BattleResult` |
| `compile_loadout` | `loadout.py:167` | `(team, enemies, weather, seed=42) -> (pieces, bus)` |
| `CombatContext.__init__` | `combat/context.py:85` | `(pieces, bus, weather, seed=0, board_state=None)` |
| `combat/loop.run` | `combat/loop.py:174` | `(ctx) -> "team"|"enemy"|"draw"` |
| `attach_map_effect` | `loadout.py:140` | `(effect_id, ctx, seed) -> MapEffect` |
| `generate_fight` | `encounter.py:446` | `(run_seed, node_index, stage, dc=1.0) -> list[Enemy]` |
| `generate_reward` | `encounter.py:465` | same |
| `generate_challenge` | `encounter.py:735` | `(run_seed, node_index, stage, live_weather, dc) -> (squad, ChallengeReward)` |
| `generate_boss_encounter` | `encounter.py:779` | `(run_seed, node_index, stage) -> BossEncounterResult` |
| `format_combat_log` | `combat_log.py:77` | `(result, *, team=None, enemies=None) -> list[str]` |
| `get_champion` / `get_enemy` | `content.py:535/539` | `(id) -> Champion / Enemy` |

## 4. Layers

Three layers, build in order. Each layer delivers standalone value.

### Layer 1 — `tools/playtest/` CLI

Argparse / Click scripts, plain Python, stdout output, optional CSV/JSON dump.
No Flet dependency. Imports only `src/game/` and `src/api/`.

| Script | Purpose | Engine |
|---|---|---|
| `sim_fight.py` | One-shot fight from `--team`, `--enemies`, `--weather`, `--seed`, `--engine legacy|new`. Renders text log + survivors + damage tables. | Both |
| `sim_node.py` | `--stage N --node-index K --run-seed S`. Generates encounter, picks weather (live or `--weather`), resolves with `--team` or stub team, prints result. | Both |
| `sim_run.py` | Walks all 50 nodes with a `--team` (or seeded stub recruit). Per-node outcome row → CSV. Final summary: clears, deaths, total damage, where the run died. | Both |
| `inspect.py` | Roster browser: `--filter affinity=rain --tier 3 --level 2` prints a table of champion/enemy stats via `compose_stats`. | n/a |
| `inspect_node.py` | Generate node only (no resolve). Print enemy squad with stats, weather, reward payload, expected DC. | n/a |
| `debug_recorder.py` | Library used by `sim_fight` when `--engine new`. Subscribes to bus hooks, produces tick-ordered text. Reusable by T.12. | New |

Each script is ~50-150 LoC. All routed through one entry point (`python -m
tools.playtest.<name>`) for predictable invocation.

### Layer 2 — scuffed admin Flet view (`/admin`)

After Layer 1 proves value. Single route wired into `src/main.py`. No styling.
Lives in `src/ui/views/admin.py`, behind an env-var or build flag so it never
ships in a normal build.

Panels (all in one `ft.Tabs`):

1. **Encounter probe** — dropdowns for stage / node_index / weather / seed,
   team picker (multiselect from roster), engine toggle, "Resolve" button,
   `ft.ListView` for log lines.
2. **Roster browser** — filter by affinity / role / tier; data table of stats.
3. **Run stepper** — initialize `Run`, "Advance" button steps the trail, shows
   current node / weather / encounter preview / resolve button.
4. **Map-effect tester** — pick a boss, build context, show `board_state`
   summary after `attach_map_effect` (slow cells, fog ranges, etc.).
5. **God-mode toggles** — force weather, override seed, instant-kill button
   that calls `ctx.deal_damage(..., amount=1e9, tag=TRUE)` on a chosen target.

All panels reuse the Layer 1 functions. The view is the rendering surface,
not a parallel implementation. ~300-500 LoC total.

### Layer 3 — tick-replay visualizer (future)

Once `DebugRecorder` is proven via Layer 1 and Layer 2 plays back the same
event stream, Layer 2's combat panel becomes the T.12 combat-view prototype.
Not built in this plan — listed so the structural reuse is intentional.

## 5. File Layout

```
tools/                                  # new — also seeded by T.25
  __init__.py
  playtest/
    __init__.py
    debug_recorder.py                   # bus subscriber → text trace (new engine)
    sim_fight.py                        # CLI: single fight
    sim_node.py                         # CLI: single generated node
    sim_run.py                          # CLI: full 50-node run
    inspect.py                          # CLI: roster stats table
    inspect_node.py                     # CLI: encounter preview (no resolve)
    _common.py                          # team/enemy id parsing, table formatters

src/ui/views/
  admin.py                              # Layer 2 (added when Layer 1 stable)

docs/design/playtesting/
  README.md                             # this index
  plan.md                               # this doc
  engine_split.md                       # reality-check note
```

`tools/playtest/` and `tools/simulation/` (T.25) are siblings. Both can import
freely from `src/game/`; neither imports `src/ui/`.

## 6. CLI Sketches

### `sim_fight.py`

```
python -m tools.playtest.sim_fight \
    --team fox_thunder,bear_snow,otter_rain \
    --enemies frost_drone,smog_bot \
    --weather rain \
    --seed 42 \
    --engine legacy \
    --trace        # also dump per-tick events
    --csv out.csv  # optional damage-dealt CSV
```

Behavior: load champions / enemies by id (errors fast on unknown id), build
team list, call chosen engine, render log to stdout. With `--engine new`,
attach `DebugRecorder` before `loop.run` and render the recorder's stream.

### `sim_node.py`

```
python -m tools.playtest.sim_node \
    --stage 3 --node-index 22 --run-seed 12345 \
    --team fox_thunder,bear_snow,otter_rain \
    --weather thunder        # else use stage.affinity
    --engine new
```

Behavior: resolve `StageDef` from `route.STAGES[stage-1]`, call the matching
generator based on `route.STAGES[stage-1].node_types[node_index]`, pass the
squad into the chosen engine.

### `sim_run.py`

```
python -m tools.playtest.sim_run \
    --run-seed 12345 \
    --team fox_thunder,bear_snow,otter_rain \
    --weather-strategy stage-affinity   # or 'fixed:rain' or 'cache' (uses api/cache)
    --csv run_12345.csv
```

Behavior: iterate all 50 nodes, generate encounter, resolve, advance.
Aborts on team wipe (LOSS / DRAW with 0 survivors) — prints node index and
weather when the run ends. CSV columns: `node_index, stage, node_type,
city_id, weather, outcome, ticks, survivors, damage_dealt`.

### `inspect.py`

```
python -m tools.playtest.inspect \
    --kind champion \
    --affinity rain \
    --tier 3 --level 2
```

Output: aligned table of `id | name | role | tier/level | hp | str | int | as |
ms | mr | armor | res | range | active | passive`.

## 7. DebugRecorder Contract

Lives in `tools/playtest/debug_recorder.py`.

```python
@dataclass
class RecordedEvent:
    tick: int
    event_name: str
    actor_id: str
    target_id: str | None
    amount: float
    note: str

class DebugRecorder:
    def __init__(self, bus: EventBus, ctx: CombatContext) -> None: ...
    def render(self) -> list[str]: ...       # text lines, same shape as combat_log
    def to_csv_rows(self) -> list[dict]: ...
```

Subscribed hooks: `on_attack_start`, `on_attack_landed`, `on_damage_dealt`,
`on_heal`, `on_cast`, `on_cast_complete`, `on_death`, `on_spawn`,
`on_status_applied`, `on_status_expired`, `on_combat_end`.

Uses `Lifetime.COMBAT` so subscriptions auto-clear on `on_combat_end`.

## 8. Phase Order

| Phase | Deliverable | Cost |
|---|---|---|
| **P1** | `_common.py`, `debug_recorder.py`, `sim_fight.py` (legacy + new). | S |
| **P2** | `inspect.py`, `inspect_node.py`. Roster + encounter visibility without resolving combat. | S |
| **P3** | `sim_node.py`, `sim_run.py`. Full 50-node walk. CSV output. | M |
| **P4** | `ui/views/admin.py` scuffed view. Wires into `main.py` behind a flag. | M |
| **P5** | Optional: integration with `pytest -m playtest` markers — known-good replay snapshots. | S |

P1 is the smallest unit that returns value. Each later phase is independent.

## 9. Invariants the Plan Holds To

- **V.1** — `tools/playtest/` and `tools/simulation/` import from `src/game/`
  only. They never import Flet. The admin view (`src/ui/views/admin.py`) is
  the only Flet-aware part of the playtest surface.
- **V.2** — Combat remains a pure function. `DebugRecorder` is a passive
  observer on the bus; it never mutates.
- **V.3 / V.4** — `sim_run.py` uses `api/cache.py` if `--weather-strategy
  cache`; HTTP only via the existing refresher path on a worker thread.
- Pure-function determinism — every CLI takes an explicit `--seed` /
  `--run-seed`; no script touches the global RNG.

## 10. Risks & Open Questions

| Risk | Mitigation |
|---|---|
| Two engines diverge further; playtest output stops matching production. | Each tool prints the engine name in its header line. `sim_fight` supports `--engine both` for an A/B diff (planned in P3, not P1). |
| Weather Favor missing in new engine misleads balance reads. | `inspect.py` prints both legacy-with-Favor and raw-base stats side-by-side. Documented in `engine_split.md`. |
| Admin view leaks into production builds. | Gated by `TFT_ADMIN=1` env var (or hard-coded debug flag); not registered in `page.on_route_change` unless flag is set. |
| `DebugRecorder` payload format drifts from `events.py` dataclasses. | Recorder stores the raw event object, renders via a single mapping table — same shape `combat_log` uses for `BattleEvent`. |
| Stub teams for `sim_run` need balance to not always wipe stage 1. | `_common.py` provides a `default_team(stage)` helper using `compose_stats` at a sensible (tier, level). |

## 11. Why this Plan, in One Paragraph

The engine is observable in principle (pure functions, deterministic) but
inaccessible in practice (no UI, no CLI). Three layers — a CLI for fast
iteration, a scuffed admin view for click-driven exploration, and a future
tick-replay visualizer — produce playtest signal at increasing fidelity using
the same underlying functions. The plan stays inside V.1 / V.2 by adding only
read-only consumers; it defers batch balance work to T.25 and combat UI work
to T.12; and it surfaces the legacy / new engine split explicitly so every
tool can pick the right entry point for the question it's asking.
