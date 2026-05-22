# Tempest Fauna Trail — Implementation Spec

## G. Goal

Roguelike strategy game: animal champions travel fixed route of ~6 real cities.
Live OpenWeather data at each city shapes combat modifiers. Auto-resolved battles.
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
| `/` | Main Menu | New game, load, quit |
| `/recruit` | Team Builder | Pick ~3 champions from roster of 8 |
| `/map` | Route Map | Canvas map with weather icons per city |
| `/combat` | Battle | Auto-resolved combat with animated log |
| `/summary` | Run Summary | BarChart of damage per battle, win/loss |

## V. Invariants

- V.1: `game/` has zero Flet imports — pure logic, no UI coupling
- V.2: Combat is pure function — `resolve_combat(team, enemies, weather) -> BattleResult`
- V.3: API failure never crashes app — fallback to cached data or Clear weather
- V.4: All HTTP calls run on `threading.Thread`, never main thread
- V.5: Weather state enum: exactly 6 values (Clear, Cloudy, Mist, Rain, Snow, Thunder), mapped 1:1 to OpenWeather id main groups
- V.6: Each piece (Champion, Enemy, CombatPieceState) carries exactly one `affinity: WeatherState` field; it drives both weather systems (node-weather buff/debuff and the affinity damage triangle) — there is no separate weakness field
- V.8: `Champion.traits: list[str]` holds auto-chess synergy tags (Hunter, Mammal, Reptile, etc.). Distinct from `affinity`. Synergy tags are open-ended strings owned by content (T.5); engine treats them as opaque labels for grouping.
- V.7: Route is a staged path with multiple stages (one per continent, up to 6), with one or more nodes per stage and a final boss fight node in a famous city.

## T. Tasks

| # | Task | Files | Depends | Est |
|---|---|---|---|---|
| T.1 | Data models — Champion, Enemy, Node, Run, BattleResult, WeatherState + NodeType/NodeState + combat runtime state + JSON serialization helpers | `game/models.py`, `docs/design/tasks/t1_data_models_plan.md`, `docs/design/tasks/t1_model_contracts.md` | — | M |
| T.2 | Weather effects — directional predator/prey ring; two decoupled systems (node-weather buff/debuff + affinity damage triangle), per-weather stat packs, shop weight, `apply_weather` for combat init | `game/weather_effects.py`, `docs/design/tasks/t2_weather_effects_plan.md` | T.1 | M |
| T.3 | Combat engine — tick-based auto-resolve (10ms tick simulation), apply weather modifiers | `game/combat.py` | T.1, T.2 | M |
| T.4 | City route — ~50 cities (one per node) across 6 staged continents, coordinates, stage affinity, enemy pools | `game/route.py` | T.1 | M |
| T.5 | Content — define champion roster (target: 1 per affinity × 10 tiers = ~60 champions; MVP cut OK) + ~5 enemy types with stats + synergy trait catalog | `game/content.py` | T.1 | M |
| T.6 | OpenWeather client — fetch current weather, parse to WeatherState | `api/weather.py` | T.1 | S |
| T.7 | Cache layer — JSON file cache with 1h TTL | `api/cache.py` | T.6 | S |
| T.8 | Theme + shared components — colors, fonts, champion card, weather badge | `ui/theme.py`, `ui/components/` | — | S |
| T.9 | Main menu view — new game, load game, quit | `ui/views/menu.py`, `main.py` | T.8 | S |
| T.10 | Team recruit view — pick 3 champions from roster | `ui/views/recruit.py` | T.5, T.8 | M |
| T.11 | Route map visualization — Canvas with city nodes + weather icons | `viz/route_map.py`, `ui/views/map.py` | T.4, T.6, T.8 | L |
| T.12 | Combat view — animated battle log, HP bars | `ui/views/combat.py` | T.3, T.8 | L |
| T.13 | Run summary visualization — BarChart of damage per battle | `viz/run_summary.py`, `ui/views/summary.py` | T.3, T.8 | M |
| T.14 | Save/load — JSON serialization of Run state | `game/save.py` | T.1 | S |
| T.15 | Routing + app wiring — connect all views in main.py | `main.py` | T.9-T.13 | M |
| T.16 | Unit tests — combat, weather effects, API parsing | `tests/` | T.1, T.2, T.3, T.6, T.7 | M |
| T.17 | Documentation — README, prompting strategy, flow chart | `README.md`, `docs/` | all | M |
| T.18 | Power & scaling model — `P` formula, `√P` stat coupling, economy cost curve | `game/scaling.py`, `docs/design/tasks/t18_power_scaling_plan.md` | T.1 | S |
| T.19 | Encounter generation — seed-deterministic squad/offer fill, enemy power clustering, node budgets | `game/encounter.py`, `docs/design/tasks/t19_encounter_generation_plan.md` | T.1, T.4, T.5, T.18 | M |
| T.20 | Ability/passive/status framework — registry, typed event bus, status gates, boss phase hook | `game/abilities.py`, `game/combat.py`, `docs/design/tasks/t20_ability_framework_plan.md` | T.3 | L |
| T.21 | Challenge & boss encounters — spirit challenges, 2-phase bosses, weather-themed map effects | `game/encounter.py`, `game/content.py`, `docs/design/tasks/t21_challenge_boss_plan.md` | T.19, T.20 | M |
| T.22 | Meta progression — augment, supply, economy, team-size cap | `game/augments.py`, `game/economy.py`, `docs/design/tasks/t22_meta_progression_plan.md` | T.1, T.18 | M |
| T.23 | Prep formation snapshot integration — lock player board placement in Prep, validate deployment constraints, pass explicit coordinates into combat init | `ui/views/prep.py`, `game/models.py`, `game/combat.py`, `docs/design/tasks/t23_prep_formation_snapshot_plan.md` | T.1, T.3, T.15 | M |
| T.24 | Enemy formation policy — deterministic role-aware spawn planner (frontline forward, backline protected, size-aware packing) with safe fallback | `game/formation.py`, `game/combat.py`, `docs/design/tasks/t24_enemy_formation_plan.md` | T.3, T.5, T.23 | M |

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
  - **System A — node weather**: buffs/debuffs each piece by its affinity vs the node weather. 5 tiers — strong/medium/weak buff (self / primary predator / secondary predator) at `+10/+6/+3%`, medium/weak debuff (primary/secondary prey) at `−6/−3%`. Self is the strict maximum; no strong debuff. Applied once at combat init.
  - **System B — affinity damage triangle**: per-hit multiplier on every damage instance by attacker affinity vs defender affinity — `1.10/1.05/1.00/0.95/0.90` for primary predator / secondary predator / mirror or Clear / secondary prey / primary prey. Resolved per hit in the combat engine.
