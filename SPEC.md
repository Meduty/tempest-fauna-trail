# Tempest Fauna Trail — Implementation Spec

## G. Goal

Roguelike auto-chess strategy game inspired by TFT, under an animal-spirits-and-weather theme.
Players start with **1 chosen champion** and **10 Amber** (starting budget), then progress
through a fixed 50-node route of real-world cities across 6 continent stages. Live
OpenWeather data at each city shapes combat modifiers. Battles are tick-based and
auto-resolved — the player's decisions happen *between* fights.

**Core game loop (per node):**
1. **Trail** — view route progress, preview next node weather & enemies.
2. **Prep** — reposition pieces on the hex board, swap bench ↔ field, use items,
   browse the **champion shop** (buy / sell / reroll), spend Amber to level team-size.
3. **Combat** — auto-resolved; outcome grants Amber, items, and/or Tempest XP.

**Core player decisions:** team composition & synergy traits, item optimization,
weather-aware roster swaps, and board positioning.

**Run-start conditions:**
- Team-size cap: **3** at rank 1 (field 1 champion, bench holds 2 spares); grows with Tempest rank up to **10** at max rank (see D.14).
- Starting champion: player picks 1 from a seed-random offer of 3 (Tier 1–2).
- Starting shop: 5 Tier-1 champions (auto-populated; first reroll per node is free).
- Starting Amber: **10** (enough to buy 2 Tier-1 champions or 1 Tier-2 + save).

Built with Flet (Python). FH Technikum Wien project — 2 students, 8 weeks.

**Grading weight**: UI 4pt | Data Loading 2pt | Visualization 4pt | Structure 6pt | Documentation 4pt

## C. Context

| Constraint | Detail |
|---|---|
| Framework | Flet (Python), desktop app |
| API | OpenWeather free tier — 60 calls/min, current weather by city |
| Visualizations | Min 2 required: route map (Canvas) + run summary (BarChart) |
| Code structure | Modules: `api/`, `game/`, `ui/`, `viz/`. Classes + functions, no monolith |
| Documentation | README with setup, prompting strategy, flow chart |
| Deliverables | Proposal PDF, source ZIP, documentation PDF |

## I. Interfaces

### OpenWeather API
- `GET /data/2.5/weather?q={city}&appid={key}&units=metric`
- Response: `weather[0].id` → `WeatherState` via `WeatherState.from_openweather_id`
- Mapping (one `WeatherState` per OpenWeather main group):
  - `200-232` Thunderstorm → `THUNDER`
  - `300-321` Drizzle + `500-531` Rain → `RAIN`
  - `600-622` Snow → `SNOW`
  - `701-781` Atmosphere (mist/fog/haze/dust/smoke) → `MIST`
  - `800` Clear → `CLEAR`
  - `801-804` Clouds → `CLOUDY`
- Icon URL: `https://openweathermap.org/img/wn/{icon}@2x.png`

### Internal Data Flow
```
OpenWeather API → WeatherClient → cache.json
                                ↓
Route (staged nodes) → Node[weather] → Combat(team, enemies, weather) → BattleResult
                                                                    ↓
                                                              Run.battle_log → viz
```

### Flet Routes
| Route | View | Purpose |
|---|---|---|
| `/` | Main Menu | New game, continue, quit |
| `/trail` | Trail Map | Route progression, node preview, weather overlays |
| `/prep` | Prep Phase | Board placement, bench/field swap, shop, items |
| `/combat` | Battle | Auto-resolved combat with animated log |
| `/summary` | Run Summary | BarChart of damage per battle, win/loss |

## V. Invariants

