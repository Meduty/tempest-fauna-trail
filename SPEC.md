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
- V.6: Each piece (Champion, Enemy) has exactly one `affinity: WeatherState` field; weakness derives from `weather_effects.DEBUFFED_AFFINITIES`
- V.8: `Champion.traits: list[str]` holds auto-chess synergy tags (Hunter, Mammal, Reptile, etc.). Distinct from `affinity`. Synergy tags are open-ended strings owned by content (T.5); engine treats them as opaque labels for grouping.
- V.7: Route is a staged path with multiple stages (target up to 5), with one or more nodes per stage and a final boss fight node in a famous city.

## T. Tasks

| # | Task | Files | Depends | Est |
|---|---|---|---|---|
| T.1 | Data models — Champion, Enemy, Node, Run, BattleResult, WeatherState + NodeType/NodeState + combat runtime state + JSON serialization helpers | `game/models.py`, `docs/design/t1_data_models_plan.md`, `docs/design/t1_model_contracts.md` | — | M |
| T.2 | Weather effects — pentagon affinity matrix (Variant B), per-weather buff/debuff stat packs, shop weight, `apply_modifier` for combat init | `game/weather_effects.py`, `docs/design/t2_weather_effects_plan.md` | T.1 | M |
| T.3 | Combat engine — tick-based auto-resolve (10ms tick simulation), apply weather modifiers | `game/combat.py` | T.1, T.2 | M |
| T.4 | City route — define 6+1 cities with coordinates, enemy pools | `game/route.py` | T.1 | S |
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

**Size**: S = <1h, M = 1-3h, L = 3-6h

### T.1 Planning Notes

- T.1 now includes non-combat node typing (`fight`, `reward`, `augment`, `boss_fight`) so route and UI flows can share one node contract.
- T.1 now includes combat runtime model surfaces needed by the combat proposal.
- T.1 now includes JSON-friendly serialization contracts to reduce risk for T.14 save/load.
- Detailed T.1 execution plan: `docs/design/t1_data_models_plan.md`
- Detailed model schema contracts: `docs/design/t1_model_contracts.md`

### T.2 Planning Notes

- Pentagon cycle of 5 active weathers (`Cloudy → Mist → Snow → Rain → Thunder`) + `Clear` as universal neutral.
- Variant B relationship: each active weather buffs self + 2 cycle neighbours (3 affinities), debuffs 2 diagonals (mutual). All active-active edges either mutual-buff or mutual-debuff (K5).
- Magnitudes flat ±10% (anti-stack ceiling ~30% team boost with 3 stacked buffed pieces). `Mist` debuff is the only flat-integer effect: `attack_range -1` (min 1).
- Modifier applies at combat init only (one-shot snapshot, not per-tick).
- Detailed T.2 plan: `docs/design/t2_weather_effects_plan.md`.

## B. Bugs / Backprop

*(Empty — populated during development)*

## D. Systems Yet To Be Determined

- D.1 Route topology details: exact stage count (up to 5), nodes per stage, and branch/merge rules.
- D.2 Boss city/content: final famous city choice, boss enemy kit, and finale weather behavior.
- D.3 Ability framework: piece-specific active ability handlers and registration model.
- D.4 Passive framework: event taxonomy (`on_hit`, `on_cast`, `on_kill`, etc.) and deterministic resolution order.
- D.5 Status effects: formal mechanics for `stun`, `silence`, `disarm`, and `root` (meter, action, movement, and mana interactions).
- D.6 Combat timeout policy: keep hard draw only or introduce sudden-death escalation.

## Implementation Order

### Phase 1: Core Logic (Week 1-2)
T.1 → T.2 → T.3 → T.4 → T.5 → T.16 (game tests)

### Phase 2: API + Data (Week 2-3)
T.6 → T.7 → T.16 (API tests)

### Phase 3: UI + Combat (Week 3-5)
T.8 → T.9 → T.10 → T.12 → T.15

### Phase 4: Visualizations (Week 5-7)
T.11 → T.13

### Phase 5: Polish + Docs (Week 7-8)
T.14 → T.17

## Content Inspiration

### Weather States
| State | OW IDs | Buff (applied to 3 affinities: self + 2 neighbours) | Debuff (applied to 2 diagonal affinities) |
|---|---|---|---|
| `CLEAR` | 800 | — (inert) | — (inert) |
| `CLOUDY` | 801-804 | `HP ×1.10`, `RES ×1.10` | `AS ×0.90` |
| `MIST` | 701-781 | `MS ×1.10`, `THR ×1.10` | `attack_range -1` (min 1) |
| `SNOW` | 600-622 | `Armor ×1.10`, `RES ×1.10` | `MS ×0.90` |
| `RAIN` | 300-321 + 500-531 | `AS ×1.10`, `MR ×1.10` | `STR ×0.90` |
| `THUNDER` | 200-232 | `STR ×1.10`, `AS ×1.10` | `INT ×0.90`, `MR ×0.90` |

Pentagon cycle (CW): `Cloudy → Mist → Snow → Rain → Thunder → Cloudy`. Each active weather buffs self + 2 cycle neighbours; debuffs 2 diagonals. `Clear` is universal neutral (affinity + weather). Full matrix and rationale in `docs/design/t2_weather_effects_plan.md`.

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

### Cities examples
| Order | City | Region | Enemy Theme |
|---|---|---|---|
| 1 | Reykjavik | Iceland | Frost drones |
| 2 | London | UK | Smog bots |
| 3 | Cairo | Egypt | Heat mechs |
| 4 | Mumbai | India | Monsoon walkers |
| 5 | Tokyo | Japan | Storm sentinels |
| 6 | Sydney | Australia | Wildfire units |
| Boss | New York | USA | All-weather titan |

### Enemy Types examples
| Type | Base ATK | Base HP | Affinity |
|---|---|---|---|
| Frost Drone | 12 | 60 | Snow |
| Smog Bot | 14 | 70 | Cloudy |
| Heat Mech | 16 | 65 | Clear |
| Monsoon Walker | 13 | 80 | Rain |
| Storm Sentinel | 15 | 75 | Thunder |