- `Mist` System-A debuff is the only flat-integer effect: base `attack_range -1` (min 1), which scales/rounds to `-1` at medium tier and `0` at weak tier.
- Detailed T.2 plan: `docs/design/tasks/t2_weather_effects_plan.md`.

### T.4 Planning Notes

- Route locked: 6 continent stages, 50 linear nodes, one distinct city per node;
  each stage carries an authored affinity (one per `WeatherState`).
- Detailed T.4 plan: `docs/design/tasks/t4_city_route_plan.md`.

### T.18-T.24 Planning Notes (Systems Expansion)

- T.18 power scalar `P = 1.5 ** ((T-1)/2 + (L-1))` drives encounter budgets and
  piece stat generation; "two tiers == one level".
- T.19 generates encounters deterministically from `Run.seed` via per-node
  sub-seeds; squads/offers are regenerated lazily, not stored.
- T.20 builds the ability/passive/status framework (resolves D.3-D.5); bosses
  are its first consumer.
- T.21 layers spirit challenges and 2-phase bosses on the T.19 generator.
- T.22 covers augment/supply choices, the Amber economy, and team-size cap.
- T.23 makes Prep placement authoritative: board coordinates from Prep become
  combat init input; combat no longer overwrites player layout when a valid
  placement snapshot is provided.
- T.24 introduces deterministic enemy formation heuristics by role and team
  size, replacing index-only right-side packing while preserving replay
  determinism.
- Detailed plans: `docs/design/tasks/t18_power_scaling_plan.md` through
  `t24_enemy_formation_plan.md`.

## B. Bugs / Backprop

- B.1 `NodeType` extended with `SUPPLY` and `CHALLENGE` for the T.4 route
  vocabulary; `docs/design/tasks/t1_model_contracts.md` must be synced.
- B.2 `Reward` node redefined as an easy fight with guaranteed loot — it carries
  both `enemy_pool_id` and `reward_table_id`, not a pure non-combat node.
