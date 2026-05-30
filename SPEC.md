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
- Team-size cap: **3** at rank 1 (field 1 champion, bench holds 2 spares); grows with Tempest rank up to **6** at max rank (see D.14).
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
- V.2: Combat is pure function — `resolve_combat(team, enemies, weather) -> BattleResult`. Single public entry point; the new ability/passive/status framework is invoked through it, never alongside it. `resolve_combat` internally delegates to `compile_loadout → CombatContext → combat/loop_new.run → BattleResultRecorder.build_result`. Boss fights use the same delegation chain but attach `map_effect_id` via `attach_map_effect` before running the loop (T.26).
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
| T.22 | Economy & shop — Amber income per node (+3 base, +1-3 win bonus), shop refresh (5 slots, auto-refresh each node, manual reroll 1 Amber, first reroll per node free), buy `Cost(T)=T`, sell `floor(Cost/2)`, team-size Tempest leveling (rank N costs 2N, max rank 6), stage-gated tier probabilities | `game/economy.py`, `game/shop.py`, `docs/design/tasks/t22_meta_progression_plan.md` | T.1, T.5, T.18 | L | 📋 Plan |
| T.23 | Prep formation snapshot integration — lock player board placement in Prep, validate deployment constraints, pass explicit coordinates into combat init | `ui/views/prep.py`, `game/models.py`, `game/combat.py`, `docs/design/tasks/t23_prep_formation_snapshot_plan.md` | T.1, T.3, T.15 | M | 📋 Plan |
| T.24 | Enemy formation policy — deterministic role-aware spawn planner (frontline forward, backline protected, size-aware packing) with safe fallback | `game/formation.py`, `game/combat.py`, `docs/design/tasks/t24_enemy_formation_plan.md` | T.3, T.5, T.23 | M | ✅ Done |
| T.25 | Power simulation & balance benchmarking — deterministic matchup sweeps and empirical power ratings | `tools/simulation/`, `docs/design/tasks/t25_power_simulation_plan.md` | T.3, T.5 | M | ✅ Done |
| T.26 | Combat engine unification — `resolve_combat` delegates to the new loop via `BattleResultRecorder`; legacy tick loop retired; Weather Favor applied in `compile_loadout` | `game/combat/legacy.py`, `game/combat/loop_new.py`, `game/combat/recorder.py`, `game/loadout.py` | T.3, T.20 | M | ✅ Done |
| T.27 | Playtesting CLI — dev-facing tools for sim_fight / sim_node / sim_run / inspect / inspect_node, no Flet, pure consumers of `src/game/` | `tools/playtest/`, `docs/design/playtesting/` | T.3, T.5, T.19, T.21, T.26 | M | ✅ Done |
| T.28 | Synergy trait effects — implement `TraitDef` / `TraitBreakpoint` types, `@register_trait` factories for all Kinship/Calling/Affinity traits, team roll-up step in `compile_loadout`, `BattleResult` activation events | `game/traits/`, `game/loadout.py`, `docs/design/content/trait_catalog.md` | T.5, T.20, T.26 | L | ❌ Not started |
| T.29 | Item engine — `Item`, `Component`, `ItemSlot` models, `RECIPE_MAP` (8 components → 36 combined), equip/unequip logic (3 slots per piece), `EffectBundle` factories per item, emblem Kinship grant, special-item run-actions, drop-table integration with REWARD nodes | `game/items.py`, `game/item_effects.py`, `docs/design/tasks/t29_item_engine_plan.md` | T.1, T.20, T.22 | L | ❌ Not started |

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

### T.18-T.29 Planning Notes (Systems Expansion)

- T.18 power scalar `P = 1.5 ** ((T-1)/2 + (L-1))` drives encounter budgets and
  piece stat generation; "two tiers == one level".
- T.19 generates encounters deterministically from `Run.seed` via per-node
  sub-seeds; squads/offers are regenerated lazily, not stored.
- T.20 builds the ability/passive/status framework (resolves D.3-D.5); bosses
  are its first consumer.
- T.21 layers spirit challenges and 2-phase bosses on the T.19 generator.
- T.22 implements the full economy loop: Amber income (+3 base/node, +1-3 win
  bonus), shop (5 slots, auto-refresh per node, reroll = 1 Amber, first free),
  buy/sell (`Cost(T) = T` / `floor(Cost/2)`), Tempest team-size leveling
  (rank N costs 2N Tempest, max rank 6), and stage-gated tier probabilities.
  Also covers augment/supply node resolution and augment pool.
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
  1 vs every piece on the losing team; draws split 0.5). Bradley-Terry MLE
  derives a latent β per piece, normalised so the weakest piece anchors at
  `β = 1.0` (plan §6.2).
