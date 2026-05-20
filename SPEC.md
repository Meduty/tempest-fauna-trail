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
- Response: `weather[0].main` → game weather state mapping
- Weather IDs: 200-232 Thunderstorm, 500-531 Rain, 600-622 Snow, 800 Clear, 801-804 Clouds
- Icon URL: `https://openweathermap.org/img/wn/{icon}@2x.png`

### Internal Data Flow
```
OpenWeather API → WeatherClient → cache.json
                                ↓
Route (6 cities) → Node[weather] → Combat(team, enemies, weather) → BattleResult
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
- V.5: Weather state enum: exactly 5 values (Clear, Rain, Storm, Heat, Cold)
- V.6: Each champion has exactly one weather affinity from V.5
- V.7: Route is fixed sequence of 6 cities + 1 boss city = 7 nodes total

## T. Tasks

| # | Task | Files | Depends | Est |
|---|---|---|---|---|
| T.1 | Data models — Champion, Enemy, Node, Run, BattleResult, WeatherState | `game/models.py` | — | S |
| T.2 | Weather effects — modifier lookup dict per WeatherState | `game/weather_effects.py` | T.1 | S |
| T.3 | Combat engine — turn-by-turn auto-resolve, apply weather modifiers | `game/combat.py` | T.1, T.2 | M |
| T.4 | City route — define 6+1 cities with coordinates, enemy pools | `game/route.py` | T.1 | S |
| T.5 | Content — define 8 champions, 5 enemy types with stats | `game/content.py` | T.1 | S |
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
| T.16 | Unit tests — combat, weather effects, API parsing | `tests/` | T.1-T.7 | M |
| T.17 | Documentation — README, prompting strategy, flow chart | `README.md`, `docs/` | all | M |

**Size**: S = <1h, M = 1-3h, L = 3-6h

## B. Bugs / Backprop

*(Empty — populated during development)*

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

## Content Definitions

### Weather States
| State | Condition IDs | Combat Effect |
|---|---|---|
| Clear | 800 | Fire +20% ATK, normal for others |
| Rain | 300-531 | Water +20% ATK, Fire -20% ATK |
| Storm | 200-232 | Air +20% ATK, all accuracy -10% |
| Heat | temp>35°C | Fire +30% ATK, Water -10% ATK |
| Cold | 600-622 or temp<0°C | Ice +20% ATK, movement speed -15% |

### Champions (8 total, 1 affinity each)
| Name | Affinity | Role | Base ATK | Base HP |
|---|---|---|---|---|
| Blaze Fox | Clear | Attacker | 18 | 80 |
| Storm Eagle | Storm | Attacker | 16 | 75 |
| Tide Otter | Rain | Tank | 12 | 120 |
| Frost Wolf | Cold | Attacker | 17 | 85 |
| Ember Salamander | Clear | Glass cannon | 22 | 60 |
| Gale Falcon | Storm | Speed | 14 | 70 |
| Coral Tortoise | Rain | Tank | 10 | 140 |
| Tundra Bear | Cold | Bruiser | 15 | 110 |

### Cities (6 + boss)
| Order | City | Region | Enemy Theme |
|---|---|---|---|
| 1 | Reykjavik | Iceland | Frost drones |
| 2 | London | UK | Smog bots |
| 3 | Cairo | Egypt | Heat mechs |
| 4 | Mumbai | India | Monsoon walkers |
| 5 | Tokyo | Japan | Storm sentinels |
| 6 | Sydney | Australia | Wildfire units |
| Boss | New York | USA | All-weather titan |

### Enemy Types (5)
| Type | Base ATK | Base HP | Weather Weakness |
|---|---|---|---|
| Frost Drone | 12 | 60 | Heat |
| Smog Bot | 14 | 70 | Storm |
| Heat Mech | 16 | 65 | Rain |
| Monsoon Walker | 13 | 80 | Cold |
| Storm Sentinel | 15 | 75 | Clear |