- V.1: `game/` has zero Flet imports — pure logic, no UI coupling
- V.2: Combat is pure function — `resolve_combat(team, enemies, weather) -> BattleResult`. Single public entry point; the new ability/passive/status framework is invoked through it, never alongside it. `resolve_combat` internally delegates to `compile_loadout → CombatContext → combat/loop_new.run → BattleResultRecorder.build_result`. Boss fights use the same delegation chain but attach `map_effect_id` via `attach_map_effect` before running the loop (T.26). `resolve_combat`/`resolve_boss_combat` also accept an optional `run_mods: RunModifiers` (active augment ids + a mutable `augment_state` for quest trackers); it stays pure and deterministic, and the `None` default leaves all non-augment callers — including every balance sim — byte-for-byte unchanged (T.31).
- V.3: API failure never crashes app — failed fetch leaves node `unknown` (never-succeeded) or `substitute` (holds `CITIES[city_id].default_weather`); refresher streams keep retrying, never escalate
- V.4: All HTTP calls run on `threading.Thread`, never main thread
- V.5: Weather state enum: exactly 6 values (Clear, Cloudy, Mist, Rain, Snow, Thunder), mapped 1:1 to OpenWeather id main groups
- V.6: Each piece (Champion, Enemy, CombatPieceState) carries exactly one `affinity: WeatherState` field; it drives both weather systems (node-weather buff/debuff and the affinity damage triangle) — there is no separate weakness field
- V.8: `Champion.traits: list[str]` holds auto-chess synergy tags (Hunter, Mammal, Reptile, etc.). Distinct from `affinity`. Synergy tags are open-ended strings owned by content (T.5); engine treats them as opaque labels for grouping.
- V.7: Route is a staged path with multiple stages (one per continent, up to 6), with one or more nodes per stage and a final boss fight node in a famous city.
- V.9: Cache always populated post-init — every node ∈ {`unknown`, `live`, `substitute`}; engine never reads `None`
- V.10: Cache + refresher stateless re: game — refresher reads `Run.current_node` only for B-stream window, never writes game state
- V.11: Refresher tick = 1/min, fires 3 streams (A: full RR 50; B: RR window `[current+1 .. current+6]` count-clamped at trail end; C: uniform random 50), deduped per tick → ≤3 API calls/min; A alone bounds staleness ≤ 50 min
- V.12: Locked node weather = frozen snapshot in `Run`; cache may refresh same city, engine ignores cache for that node and reads `Run`
- V.13: Advance to `unknown` triggers one synchronous fetch + lock; on fetch fail, lock `substitute` with `CITIES[city_id].default_weather`
- V.14: `tools/simulation/` imports only from `src/game/` — no `ui/`, no `api/`. Matches the V.1 isolation rule extended to the sim layer; keeps `resolve_combat` as the only engine entry. (T.25)
- V.15: Every `ability_id` and `passive_id` referenced by `ChampionDef`, `EnemyDef`, or `BossDef` in content/roster data **must** resolve in `ABILITY_REGISTRY` or `PASSIVE_REGISTRY` respectively — enforced by CI guard test (`test_ability_catalog.py::test_all_*_resolve` and `test_all_boss_abilities_resolve`). BossDef coverage includes `phase1_active`, `phase1_passive`, `phase1_phase_hook`, `phase2_active`, `phase2_passive`, and `on_death_hook`. (T.30)
- V.16: Sim weather-affinity metrics (`own_weather_wr`, `counter_weather_wr`, `weather_sensitivity` on `PieceStats`) are **cross-weather** — derived only via `ratings.weather_metrics()` over per-piece win-rates pooled across **all** weathers, never from a single-weather `aggregate_stats` pass. A single weather yields `weather_sensitivity ≡ 0` by construction; `mega`/`runner` must pool weathers then inject before writing per-weather ratings CSVs. (T.25)
- V.17: Every id in `Run.active_augments` (and every quest-tracker id it implies) **must** resolve in `AUGMENT_REGISTRY` / `QUEST_TRACKER_REGISTRY` — enforced by CI guard test, mirroring V.15. (T.31)
- V.18: Augments are **run-long**: `TEAM`/`PIECE` augment effects are rebuilt fresh in `compile_loadout` each combat from `Run.active_augments`, never persisted as combat state; `RUN`-scope augments mutate `Run` exactly once at pick time. (T.31)
- V.19: Economy / shop / offer rolls are **seed-deterministic** — shop offers from `(run_seed, visit_index, reroll_count)` via `CH_SHOP`, SUPPLY from `(run_seed, node_index)` via `CH_SUPPLY`, Amber win-bonus from `(run_seed, node_index)` via `CH_ECONOMY`; same seed → same draws, mirroring the T.19 encounter contract (extends V.14-style determinism to the economy layer). (T.22)
- V.20: `Tempest` rank is **monotonic non-decreasing** — starts at 1, capped at 10, `rank == deployable board cap`. `Run.tempest` accumulates (+2/fight, +challenge bonus, or Amber rush) and cascades into rank-ups consuming the per-rank thresholds; overflow Tempest carries to the next rank, never decrements rank. (T.22)
- V.21: Trait breakpoints count **unique champion ids** (duplicate copies count once); trait effects enter combat **only** via `compile_loadout` (never alongside `resolve_combat`); `_resolve_traits` is a pure, RNG-free function of the team — replay-stable. (T.28)
- V.22: Every tag in `Champion.traits` **must** resolve in `TRAIT_REGISTRY`, and every champion carries ≥1 Kinship + ≥1 Calling (+ `Primordial` at T10) — CI-guarded, mirroring V.15. Enemies carry trait tags as opaque labels only and never light up breakpoints. (T.28)
- V.23: Items apply **only** via `compile_loadout` (combat-facing `EffectBundle` factories in `ITEM_REGISTRY`) or `RUN_ACTION_REGISTRY` (run-facing); ≤3 equipped items per piece; item procs are deterministic (cadence counters / one-shot flags, never RNG). (T.29)
- V.24: Special items (`RUN_ACTION_REGISTRY`) operate on `Run` state only and are **never** referenced from `game/combat/` — combat sees only their result (`effect_systems_design.md` §8.4). (T.29)
- V.25: Damage-over-time fires on a **per-status cadence**, not per engine tick — `StatusDef.dot_interval_ticks` (default `100` ticks = 1s; `sudden_death` = `1` = per-tick timeout failsafe). DOT damage **and** stack decay (`decay_stacks_per_dot`, renamed from `decay_stacks_per_tick`) apply only when the per-instance clock `StatusInstance.ticks_to_next_dot` reaches 0. That clock **free-runs**: re-applying a status refreshes duration/stacks but never resets the next-DOT timer (so poison-on-every-auto can't starve or delay ticks). A DOT pays its final tick on the same engine tick it expires (DOT runs **before** the expiry check); expiry itself stays tick-precise (`remaining_ticks` decremented every tick). Rationale: 1 action ≈ 600 ticks, so the old per-tick DOT was ~100× mis-scaled and spammed `on_damage_*` hooks. `dot_per_tick` magnitudes are now per-DOT-tick (≈ per-second): burn `40.0`, poison `18.0`/stack, sudden_death `0.5` (provisional, pending sim sweep). (T.20, T.30)
- V.26: A status has **one** `StatusInstance` per `status_id` per piece — identity is `status_id` only, non-stacking across sources (Option 1 / TFT-style). Re-application merges into that single instance; `ctx.apply_status(..., potency=)` lets a caster override per-DOT-tick damage (`StatusInstance.potency`, `0` → fall back to `StatusDef.dot_per_tick`), and on merge the **strongest potency wins** and takes damage credit (`source_id`). Intensity that should *accumulate* across applications uses `StackBehaviour.STACK` (poison), never separate instances. (T.20, T.30)
- V.27: The combat `Piece` carries `level` (in-tier 1–3), copied from `Champion.level`/`Enemy.level` in `loadout.piece_from_*`, so level-scaling passives can read `owner.level`. The marker status `focus_fire` (no gates, no DOT) backs the `enemy_company_captain` **Focus Fire** passive: a captain hit marks the struck enemy **and raises its `threat`** (targeting priority — a TIMED modifier expiring with the mark) so the captain's allies focus it; an ally *other than* the captain hitting a marked target triggers bonus INT magic damage from the captain. Both the bonus and the threat bump scale with captain `level` — guarded against re-triggering on its own bonus hit. (T.30)

## T. Tasks

**Status legend:** ✅ Done — ✔ implemented & tested | 🔶 Partial — incomplete implementation | 📋 Plan — documented design, not yet coded | ❌ Not started — no plan or code

| # | Task | Files (code paths are relative to `src/`; `docs/` and `tools/` paths are repo-root relative) | Depends | Est | Status |
|---|---|---|---|---|---|
| T.1 | Data models — Champion, Enemy, Node, Run, BattleResult, WeatherState + NodeType/NodeState + combat runtime state + JSON serialization helpers | `game/models.py`, `docs/design/tasks/t1_data_models_plan.md`, `docs/design/tasks/t1_model_contracts.md` | — | M | ✅ Done |
| T.2 | Weather effects — directional predator/prey ring; two decoupled systems (node-weather buff/debuff + affinity damage triangle), per-weather stat packs, shop weight, `apply_weather` for combat init | `game/weather_effects.py`, `docs/design/tasks/t2_weather_effects_plan.md` | T.1 | M | ✅ Done |
| T.3 | Combat engine — tick-based auto-resolve (10ms tick simulation), apply weather modifiers | `game/combat.py` | T.1, T.2 | M | ✅ Done |
| T.4 | City route — ~50 cities (one per node) across 6 staged continents, coordinates, stage affinity, enemy pools | `game/route.py` | T.1 | M | ✅ Done |
| T.5 | Content — define champion roster (target: 1 per affinity × 10 tiers = ~60 champions; MVP cut OK) + ~5 enemy types with stats + synergy trait catalog | `game/content.py` | T.1 | M | ✅ Done |
| T.6 | OpenWeather client — fetch current weather, parse to WeatherState | `api/weather.py` | T.1 | S | ✅ Done |
| T.7 | Cache + refresher — stateless per-city cache (`unknown` / `live`+`fetched_at` / `substitute` holding city-default weather), 3-stream refresher (A full RR 50, B window `[current+1..+6]` count-clamped, C uniform random) ticks 1/min deduped → ≤3 calls/min, sync fetch on advance-to-`unknown` | `api/cache.py`, `api/refresher.py`, `docs/design/tasks/t7_cache_refresher_plan.md` | T.6 | M | ✅ Done |
| T.8 | Theme + shared components — colors, fonts, champion card, weather badge | `ui/theme.py`, `ui/components/` | — | S | ✅ Done |
| T.9 | Main menu view — new game, load game, quit | `ui/views/menu.py`, `main.py` | T.8 | S | 📋 Plan |
| T.10 | Run-start flow — initial champion pick (1-of-3 offer), first shop population, starting Amber/Tempest state init | `game/run_init.py`, `ui/views/trail.py` | T.5, T.8, T.22 | S | 📋 Plan |
| T.11 | Route map visualization — Canvas with city nodes + weather icons | `viz/route_map.py`, `ui/views/trail.py` | T.4, T.6, T.8 | L | 📋 Plan |
| T.12 | Combat view — animated battle log, HP bars | `ui/views/combat.py` | T.3, T.8 | L | 📋 Plan |
| T.13 | Run summary visualization — BarChart of damage per battle | `viz/run_summary.py`, `ui/views/summary.py` | T.3, T.8 | M | 📋 Plan |
| T.14 | Save/load — JSON serialization of Run state | `game/save.py` | T.1 | S | ❌ Not started |
| T.15 | Routing + app wiring — connect all views in main.py | `main.py` | T.9-T.13 | M | 📋 Plan |
| T.16 | Unit tests — combat, weather effects, API parsing | `tests/` | T.1, T.2, T.3, T.6, T.7 | M | ✅ Done |
| T.17 | Documentation — README, prompting strategy, flow chart | `README.md`, `docs/` | all | M | 🔶 Partial |
| T.18 | Power & scaling model — `P` formula, `√P` stat coupling, economy cost curve | `game/scaling.py`, `docs/design/tasks/t18_power_scaling_plan.md` | T.1 | S | ✅ Done |
| T.19 | Encounter generation — seed-deterministic squad/offer fill, enemy power clustering, node budgets | `game/encounter.py`, `docs/design/tasks/t19_encounter_generation_plan.md` | T.1, T.4, T.5, T.18 | M | ✅ Done |
| T.20 | Ability/passive/status framework — registry, typed event bus, status gates, boss phase hook | `game/abilities/`, `game/effects.py`, `game/events.py`, `game/status.py`, `game/registries.py`, `docs/design/tasks/t20_ability_framework_plan.md` | T.3 | L | ✅ Done |
| T.21 | Challenge & boss encounters — champion-faction challenges, 2-phase bosses, auto-battle-aware map effects | `game/encounter.py`, `game/board.py`, `game/map_effects.py`, `game/bosses/`, `docs/design/tasks/t21_challenge_boss_plan.md` | T.19, T.20 | M | ✅ Done |
| T.22 | Economy & shop — Amber income per node (+3 base, +1-3 win bonus, +interest 1/10 cap 5), shop refresh (5 slots, auto-refresh each node, manual reroll 1 Amber, first reroll per node free), buy `Cost(T)=T`, sell `floor(Cost/2)`, 3-copy leveling, SUPPLY 1-of-5 free recruit, team-size Tempest leveling (accelerating thresholds 2/4/6/10/14/18/24/30/36, free +2/fight, all-or-nothing Amber rush 1:1, max rank 10), stage-gated tier probabilities | `game/economy.py`, `game/shop.py`, `game/models.py`, `docs/design/tasks/t22_meta_progression_plan.md` | T.1, T.5, T.18 | L | ✅ Done |
| T.23 | Prep formation snapshot integration — lock player board placement in Prep, validate deployment constraints, pass explicit coordinates into combat init | `ui/views/prep.py`, `game/models.py`, `game/combat.py`, `docs/design/tasks/t23_prep_formation_snapshot_plan.md` | T.1, T.3, T.15 | M | 📋 Plan |
| T.24 | Enemy formation policy — deterministic role-aware spawn planner (frontline forward, backline protected, size-aware packing) with safe fallback | `game/formation.py`, `game/combat.py`, `docs/design/tasks/t24_enemy_formation_plan.md` | T.3, T.5, T.23 | M | ✅ Done |
| T.25 | Power simulation & balance benchmarking — deterministic matchup sweeps and empirical power ratings | `tools/simulation/`, `docs/design/tasks/t25_power_simulation_plan.md` | T.3, T.5 | M | ✅ Done |
| T.26 | Combat engine unification — `resolve_combat` delegates to the new loop via `BattleResultRecorder`; legacy tick loop retired; Weather Favor applied in `compile_loadout` | `game/combat/legacy.py`, `game/combat/loop_new.py`, `game/combat/recorder.py`, `game/loadout.py` | T.3, T.20 | M | ✅ Done |
| T.27 | Playtesting CLI — dev-facing tools for sim_fight / sim_node / sim_run / inspect / inspect_node, no Flet, pure consumers of `src/game/` | `tools/playtest/`, `docs/design/playtesting/` | T.3, T.5, T.19, T.21, T.26 | M | ✅ Done |
| T.28a | Synergy trait framework + declarative content — `TraitScope`/`TraitBreakpoint` types + `@register_trait`; `_resolve_traits` team roll-up in `compile_loadout` (unique-id count, scope, §10.1 order); affinity-trait synthesis from `affinity`; Calling-vocabulary reconciliation (drop 4 dead T.5 tags, add `Packmate` + carriers); `BattleResult.trait_activations`; all stat-pack breakpoints (Affinities + Kinship/Calling stat portions) | `game/traits/`, `game/loadout.py`, `game/models.py`, `game/content.py`, `docs/design/tasks/t28_trait_effects_plan.md` | T.5, T.20, T.26 | M | 📋 Plan |
| T.28b | Trait combat primitives + mechanic breakpoints — `Piece.shield_hp` absorb, `StatusGate.UNTARGETABLE`, `taunt`, deterministic dodge, revive-once, time-ramp, echo/double-cast, mana-denial aura (all RNG-free); Tier-B proxies (Skyborn collision/tie, Stalker reposition); all hook-based breakpoint effects | `game/status.py`, `game/piece.py`, `game/combat/loop_new.py`, `game/combat/context.py`, `game/targeting.py`, `game/traits/`, `docs/design/tasks/t28_trait_effects_plan.md` | T.28a | M | 📋 Plan |
| T.29a | Item engine — components + combined + 16 core cut — real component→stat mapping (mana per-`ActiveSlot`, not a stat), `RECIPE_MAP` (8×8 = 36) + `combine()` recipe branch, `Champion.items` (≤3 persistent) equip applied in `compile_loadout`, `@register_item` factories for 8 components + 16 core-cut items (modifier + hook, closure-per-combat), seed-deterministic REWARD-node drops | `game/items/`, `game/loadout.py`, `game/models.py`, `game/encounter.py`, `docs/design/tasks/t29_item_engine_plan.md` | T.1, T.20, T.22 | L | 📋 Plan |
| T.29b | Items — remaining 20 combined + emblems + special — remaining 20 combined-item factories, 6 emblems (`granted_traits`, counted via T.28a) + Spirit-Gem `combine()` branch, 6 special run-actions (`RUN_ACTION_REGISTRY`, operate on `Run`) + interactive `sim_run` driver (shared shell with T.31), Spellfang Crown `ability_can_crit` unlock | `game/items/`, `game/registries.py`, `tools/playtest/sim_run.py`, `docs/design/tasks/t29_item_engine_plan.md` | T.29a, T.28a | M | 📋 Plan |
| T.30 | Ability & passive catalog — implement all 120 roster ability/passive handlers (60 champions + 60 enemies) plus 6 full 2-phase boss kits; fix registration IDs, fix generic-fallback bias, add summon lifecycle primitives, add CI guard test for ability-id resolution | `game/abilities/champions.py`, `game/abilities/enemies.py`, `game/abilities/bosses.py`, `game/piece.py`, `game/combat/loop_new.py`, `docs/design/tasks/t30_ability_catalog_plan.md` | T.5, T.20, T.21, T.26 | L | ✅ Done |
| T.31 | Augment system — `Augment`/`AugmentScope`/`AugmentQuality` model + `@register_augment`; all ~50 catalog augments (4 qualities × 3 scopes `TEAM`/`PIECE`/`RUN`, incl. quest trackers); deterministic 1-of-3 offers + one reroll + Prismatic gating + per-stage quality-weight curve; `Run.active_augments`/`augment_state` (+ serialization, id-validation); `compile_loadout` augment-bundle application (step 6) + quest-tracker wiring (step 9); `RunModifiers` combat seam (optional, `None`-default back-compat); `sim_run` augment resolution — `--augment-policy {first,random,highest-quality,none}` + `--interactive` manual run | `game/augments.py`, `game/loadout.py`, `game/models.py`, `game/combat/legacy.py`, `tools/playtest/sim_run.py`, `docs/design/tasks/t31_augment_system_plan.md` | T.20, T.22, T.26, T.28b, T.29b | L | 📋 Plan |

**Size**: S = <1h, M = 1-3h, L = 3-6h

### T.1 Planning Notes

- T.1 now includes non-combat node typing (`fight`, `reward`, `augment`, `boss_fight`) so route and UI flows can share one node contract.
- T.1 now includes combat runtime model surfaces needed by the combat proposal.
- T.1 now includes JSON-friendly serialization contracts to reduce risk for T.14 save/load.
- Detailed T.1 execution plan: `docs/design/tasks/t1_data_models_plan.md`
- Detailed model schema contracts: `docs/design/tasks/t1_model_contracts.md`

### T.2 Planning Notes

- Directed predator/prey ring of 5 active weathers (`Mist → Cloudy → Rain → Snow → Thunder`) + `Clear` outside, inert in both systems. Each weather's primary prey is the previous ring member, secondary prey the one before that; predators are the inverse.
- **Two decoupled systems**, evaluated separately, never summed:
  - **Weather Favor — node weather**: buffs/debuffs each piece by its affinity vs the node weather. 5 tiers — strong/medium/weak buff (self / primary predator / secondary predator) at `+10/+6/+3%`, medium/weak debuff (primary/secondary prey) at `−6/−3%`. Self is the strict maximum; no strong debuff. Applied once at combat init.
  - **Affinity Clash — affinity damage triangle**: per-hit multiplier on every damage instance by attacker affinity vs defender affinity — `1.20/1.10/1.00/0.90/0.80` for primary predator / secondary predator / mirror or Clear / secondary prey / primary prey. Resolved per hit in the combat engine.
- `Mist` Weather Favor debuff is the only flat-integer effect: base `attack_range -1` (min 1), which scales/rounds to `-1` at medium tier and `0` at weak tier.
- Detailed T.2 plan: `docs/design/tasks/t2_weather_effects_plan.md`.

### T.4 Planning Notes

- Route locked: 6 continent stages, 50 linear nodes, one distinct city per node;
  each stage carries an authored affinity (one per `WeatherState`).
- Detailed T.4 plan: `docs/design/tasks/t4_city_route_plan.md`.

### T.7 Planning Notes

- Cache state per city: `unknown` (initial), `live` (fetched ok + `fetched_at` age), `substitute` (fetch failed, holds `CITIES[city_id].default_weather`). Substitutes retry every tick; success flips to `live`.
- 3 streams per 1-min tick, dedupe order A→B→C: A = full RR over 50; B = RR over `[current+1..+6]` (count-clamped at trail end, modbus-style base+count, no wrap, no pad); C = uniform random over 50 (no freshness re-roll). A alone ⇒ ≤ 50 min staleness everywhere.
- Run init: alloc cache as 50× `unknown`, fire tick #1 sync (fetches nodes 0, 1, + 1 random), then start. Node 0 locks from tick-1 result.
- Lock semantics: on advance, snapshot cache entry into `Run`. Cache keeps refreshing same city (harmless). Engine reads `Run` for locked nodes, cache for unlocked.
- Advance-to-`unknown` = single sync fetch + lock; on fail, lock substitute. Rare path: tick beats player advance speed.
- No backoff on repeated fetch fails; streams keep firing at 3/min.
- UI age warnings (subtle top-right indicator when any `substitute` present or any `live` aged > 2h, hover lists affected cities) deferred — see D.17.
- Detailed plan: `docs/design/tasks/t7_cache_refresher_plan.md`.

### T.18-T.31 Planning Notes (Systems Expansion)

- T.18 power scalar `P = 1.5 ** ((T-1)/2 + (L-1))` drives encounter budgets and
  piece stat generation; "two tiers == one level".
- T.19 generates encounters deterministically from `Run.seed` via per-node
  sub-seeds; squads/offers are regenerated lazily, not stored.
- T.20 builds the ability/passive/status framework (resolves D.3-D.5); bosses
  are its first consumer.
- T.21 layers spirit challenges and 2-phase bosses on the T.19 generator.
- T.22 implements the full economy loop: Amber income (+3 base/node, +1-3 win
  bonus, +interest 1/10 cap 5), shop (5 slots, auto-refresh per node, reroll =
  1 Amber, first free), buy/sell (`Cost(T) = T` / `floor(Cost/2)`), 3-copy
  leveling, Tempest team-size leveling (accelerating thresholds, free +2/fight,
  all-or-nothing Amber rush, max rank 10), and stage-gated tier probabilities.
  Also covers supply node resolution (1-of-5 free recruit). (Augment node
  resolution + the augment pool moved to T.31; T.22 stays a dependency.)
- T.23 makes Prep placement authoritative: board coordinates from Prep become
  combat init input; combat no longer overwrites player layout when a valid
  placement snapshot is provided.
- T.24 introduces deterministic enemy formation heuristics by role and team
  size, replacing index-only right-side packing while preserving replay
  determinism.
- T.25 adds deterministic balance simulation and matchup benchmarking over the
  existing auto-resolve engine for data-driven tuning. Ships three modes:
  full 1v1 (C(N,2) pairs), full 2v2 Cartesian (opt-in, ~25M pairs), and
  random team sampling (`team-sample`, default; optional tier-stratification).
  Per-piece win attribution is binary (every piece on the winning team scores
  1 vs every piece on the losing team; draws split 0.5). Win-rate analysis
  uses the deterministic power-threshold model (higher power wins 100%,
  equal power scores 50%).
- T.26 unified the two combat engines that briefly coexisted: legacy
  `resolve_combat` (T.3) and `compile_loadout + CombatContext + loop.run`
  (T.20). Post-T.26 there is **one** entry point — see V.2 and
  `docs/design/playtesting/engine_split.md` for the historical note.
- T.27 ships the dev-facing playtest CLI suite (`tools/playtest/`) used to
  exercise the engine before the Flet UI exists; pure consumer of
  `src/game/`. See `docs/design/playtesting/plan.md`.
- T.28 (split **T.28a/T.28b**) implements synergy trait breakpoint effects on the
  T.20 substrate. T.28a = framework + declarative stat-pack content + the
  Calling-vocabulary reconciliation (B.9); T.28b = combat primitives
  (shield/untargetable/taunt/dodge/revive/ramp/echo/aura — deterministic, no RNG)
  + hook-based breakpoints, with the most engine-invasive ones (Skyborn
  collision/tie, Stalker reposition) MVP-simplified to proxies. Affinity traits
  are derived from `affinity`. Plan: `docs/design/tasks/t28_trait_effects_plan.md`.
- T.29 (split **T.29a/T.29b**) implements the item engine: components + combined
  items + 3-slot equip + REWARD drops + 16-item core cut (T.29a), then the
  remaining 20 combined + emblems + special run-actions with an interactive
  `sim_run` driver (T.29b). Components map to **real** engine stats (mana handled
  per-`ActiveSlot`, not as a base stat — see B.10); emblems gate on T.28a.
  Content `docs/design/content/item_catalog.md`; substrate
  `docs/design/systems/effect_systems_design.md` §8; plan
  `docs/design/tasks/t29_item_engine_plan.md`.
- T.30 implements the full ability & passive catalog for all 120 roster pieces
  and 6 bosses. Key design decisions: round = 600 ticks (G8, convention only,
  no round abstraction); summons are full Piece objects (G6); auras use periodic
  radius re-application (Q4); coefficients are fixed authored values; boss kits
  are full 2-phase with phase-transition map effects (Q5). Also fixes the
  generic fallback formula (`max(STR, INT)` instead of INT-biased) and re-keys
  all ability registration IDs to match content roster prefixes.
- T.31 implements the full augment system on the T.20 effect substrate
  (`effect_systems_design.md` §9): `Augment` model with `TEAM`/`PIECE`/`RUN`
  scopes, all ~50 augments from `augment_catalog.md` across 4 qualities, and
  quest augments as `RUN`-scope + persistent cross-combat trackers. Augments are
  run-long (V.18) — picked at `AUGMENT` nodes, re-applied every combat via
  `compile_loadout`, threaded in through the optional `RunModifiers` seam (V.2).
  Sequenced **after** T.22/T.28/T.29 because most augment content reaches into
  economy/trait/item systems those tasks build. The `sim_run` CLI walks a
  complete run (headless `--augment-policy` + rudimentary interactive mode),
  groundwork the eventual Flet view fires. Detailed plan:
  `docs/design/tasks/t31_augment_system_plan.md`.
- Detailed plans: `docs/design/tasks/t18_power_scaling_plan.md` through
  `docs/design/tasks/t25_power_simulation_plan.md`;
  `docs/design/playtesting/plan.md` covers T.27;
  `docs/design/tasks/t30_ability_catalog_plan.md` covers T.30.

## B. Bugs / Backprop

- B.1 `NodeType` extended with `SUPPLY` and `CHALLENGE` for the T.4 route
  vocabulary; `docs/design/tasks/t1_model_contracts.md` must be synced.
- B.2 `Reward` node redefined as an easy fight with guaranteed loot — it carries
  both `enemy_pool_id` and `reward_table_id`, not a pure non-combat node.
- B.3 Planned model additions: `CombatPieceState.active_statuses` (T.20) and
  `Run.content_version` (T.19) for procedural-run save stability.
- B.5 Weather rework (T.2 revision): `CombatPieceState` gains an `affinity:
  WeatherState` field — the combat engine needs per-piece affinity at damage
  time for Affinity Clash (target-dependent, cannot be pre-snapshotted). The shipped
  `combat.py` damage step gains an Affinity Clash multiplier hook; `apply_modifier` is
  renamed `apply_weather`. Touches `models.py`, `to_dict`/`from_dict`,
  `combat.py`, `t1_model_contracts.md`, `test_models.py`, `test_combat.py`.
- B.4 Currency named **Amber**, the team-size XP counter named **Tempest**
  (`1 Amber : 1 Tempest`). The `Run.gold` model field should be renamed
  `Run.amber` — touches `models.py`, `to_dict`/`from_dict`, `test_models.py`,
  and `t1_model_contracts.md`.
  **RESOLVED [2026-06-03] (T.22):** `Run.gold` → `Run.amber` (`from_dict` reads
  the legacy `gold` key for back-compat); `Run` also gained `tempest`,
  `tempest_rank`, `champion_copies`, `shop_offers`, `shop_rerolls`
  (+ validation + serialization). See V.19/V.20.

- B.6 Combat gains a **penetration** stat pair — `penetration` (flat) and
  `penetration_pct` (`[0.0, 1.0]`) on `Champion`, `Enemy`, and
  `CombatPieceState`. The attacker's penetration erodes the target's
  Armor/Resistance before mitigation (percent first, then flat, clamped at 0);
  `true` damage is unaffected. Default `0` — a build-around stat, not a base
  archetype stat, not power-scaled (`T18`). Touches `models.py`, `combat.py`,
  `weather_effects.py` (`apply_weather` copy-through), `combat_system_proposal.md`
  §4.2/§4.4, `t1_model_contracts.md`, `t3_combat_engine_plan.md`,
  `test_models.py`, `test_combat.py`.

- B.7 Route reworked to **one city per node** — ~50 real cities across 6
  continent stages (was 6 hub cities, one per stage). A stage carries an
  authored **affinity** (`StageDef.affinity`, one per `WeatherState`) used by its
  boss and challenge; each node/city carries its own live weather. The stage-1
  boss fight moved to Vienna. Supersedes the "~6 cities" content budget. Touches
  `t4_city_route_plan.md`, `boss_roster.md`, `CLAUDE.md`, and (when built)
  `route.py`.

- B.8 [2026-06-03] Sim weather columns (`own_weather_wr`, `counter_weather_wr`,
  `weather_sensitivity`) were dead — computed inside `aggregate_stats`, which
  `mega`/`runner` call once **per single-weather** ratings file, so
  `weather_sensitivity = max−min` over one value ≡ always `0.0` and own/counter
  were sparse-zero. **Cause:** a cross-weather metric derived from single-weather
  input. **Fix → V.16:** extracted `ratings.weather_metrics()` (single source of
  truth); `mega`/`runner` now pool per-weather win-rates and inject before
  writing. Tests: `test_ratings.py` (own/counter/sensitivity + single-weather→0).
  Note: the report's "weather inert" verdict was a *separate* analysis error —
  the cross-weather sweep measures only Weather Favor, never Affinity Clash
  (target-dependent, weather-independent); both must be measured separately.

- B.9 [2026-06-03] Calling-vocabulary drift: `CALLING_TAGS` (`content.py`) carried
  4 dead tags (`Bulwark/Drifter/Harbinger/Emissary`) introduced in the T.5 content
  commit — 0 carriers, referenced nowhere else, never present in any design doc —
  and omitted `Packmate` (the catalog's 12th Calling). **Cause:** the T.5 ad-hoc
  calling set was never reconciled with the later `trait_catalog.md` /
  `champion_roster.md` 12-Calling design. **Fix (T.28a):** drop the 4 dead tags,
  add `Packmate` + ~8 T1-3 carriers; **V.22** prevents recurrence.

- B.10 [2026-06-03] Item-doc drift: `effect_systems_design.md` §8.1 budgets "15
  combined" and §8.2/§8.3 use placeholder component ids + stat keys that don't
  exist in the engine (`ability_power`, `attack_damage`, `mana_max`); `item_catalog.md`
  §6 cites a non-existent "§14" for the 3-slot rule. **Cause:** the §8 sketch
  predates the 8-component/36-item `item_catalog.md` and the engine's real stat
  vocabulary. **Fix (T.29):** map components to real `Piece.base_stats` keys (mana
  handled per-`ActiveSlot`), annotate §8.1 → 36, and make
  `t29_item_engine_plan.md` §3.3 the 3-slot authority.

- B.11 [2026-06-03] DOT decay was mis-scaled to the engine tick: `poison`
  `decay_stacks_per_tick` removed one stack **every 10ms tick** while
  `duration_ticks` (400–500) was sized for the action clock — so a 4-stack
  poison drained in 4 ticks (~40ms, ~15 dmg), its `duration_ticks` was dead
  code, and poison sat ~40× weaker than `burn` (600+) with nothing visible at
  the call site. Separately, `StatusDef.dot_per_tick` was static on the shared
  def, so no caster could scale a DOT (every burn identical T1↔T10). **Cause:**
  DOT cadence + decay written as if 1 tick ≈ 1 turn, but a tick is ~600× finer
  than an action; intensity hard-coded on the shared def. **Fix → V.25/V.26:**
  data-driven `dot_interval_ticks` (1s default, `sudden_death` = 1),
  free-running per-instance DOT clock, `decay_stacks_per_dot`, per-instance
  `potency` with strongest-wins merge; magnitudes retuned to per-second. Touches
  `status.py`, `piece.py`, `loadout.py`, `combat/context.py`,
  `combat/loop_new.py`, `combat/loop.py`, `effect_systems_design.md`.

## D. Systems Yet To Be Determined

Live backlog of big design decisions still open. Items now locked are recorded
in their T-task plan docs; what remains here is genuinely undecided.

### Route & Encounters

- D.1 Route branching: the linear 6-stage / 50-node chain is **locked** (T.4);
  whether optional branch/merge paths are added post-MVP is open.
- D.2 Boss content: authored per-boss kits (phase 1 + phase 2 abilities, on-death
  hooks) **designed in T.21** — `game/bosses/data.py`. Ability *implementation*
  (handler functions) **completed in T.30** — `game/abilities/bosses.py` contains
  full 2-phase kits for all 6 bosses with phase-transition hooks at 50% HP.
- D.3 Combat board-cell modifiers: **designed and implemented in T.21** —
  `game/board.py` (BoardState + CellModifier), `game/map_effects.py` (6 effect
  classes), `game/combat/loop.py` (_process_board_state), `game/targeting.py`
  (fog filter). Remaining: per-ability content that writes to board_state.

### Combat Systems

- D.5 Ability / passive / status framework: **designed in T.20**; per-champion
  ability and passive *content* (kits) **implemented in T.30** — all 120 roster
  pieces + 6 bosses now have authored handlers with fixed coefficients.
- D.6 Combat timeout policy: keep hard draw only or add sudden-death escalation.
- D.7 HP carryover: **LOCKED — full reset per fight.** Champions heal to full HP
  between nodes. Simplifies economy tuning and avoids snowball/frustration; the
  challenge comes from enemy scaling and weather variance, not attrition.

### Content

- D.8 Synergy traits: V.8 reserves `Champion.traits` as auto-chess synergy tags.
  **Design complete; implementation planned as T.28a/T.28b**
  (`docs/design/tasks/t28_trait_effects_plan.md`) — breakpoint *concepts* in
  `docs/design/content/trait_catalog.md`, substrate in
  `docs/design/systems/effect_systems_design.md` §7, breakpoint **stat values
  authored in the plan (first pass)**. Open: breakpoint-value tuning, the Tier-B
  fidelity pass (Skyborn collision/tie + Stalker reposition ship as MVP proxies),
  and two-Kinship hybrids.
- D.9 Item system: **LOCKED — design in `docs/design/content/item_catalog.md`,
  implementation planned as T.29a/T.29b** (`docs/design/tasks/t29_item_engine_plan.md`).
  8 base components, 36 combined items via `RECIPE_MAP` (16-item core cut in
  T.29a, rest in T.29b), 6 emblems (Spirit Gem + component → Kinship; counted via
  T.28a), 6 special `RUN_ACTION_REGISTRY` items. 3 item slots per champion piece.
  Items acquired from REWARD-node drops, SUPPLY-node picks, and the prep shop.
  Open: Heartwood/radiant tier + component magnitude (% vs flat) tuning.
- D.10 Champion / enemy archetypes: the ~6-8 role archetypes and their `P = 1`
  base stats, enemy power tags, and the spirit roster (T.5 / T.18).
- D.11 Augment content: augment pool, 4 quality tiers, 3 scopes, and per-augment
  effects **owned by T.31** (substrate `effect_systems_design.md` §9, content
  `augment_catalog.md`, plan `t31_augment_system_plan.md`). Open tuning only: the
  per-stage quality-weight curve and a degenerate-combo (interaction-cap) audit.
- D.12 Drop tables: `REWARD`-node loot content (Amber / item / champion weights).
  **REWARD item drops integrated in T.29a** (seed-deterministic roll); the
  drop-table *weights* remain T.22/economy's to author.

### Economy & Meta

- D.13 Champion economy: **LOCKED — implemented in T.22.** Amber sources: +3
  base per node, +1-3 bonus on win (seed-deterministic), REWARD-node loot.
  Sinks: buy champion `Cost(T) = T` Amber, shop reroll = 1 Amber (first reroll
  each node is free), Tempest buy-up (`1 Amber : 1 Tempest`). Sell value:
  `floor(Cost / 2)` Amber per copy. Leveling: 3 copies → L2, 9 → L3
  (`Run.champion_copies`). **Interest [revised T.22]:** TFT-style +1 Amber per
  10 banked, cap +5 (computed on Amber held *before* node income) — supersedes
  the original "interest: none", added to deepen the save-vs-spend choice.
- D.14 Team-size cap: **LOCKED — implemented in T.22.** `Tempest` counter (the
  XP analogue) — start at rank `1` (field 1 + 2 bench = team-size 3), `+2`
  Tempest per fight (challenge clears +1 more). Rank-up thresholds are an
  **accelerating** curve (rank `N→N+1`): `1→2:2, 2→3:4, 3→4:6, 4→5:10, 5→6:14,
  6→7:18, 7→8:24, 8→9:30, 9→10:36`; reaching a threshold auto-ranks and overflow
  carries. Over ~38 combat nodes, free `+2`/fight tops out ~rank 7-8; ranks 9-10
  need the Amber rush (`1 Amber : 1 Tempest`, full remaining cost only,
  all-or-nothing). Max rank **10** (field cap == `tempest_rank`). [Was "max rank
  6"; corrected — shipped T.21 `CHALLENGE_TEAM_SIZE` stage-6 = 11 at design's
  `cap+1`/final`+2` implies cap ~10; code beat the spec.]
- D.15 Shop: **LOCKED — implemented in T.22.** Lives in the Prep view. 5 champion
  slots, auto-refreshed each node entry (free). Manual reroll costs 1 Amber; the
  first reroll each node is free (counter resets every node advance). Stage-gated
  tier probabilities: stage 1 sees Tier 1-2 only; stage 6 widens to Tier 1-9 with
  higher-tier weight. **Buyable ceiling is T9** — T10 Primordials stay boss-only,
  so "Tier 1-10" reads as "up to the buyable max T9". Probability table authored
  in `docs/design/tasks/t22_meta_progression_plan.md` and `shop.STAGE_TIER_WEIGHTS`.

### UI / Flow

- D.16 View/route drift: **RESOLVED.** Canonical routes are `/`, `/trail`,
  `/prep`, `/combat`, `/summary` — matching `views_spec.md`. The legacy
  `/recruit` and `/map` routes are retired; initial champion pick is handled
  inline during run-start (first Prep node). `views_spec.md` §11 node-type set
  updated to match `NodeType` enum (`fight`, `reward`, `augment`, `supply`,
  `challenge`, `boss_fight`).
- D.17 Cache health UX: warn indicator surface when any node is `substitute`
  or any `live` weather aged > 2h; hover shows affected cities; smart
  failsafe copy when many nodes degraded. Polish layer over T.7 cache states.

## Implementation Order

### Phase 1: Core Logic (Week 1-3)
T.1 → T.2 → T.3 → T.4 → T.18 → T.5 → T.19 → T.20 → T.21 → T.24 → T.26 → T.16 (game tests) → T.27 (playtest CLI)

### Phase 1b: Economy & Content Systems (Week 3-4) ← NEW critical path
T.22 (economy + shop) → T.28a → T.28b (traits) → T.29a → T.29b (items) → T.31 (augments)

### Phase 2: API + Data (Week 2-3)
T.6 → T.7 → T.16 (API tests)

### Phase 3: UI + Combat (Week 4-6)
T.8 → T.9 → T.10 → T.15 → T.23 → T.12

### Phase 4: Visualizations (Week 6-7)
T.11 → T.13

### Phase 5: Polish + Docs (Week 7-8)
T.14 → T.17

## Content Inspiration

### Weather States

Weather Favor stat packs per weather (the strong-tier `±10%` base; `combat_modifier`
scales the deviation by tier — see `docs/design/tasks/t2_weather_effects_plan.md`):

| State | OW IDs | Buff stats (self / predators) | Debuff stats (prey) |
|---|---|---|---|
| `CLEAR` | 800 | — (inert) | — (inert) |
| `CLOUDY` | 801-804 | `HP`, `RES` | `AS` |
| `MIST` | 701-781 | `MS`, `THR` | `attack_range -1` (min 1) |
| `SNOW` | 600-622 | `Armor`, `RES` | `MS` |
| `RAIN` | 300-321 + 500-531 | `AS`, `MR` | `STR` |
| `THUNDER` | 200-232 | `STR`, `AS` | `INT`, `MR` |

Directed predator/prey ring: `Mist → Cloudy → Rain → Snow → Thunder → Mist`.
Each weather preys on the previous ring members (primary = prev, secondary =
prev-prev). Weather Favor buffs self + predators, debuffs prey (§T.2 notes). Affinity Clash
multiplies every hit by the attacker-vs-defender ring relation. `Clear` is
outside the ring — inert in both systems. Full matrices in
`docs/design/tasks/t2_weather_effects_plan.md`.

> **Terminology**: `affinity` is the piece's single weather alignment (one of the 6 `WeatherState` values). `traits` are open-ended auto-chess synergy tags (e.g. `Hunter`, `Mammal`, `Reptile`, `Guardian`) — multiple per champion, used for team synergies. Do not confuse the two; weather logic only consumes `affinity`.

### Champions examples
| Name | Affinity | Synergy Traits | Role | Base ATK | Base HP |
|---|---|---|---|---|---|
| Blaze Fox | Clear | Mammal, Hunter | Attacker | 18 | 80 |
| Ember Salamander | Clear | Reptile, Mystic | Glass cannon | 22 | 60 |
| Drift Yak | Cloudy | Mammal, Guardian | Bruiser | 14 | 115 |
| Haze Owl | Mist | Bird, Mystic | Scout | 15 | 70 |
| Frost Wolf | Snow | Mammal, Hunter | Attacker | 17 | 85 |
| Tundra Bear | Snow | Mammal, Guardian | Bruiser | 15 | 110 |
| Tide Otter | Rain | Mammal, Mystic | Tank | 12 | 120 |
| Storm Eagle | Thunder | Bird, Hunter | Attacker | 16 | 75 |

T.5 expands this to a full roster of ~60 (1 champion per affinity × 10 tiers).

### Cities & route

The route is **6 continent stages, ~50 nodes, one distinct real city per node**
(`docs/design/tasks/t4_city_route_plan.md`). Each stage has an authored
**affinity** used by its boss/challenge encounters; each node/city carries its
own **live weather**. Boss cities, one per stage:

| Stage | Continent | Affinity | Boss city |
|---|---|---|---|
| 1 | Europe | Clear | Vienna |
| 2 | Africa | Mist | Cairo |
| 3 | Asia | Thunder | Tokyo |
| 4 | Oceania | Cloudy | Sydney |
| 5 | South America | Rain | Rio de Janeiro |
| 6 | North America | Snow | New York (grand boss) |

### Enemy Types examples
| Type | Base ATK | Base HP | Affinity |
|---|---|---|---|
| Frost Drone | 12 | 60 | Snow |
| Smog Bot | 14 | 70 | Cloudy |
| Heat Mech | 16 | 65 | Clear |
| Monsoon Walker | 13 | 80 | Rain |
| Storm Sentinel | 15 | 75 | Thunder |