- T.26 unified the two combat engines that briefly coexisted: legacy
  `resolve_combat` (T.3) and `compile_loadout + CombatContext + loop.run`
  (T.20). Post-T.26 there is **one** entry point — see V.2 and
  `docs/design/playtesting/engine_split.md` for the historical note.
- T.27 ships the dev-facing playtest CLI suite (`tools/playtest/`) used to
  exercise the engine before the Flet UI exists; pure consumer of
  `src/game/`. See `docs/design/playtesting/plan.md`.
- T.28 implements synergy trait breakpoint effects — the team-building payoff
  layer. Depends on T.22 for the economy that feeds champion acquisition.
- T.29 implements the item engine: `Item`/`Component` models, `RECIPE_MAP`,
  equip/unequip (3 slots/piece), per-item `EffectBundle` factories, emblem
  Kinship-grant, special-item run-actions, and REWARD-node drop integration.
  Content authored in `docs/design/content/item_catalog.md`; substrate spec'd
  in `docs/design/systems/effect_systems_design.md` §8.
- Detailed plans: `docs/design/tasks/t18_power_scaling_plan.md` through
  `docs/design/tasks/t25_power_simulation_plan.md`;
  `docs/design/playtesting/plan.md` covers T.27.

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
- D.2 Boss content: authored per-boss kits (phase 1 + phase 2 abilities, on-death
  hooks) **designed in T.21** — `game/bosses/data.py`. Ability *implementation*
  (handler functions) is still open; currently stubs in the registry.
- D.3 Combat board-cell modifiers: **designed and implemented in T.21** —
  `game/board.py` (BoardState + CellModifier), `game/map_effects.py` (6 effect
  classes), `game/combat/loop.py` (_process_board_state), `game/targeting.py`
  (fog filter). Remaining: per-ability content that writes to board_state.

### Combat Systems

- D.5 Ability / passive / status framework: **designed in T.20**; per-champion
  ability and passive *content* (kits) is still open.
- D.6 Combat timeout policy: keep hard draw only or add sudden-death escalation.
- D.7 HP carryover: **LOCKED — full reset per fight.** Champions heal to full HP
  between nodes. Simplifies economy tuning and avoids snowball/frustration; the
  challenge comes from enemy scaling and weather variance, not attrition.

### Content

- D.8 Synergy traits: V.8 reserves `Champion.traits` as auto-chess synergy tags.
  **Design complete** — breakpoints and bonuses authored in
  `docs/design/content/trait_catalog.md`; technical substrate in
  `docs/design/systems/effect_systems_design.md` §7. Implementation tracked as
  T.28.
- D.9 Item system: **LOCKED — design in `docs/design/content/item_catalog.md`**;
  implementation tracked as T.29. 8 base components, 36 combined items via
  `RECIPE_MAP`, 6 emblems (Spirit Gem + component → Kinship), 6 special
  run-action items. 3 item slots per champion piece. Items acquired from
  REWARD-node drops, SUPPLY-node picks, and the prep shop.
- D.10 Champion / enemy archetypes: the ~6-8 role archetypes and their `P = 1`
  base stats, enemy power tags, and the spirit roster (T.5 / T.18).
- D.11 Augment content: the augment pool, the 4 quality tiers, and per-augment
  effects (T.22).
- D.12 Drop tables: `REWARD`-node loot content (Amber / item / champion weights).

### Economy & Meta

- D.13 Champion economy: **LOCKED.** Amber sources: +3 base per node, +1-3
  bonus on win, REWARD-node loot. Sinks: buy champion `Cost(T) = T` Amber,
  shop reroll = 1 Amber (first reroll each node is free), Tempest buy-up
  (`1 Amber : 1 Tempest`). Sell value: `floor(Cost / 2)` Amber. Interest: none
  (keeps runs short).
- D.14 Team-size cap: `Tempest` counter (the XP analogue) — start at rank `1`
  (field 1 + 2 bench = team-size 3), `+2` Tempest per fight, raise rank `N` at
  `2N` Tempest; Amber can complete a rank-up instantly at `1 Amber : 1 Tempest`,
  full remaining cost only, all-or-nothing (T.22). Max rank **6** (field 6
  pieces).
- D.15 Shop: **LOCKED.** Lives in the Prep view. 5 champion slots, auto-refreshed
  each node entry (free). Manual reroll costs 1 Amber; the first reroll each
  node is free (counter resets every node advance). Stage-gated tier
  probabilities: stage 1 sees Tier 1-2 only; stage 6 sees Tier 1-10 with
  higher-tier weight. Exact probability table authored in
  `docs/design/tasks/t22_meta_progression_plan.md`.

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
T.22 (economy + shop) → T.28 (traits) → T.29 (items)

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