- B.3 Planned model additions: `CombatPieceState.active_statuses` (T.20) and
  `Run.content_version` (T.19) for procedural-run save stability.
- B.5 Weather rework (T.2 revision): `CombatPieceState` gains an `affinity:
  WeatherState` field — the combat engine needs per-piece affinity at damage
  time for System B (target-dependent, cannot be pre-snapshotted). The shipped
  `combat.py` damage step gains a System-B multiplier hook; `apply_modifier` is
  renamed `apply_weather`. Touches `models.py`, `to_dict`/`from_dict`,
  `combat.py`, `t1_model_contracts.md`, `test_models.py`, `test_combat.py`.
- B.4 Currency named **Amber**, the team-size XP counter named **Tempest**
  (`1 Amber : 1 Tempest`). The `Run.gold` model field should be renamed
  `Run.amber` — touches `models.py`, `to_dict`/`from_dict`, `test_models.py`,
  and `t1_model_contracts.md`.

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

## D. Systems Yet To Be Determined

Live backlog of big design decisions still open. Items now locked are recorded
in their T-task plan docs; what remains here is genuinely undecided.

### Route & Encounters

- D.1 Route branching: the linear 6-stage / 50-node chain is **locked** (T.4);
  whether optional branch/merge paths are added post-MVP is open.
- D.2 Boss content: per-boss kits, phase-2 ability pairs, exact map-effect
  mechanics (T.21).
- D.3 Combat board-cell modifiers: boss map effects need a new combat-engine
  cell-modifier mechanic — not yet a task, not yet designed.

### Combat Systems

- D.5 Ability / passive / status framework: **designed in T.20**; per-champion
  ability and passive *content* (kits) is still open.
- D.6 Combat timeout policy: keep hard draw only or add sudden-death escalation.
- D.7 HP carryover: whether champion HP persists across nodes or resets per
  fight (`views_spec.md` Trail panel assumes "carry-over if persistent").

### Content

- D.8 Synergy traits: V.8 reserves `Champion.traits` as auto-chess synergy tags,
  but which synergies exist and what bonuses they grant is undesigned.
- D.9 Item system: items are referenced by `SUPPLY` combos, `REWARD` drops, and
  the prep inventory, but no item model, pool, or effects exist — undesigned.
- D.10 Champion / enemy archetypes: the ~6-8 role archetypes and their `P = 1`
  base stats, enemy power tags, and the spirit roster (T.5 / T.18).
- D.11 Augment content: the augment pool, the 4 quality tiers, and per-augment
  effects (T.22).
- D.12 Drop tables: `REWARD`-node loot content (Amber / item / champion weights).

### Economy & Meta

- D.13 Champion economy: Amber sources/sinks, `Cost(T) = T` tuning, reroll costs
  (augment reroll is free once; shop reroll undecided), and sell values.
- D.14 Team-size cap: `Tempest` counter (the XP analogue) — start at rank `1`,
  `+2` Tempest per fight, raise rank `N` at `2N` Tempest; Amber can complete a
  rank-up instantly at `1 Amber : 1 Tempest`, full remaining cost only,
  all-or-nothing (T.22).
- D.15 Shop: lives in the Prep view (`views_spec.md` §6.4); its inventory model,
  refresh rule, and stage availability gating are open (T.22).

### UI / Flow

- D.16 View/route drift: SPEC's Flet route table (`/recruit`, `/map`,
  `/summary`) is stale against `views_spec.md` (`/trail`, `/prep`); a single
  canonical route set must be chosen. `views_spec.md` §11 is also stale
  (7-node route, 4-value `NodeType`) and needs a sync pass.

## Implementation Order

### Phase 1: Core Logic (Week 1-3)
T.1 → T.2 → T.3 → T.4 → T.18 → T.5 → T.19 → T.20 → T.21 → T.24 → T.16 (game tests)

### Phase 2: API + Data (Week 2-3)
T.6 → T.7 → T.16 (API tests)

### Phase 3: UI + Combat (Week 3-5)
T.8 → T.9 → T.10 → T.12 → T.15 → T.23

### Phase 4: Visualizations (Week 5-7)
T.11 → T.13

### Phase 5: Polish + Docs (Week 7-8)
T.14 → T.17

## Content Inspiration

### Weather States

System-A stat packs per weather (the strong-tier `±10%` base; `combat_modifier`
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
prev-prev). System A buffs self + predators, debuffs prey (§T.2 notes). System B
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
