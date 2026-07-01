# Architecture & Systems Guide

How Tempest Fauna Trail is built, how the systems fit together, and **where to find
each one in the code**. This is the map for understanding the game and finding your
way around the repo.

> **How the docs relate.** [SPEC.md](SPEC.md) is the *contract* (goals, invariants
> `§V`, task table `§T`, bug log `§B`) — the source of truth for *what must hold*.
> [CLAUDE.md](CLAUDE.md) is the *agent quick-start*. The [journal](docs/journal/) is
> the *narrative* — why decisions were made. **This file is the *system map*** — what
> exists, how it interacts, and the file you open to touch it. When in doubt about a
> rule, SPEC wins; when lost in the tree, start here.

---

## 1. What the game is

A roguelike **auto-battler** (TFT-inspired) themed around animal spirits and weather.
You pick **1 champion**, start with **10 Amber**, and travel a fixed **50-node route**
of real-world cities across 6 continent stages. **Live OpenWeather data** at each city
warps combat. Battles are **tick-based and auto-resolved** — all player agency happens
*between* fights.

**The per-node loop** (SPEC §G):

```
 Trail  ──▶  Prep  ──▶  Combat  ──▶  (rewards: Amber / items / Tempest XP)  ──▶  next node
 view route   shop, board    auto-resolved
 + preview    placement,      tick battle
 weather      level team
```

The player's decisions: **team composition + synergy traits**, **item optimization**,
**weather-aware roster swaps**, **board positioning**. The engine then resolves the
fight deterministically.

---

## 2. The layered architecture

Four source layers under `src/`, plus dev tooling under `tools/`. The **cardinal rule
is dependency direction** — everything points *inward* toward pure game logic:

```
            ┌─────────────────────────────────────────────┐
   tools/   │  playtest CLI  ·  power simulation           │  dev-only, import game/ only
            └───────────────────────┬─────────────────────┘
   ui/  ────────────────────┐       │        ┌──────────  api/  (OpenWeather, cache, refresher)
   (Flet views,             ▼       ▼        ▼            threads only
    components, theme)   ┌─────────────────────────┐
                         │        game/            │   PURE LOGIC — zero Flet, zero I/O
                         │  models, combat, weather │   (V.1)
                         │  content, economy, ...   │
                         └─────────────────────────┘
   viz/  (charts, canvas — stub today)
```

**Invariants that enforce this** (SPEC §V):

| Rule | Invariant |
|---|---|
| `game/` has **zero Flet imports** — pure logic | V.1 |
| `tools/simulation/` imports only from `src/game/` (no `ui/`, no `api/`) | V.14 |
| All HTTP runs on a worker `threading.Thread`, never the main thread | V.4 |
| API failure never crashes — leaves a node `unknown`/`substitute`, keeps retrying | V.3 |

Because `game/` is pure and I/O-free, the **entire game is testable and simulatable
without a UI or network** — which is exactly what `tools/` exploits.

---

## 3. The combat engine — the heart of the system

Combat is a **single pure function** (V.2):

```python
resolve_combat(team, enemies, weather, *, run_mods=None, node_id="") -> BattleResult
```

Identical inputs → byte-identical output. No RNG, no clock, no globals. The optional
`run_mods` (a `RunModifiers` from `game/augments.py`, T.31) threads active augments +
quest state into the fight; it **defaults to `None`**, so every legacy caller and every
sim stays byte-for-byte unchanged (V.2). It internally delegates through a fixed chain
(the shared `build_combat` helper in `resolve.py`):

```
compile_loadout(team, enemies, weather, run_mods)   # content ↔ combat boundary
        │  → (pieces, EventBus, trait_activations)
        ▼
CombatContext(pieces, bus, weather, seed)    # the mutator API (board_state optional)
        │
        ▼
combat/engine.run(ctx)                        # the ONE tick loop (V.29)
        │  events ──▶ EventBus
        ▼
BattleResultRecorder.build_result()          # rebuilds BattleResult from events
```

Boss fights insert one extra step — `attach_map_effect(...)` after building the context
and before `run()`. The canonical wiring is **`src/game/combat/resolve.py::resolve_boss_combat`**
(T.12b/V.59 — the single src-side boss entry, takes a `map_effect_id: str` so `combat/`
stays content-import-free; `tools/playtest/_common` delegates to it). `CombatReplay`/
`inspect_at_tick` accept the same `map_effect_id` to replay a boss fight.

### 3.1 Where each piece lives

| Concern | File |
|---|---|
| Public entry (`resolve_combat`) + the shared `build_combat` wiring helper (compile → assign_spawns → context, optional recorder) reused by resolve / boss / replay | `src/game/combat/resolve.py` |
| Package re-exports (`resolve_combat`, `CombatContext`, `run`, `inspect_at_tick`, `CombatReplay`) | `src/game/combat/__init__.py` |
| **The tick loop** — the single `_step_combat` generator (energy meters, pathing, attacks, casts, statuses, map effects, sudden death) + tuning constants; `run` drains it, `CombatReplay` steps it forward (T.37c) | `src/game/combat/engine.py` |
| **Mutator API** — the *only* way content touches the world | `src/game/combat/context.py` |
| Event → `BattleResult` reconstruction (beats + `initial_pieces` board snapshot) | `src/game/combat/recorder.py` |
| **Replay** — `CombatReplay` steps the engine **forward** for playback; `inspect_at_tick` re-runs to a tick (random seek) on a cloned `run_mods`; both return read-only `PieceView`s, record nothing (V.55); the live state is the view's resource truth, not the event stream (V.56/V.57, B.28) | `src/game/combat/replay.py` |
| Compile models → combat `Piece`s + wire passives/weather/**traits**/augments; **uniquifies duplicate piece ids** so twins in a squad get distinct `id`s (`id`, `id#1`, …) for stable combat-view/log references (B.65) | `src/game/loadout.py` |
| **Synergy traits** — `TraitScope`/`TraitBreakpoint`/`DynamicThreshold`, `@register_trait`, `_resolve_traits` (unique-id count, affinity synthesis, apex/dynamic threshold) applied in `compile_loadout` step 3 (T.28a; primitives T.28b/c) | `src/game/traits/` |

> **V.29 — there is exactly one tick loop.** `engine.py` is it. The old `loop.py` was
> deleted after the T.26 unification; do not reintroduce a parallel engine (see the
> [2026-06-04 journal](docs/journal/2026-06-04_barriers_engine_unification_weather_metric_fix.md)).

### 3.2 The tick model

Time is discretized into **10ms ticks**. A piece acts when its **action energy meter**
overflows `ENERGY_THRESHOLD`; movement uses a separate meter. One action ≈ **~600 ticks
(~6s)** — this scale matters: it's why DOT fires on a *per-status cadence*, not per tick
(V.25). Meter overflow carries over, and triggered meters resolve in a **deterministic
order** so replays stay identical.

### 3.3 The ability / passive / status framework (T.20)

Content (abilities, passives, items, traits, augments) never mutates combat state
directly. It plugs in through three declarative primitives, then reacts through events:

- **`EffectBundle`** (`effects.py`) — a bag of `Modifier`s, `Hook`s, granted statuses /
  abilities / traits. The unit of "what this thing does."
- **`Modifier`** (`effects.py`) — a stat change with a `Lifetime` (PERMANENT / COMBAT /
  TIMED). Stats are computed via `compute_stat` layering base + modifiers.
- **`Hook`** (`effects.py`) — a callback subscribed to the **`EventBus`** by `event`
  name, with a `HookScope` dedup (`PER_HIT` / `ONCE_PER_CAST` / `ONCE_PER_TARGET` /
  `ONCE_PER_COMBAT`). Real event names the loop emits include `on_attack_landed`,
  `on_attack_start`, `on_damage_pre` / `on_damage_dealt` / `on_damage_taken`,
  `on_cast` / `on_cast_complete`, `on_death`, `on_kill`, `on_heal`, `on_tick`,
  `on_status_applied` / `on_status_expired`, `on_spawn`, `on_combat_start` /
  `on_combat_end`. Typed payloads live in `events.py` (`AttackEvent`, `DamageEvent`, …).
- **Registries** (`registries.py`) — `ABILITY_REGISTRY` (144) + `PASSIVE_REGISTRY` (147)
  + `TRAIT_REGISTRY` (25, T.28+Multicaster) + `ITEM_REGISTRY` (50, T.29a-d)
  + `RUN_ACTION_REGISTRY` (5, T.29b) + `AUGMENT_REGISTRY` (54, T.31 — populated by
  `game/augments.py`, alongside a `QUEST_TRACKER_REGISTRY` for quest-scoped augments).
  Content factories self-register via `@register_*` decorators; importing the content
  package triggers them. Lookups are by **string id**.
- **Presentation layer** (`registries.py` + `ability_text.py`, T.34/T.35) — a parallel
  `ABILITY_META` (285 ids) gives every roster ability a tooltip. Numeric outlets flow
  through the **closed `Magnitude` family** (`ScalingTerm` linear / `PctResource` /
  `MaxOfTerm` / `SetByCaller`, GAS-modeled, V.46): the handler reads the number via
  `term.eval(...)` and `ability_text.render` renders the *same* object (source-of-truth B,
  V.38 — tooltip can't drift from combat). Pure, no Flet (V.1). An AST guard
  (`test_no_orphan_stat_reads`) fails the build on any handler stat-read not backed by a
  `Magnitude`.
- **Description render-layer** (`game/describe.py` + `items/meta.py` + `traits/meta.py`, T.41)
  — the same pattern for **champion-independent** content (items + traits): `RenderedEntry` /
  `RenderedTrait` (name + blurb + stat line) from a per-domain `*_META` (authored name/blurb,
  transcribed from the design catalogs; trait rung counts reconciled to code, V.79). The
  **stat line is derived from the live numbers** — introspected from the item's `EffectBundle`
  (V.78) or from `traits/_packs.TRAIT_STAT_PACKS` (V.79), never re-typed, so it can't drift;
  no `Magnitude` machinery (these grant fixed %, not caster-scaled). Pure, no Flet, no mutation
  (V.80). Consumed by the Prep item chips + the `trait_synergies_panel` tooltips (Prep + Combat).

> **V.15 / V.22 / V.17 / V.38 / V.46 / V.47 — every id resolves + every scaler is visible.**
> Any `ability_id`, `passive_id`, `trait` tag, or augment id referenced by content data must
> resolve in its registry; every ability id must have an `ABILITY_META`; every handler stat
> read must be a `Magnitude`; an `int`/`hybrid` unit must read INT in its kit. All CI-guarded.

The **`CombatContext`** (`context.py`) is the single mutation point: `ctx.deal_damage`,
`ctx.apply_status`, `ctx.grant_barrier`, `ctx.heal`, `ctx.register_bundle`, etc. "Direct
mutation architecture" — no effect-as-data reducer.

### 3.4 Statuses, DOT, and barriers

- **Statuses** (`status.py`, `piece.py`) — id-based, **one `StatusInstance` per
  `status_id` per piece** (V.26, non-stacking identity; intensity that should accumulate
  uses `StackBehaviour.STACK`, e.g. poison). Carry gates (stun → can't act), DOT info,
  and stacks.
- **DOT cadence** (V.25) — DOT damage + stack decay fire on a **per-status clock**
  (`dot_interval_ticks`, default 100t = 1s), *not* every engine tick. The clock
  free-runs (re-applying never resets the next tick). Stack decay is **percentage**
  (`decay_fraction`), giving an investment-scaling equilibrium with **no hard cap** —
  see [journal](docs/journal/2026-06-03_dot_cadence_and_focus_fire.md) and the
  *no-hard-caps* balance philosophy.
- **Barriers** (V.28, `piece.py`) — a temporary absorb pool **distinct from HP and from
  "shield"**. Soaked before HP inside `deal_damage`, FIFO, optional tick expiry, granted
  only via `ctx.grant_barrier`. "Shield" in content ids means an armor/resistance *buff*,
  a different mechanic — do not conflate.

---

## 4. The two weather systems (T.2)

`src/game/weather_effects.py` — **two decoupled systems**, never summed:

1. **Weather Favor** (`combat_modifier`) — does the *node weather* suit
   my affinity? A 5-tier stat buff/debuff applied **once at combat init**, in the
   single application path `compile_loadout::_apply_weather_to_piece`.
2. **Affinity Clash** (`damage_modifier`) — do *I* beat *this enemy*? A per-hit damage
   multiplier by attacker-affinity vs defender-affinity, resolved **per hit** in the loop
   (it depends on the defender, so it can't be pre-snapshotted).

Both run off the **single `affinity: WeatherState` field** every piece carries (V.6 —
there is no separate weakness field). `CLEAR` sits outside the predator/prey ring and is
inert in both. The 6 weather states (V.5) map 1:1 to OpenWeather id groups.

---

## 5. Content layer — champions, enemies, bosses, abilities

| Concern | File |
|---|---|
| Champion / enemy rosters + base-stat template + level scaling | `src/game/content.py` |
| Champion ability/passive handlers (~60 champions) | `src/game/abilities/champions.py` |
| Enemy ability/passive handlers (~60 enemies) | `src/game/abilities/enemies.py` |
| Boss kits — 6 two-phase bosses | `src/game/abilities/bosses.py` |
| Boss definitions, supporting cast, phase/death hooks | `src/game/bosses/data.py` |
| Boss **map effects** (decoupled board hazards) | `src/game/map_effects.py`, `src/game/board.py` |
| Ability tooltips — `AbilityMeta` + `Magnitude` family + renderer (T.34/T.35) | `src/game/registries.py`, `src/game/ability_text.py` |
| Synergy traits (Kinship / Calling / Affinity) | `docs/design/content/trait_catalog.md` → `game/traits/` (T.28 ✅) |
| Items | `game/items/` (T.29a-d ✅ — components, combined, emblems, special run-actions, mana primitive, multi-slot) |
| Augments | `game/augments.py` (T.31 ✅ — model + ~50 catalog + offers/reroll; picked in-game at AUGMENT nodes via `ui/views/augment.py` + `economy.resolve_nonfight_node`, T.42a) |

Content **vocabulary lives with content** (V.8): synergy tags are open-ended strings the
engine treats as opaque labels. The roster has a history of drifting from the catalog
docs (e.g. `CALLING_TAGS` once carried dead tags) — always diff code vocabulary against
`docs/design/content/*_catalog.md` and add a V-guard (see CLAUDE.md planning rules).

---

## 6. Power & scaling model (T.18)

`src/game/scaling.py` — one formula governs all power:

```
P(T, L) = 2 ^ ((T-1)/3 + triplings(L))     triplings = {L1:0, L2:1, L3:3}
```

Stat multiplier is **√P** so that HP·DPS (≈ combat value) grows *linearly* with P,
keeping encounter budgets linear. Level-ups use a **tripling** mechanic (3 copies →
next level), giving an accelerating curve (L2 modest, L3 a spike). Total T1L1→T10L3 ≈
**8× in stats**. Tier-10 "Primordials" are boss-only — the buyable ceiling is T9.

---

## 7. Route & encounter generation

| Concern | File |
|---|---|
| Fixed 50-node route, 6 stages, city coords + enemy pools | `src/game/route.py` |
| Seed-deterministic squads for FIGHT/REWARD/CHALLENGE/BOSS | `src/game/encounter.py` |
| Role-aware enemy board placement | `src/game/formation.py` |

**Determinism doctrine** (V.19 + the T.19 contract): all "randomness" derives from
`(run_seed, node_index, channel)` — no clock, no global RNG. Same seed → same route
draws, same squads, same shop, same economy. This is what makes the simulation layer
trustworthy. Enemy formation (`formation.py`) is fully deterministic and role-aware
(tanks col 7, bruisers col 8, backline col 9, bosses authored positions).

---

## 8. Economy & shop (T.22)

| Concern | File |
|---|---|
| Amber income, interest, Tempest progression; **node-result orchestrators** (`apply_node_result` for fights, `resolve_nonfight_node` for AUGMENT/SUPPLY, V.83) + CHALLENGE recruit | `src/game/economy.py` |
| Stage-gated tier rolls, buy / sell / reroll, SUPPLY free-recruit offer | `src/game/shop.py` |
| Item equip/unequip seam (`Run.inventory` ↔ `Champion.items`, auto-combine on double-equip, V.63) | `src/game/inventory.py` |
| Augments — `Augment`/`RunModifiers` model, ~54 catalog, offer/reroll, `apply_augment` | `src/game/augments.py` |

Currency is **Amber**; team-size XP is **Tempest** (rank = deployable board cap, 1→10,
**monotonic non-decreasing**, V.20). Shop offers are seed-deterministic
`(run_seed, visit_index, reroll_count)` (V.19). These are the **headless economy
substrate** the live Prep / Reward / Augment / Supply views drive: the view chooses,
the game mutates (V.63), and the producer autosaves after (V.65). A non-fight node
grants no income/Tempest and touches no Hearts — its pick (augment or supply recruit)
is applied by the view, then `resolve_nonfight_node` marks the node cleared + advances.

---

## 9. Data models & run state (T.1)

`src/game/models.py` — all dataclasses (`slots=True`), JSON-serializable:

- `WeatherState`, `NodeType`, `NodeState`, `RunStatus`, `CombatOutcome` (enums)
- `Champion`, `Enemy` — roster/source models (carry `affinity`, `traits`, stats, ability
  ids)
- `Node` — one route stop
- `BattleEvent`, `BattleResult` — combat output + event stream (the runtime combat
  entity is `Piece` in `piece.py`, built by the loadout compiler)
- **`Run`** — the single object holding *all* game state (current node, roster, battle
  log, Amber, Tempest, augments). Per V: one `Run` is the whole game.

`src/game/save.py` (T.14) — the **file-I/O layer** over that contract: `save_run`
(atomic temp+`os.replace`), `load_run` (`schema_version` gate → `Run.from_dict`),
`default_save_dir`, `CURRENT_SCHEMA_VERSION`, and typed errors (`SaveError` /
`CorruptSaveError` / `UnsupportedSchemaError`). No Flet import (V.1); the
(de)serialization contract itself stays on the dataclasses. See
[docs/live/systems/save.md](docs/live/systems/save.md).

---

## 10. API layer (T.6 + T.7)

| Concern | File |
|---|---|
| OpenWeather client — fetch by lat/lon, parse → `WeatherState` | `src/api/weather.py` |
| Stateless per-city cache (`unknown` / `live`+`fetched_at` / `substitute`) | `src/api/cache.py` |
| 3-stream tick refresher (≤3 calls/min) | `src/api/refresher.py` |

The refresher ticks 1/min and fires three deduped streams (A: full round-robin 50;
B: window `[current+1..+6]`; C: uniform random) → bounded API usage, staleness ≤ 50 min
(V.11). On fetch failure a node falls back to the city's `default_weather` flagged
`substitute` (V.3, V.13). Key via `OPENWEATHER_API_KEY`, **never logged** (V.3). All HTTP
on a worker thread (V.4).

**Persistence (T.39, V.73).** The cache is the fetch-scheduling/freshness layer; the
**persisted source of truth is the `Run` `Node`**: each node carries `weather` (the
effective game weather — `default_weather` placeholder until a live fetch overwrites it),
`weather_state: NodeWeatherState` {`unknown`/`live`/`substitute`}, and `weather_locked`.
The Trail writes fetched cache values onto the `Run` via the pure game-side mutators
`Run.set_node_live_weather` / `Run.lock_node_weather` only (cache/refresher stay stateless
re: game, V.10). The **current** node's weather **locks at the Trail→Prep transition** (frozen
for the run; refresher skips locked nodes) — so live weather reaches combat (Weather Favor,
CHALLENGE rolls) while staying byte-identical across the fight + reward (load-bearing for V.70).

---

## 11. UI & visualization — the full run loop is live

The player-facing Flet UI is built end-to-end: menu → run-start → the per-node loop
(trail → prep → combat → reward, plus augment / supply nodes) → run summary.

| Concern | File | Status |
|---|---|---|
| Design tokens (colors, type, spacing, animation) | `src/ui/theme.py` | ✅ T.8 |
| Shared components — champion card, weather badge, meter bar, chips, **shared infocard** (Prep + Combat), **trait-synergy panel**, **hex board geometry**, **iconography glyphs** | `src/ui/components/` | ✅ T.8/T.12d/T.23a |
| Pure Flet-free combat-playback model over the replay backend | `src/ui/combat_playback.py` | ✅ T.12a |
| Flet entry point — menu-rooted `page.views` shell + full run router | `src/main.py` | ✅ T.9/T.42 |
| Main menu (`/`) — New Run / **Continue** (loads latest save into Trail, T.15b) / Playfight / Quit / Settings | `src/ui/views/menu.py` | ✅ T.9 |
| RunStart (`/run-start`) — seed-deterministic 1-of-3 champion pick → `Run` | `src/game/run_init.py`, `src/ui/views/run_start.py` | ✅ T.10 |
| Trail (`/trail`) — route map + node focus + team summary + live weather | `src/ui/views/trail.py` | ✅ T.11 |
| Prep (`/prep`) — shop, hex-board placement, item equip, trait preview | `src/ui/views/prep.py` | ✅ T.23 |
| Combat view + dev/Playfight harness | `src/ui/views/combat.py`, `dev_harness.py` | ✅ T.12 |
| Reward (`/reward`) — post-fight node-result panel + CHALLENGE recruit | `src/ui/views/reward.py` | ✅ T.15a/T.38 |
| Augment (`/augment`) — 1-of-3 pick + reroll at AUGMENT nodes | `src/ui/views/augment.py` | ✅ T.42a |
| Supply (`/supply`) — 1-of-5 free-recruit at SUPPLY nodes | `src/ui/views/supply.py` | ✅ T.42b |
| Run summary (`/summary`) — run-end screen + damage chart | `src/ui/views/summary.py` | ✅ T.13 |
| Settings — set OpenWeather API key in-app | `src/ui/views/settings.py`, `src/app_config.py` | ✅ |
| Playtest admin panel (dev) | `src/ui/views/admin.py` | dev tool |
| Route map + run-summary chart + affinity-clash heatmap — all **hand-drawn `flet.canvas`** (V.72) | `src/viz/route_map.py`, `run_summary.py`, `affinity_clash_heatmap.py` | ✅ T.11/T.13 |

`main.py` is the menu-rooted `page.views` shell and the run router. **New Run** opens
RunStart (`game/run_init.new_run`) → champion pick → `Run` → Trail. **Continue** loads
the most-recent save into the Trail (T.15b; a corrupt save is skipped). From the Trail,
`_play_node` dispatches by `node.node_type`: fight nodes go Prep → Combat → Reward →
back to Trail; non-fight nodes go to the Augment or Supply view then `resolve_nonfight_node`
→ Trail. **Playfight** opens the combat dev harness → combat view. `TEMPEST_ADMIN=1`
opens the admin panel and `TEMPEST_DEV=1` jumps straight to Playfight.

The **combat view is pure presentation over the replay backend** (V.56): it drives the
Flet-free `combat_playback` model and the `CombatReplay` forward-stepper — it records
nothing and re-derives no formation, laying out from the recorder's `initial_pieces`
snapshot. See [SPEC §I Flet Routes](SPEC.md) and `views_spec.md`; Flet conventions live
in [.claude/rules/flet-ui.md](.claude/rules/flet-ui.md) and CLAUDE.md.

---

## 12. Dev tooling — how to drive the game without a UI

Because `game/` is pure, two toolkits exercise it directly:

### Playtest CLI (`tools/playtest/`, T.27) — interactive inspection
```bash
uv run python -m tools.playtest.sim_fight --help     # one fight
uv run python -m tools.playtest.sim_node ...          # a node encounter
uv run python -m tools.playtest.sim_run ...           # a full run
uv run python -m tools.playtest.inspect ...           # roster inspection
uv run python -m tools.playtest.inspect_node ...
```
`_common.py` holds shared helpers; `resolve_boss_combat` now delegates to the
src-side `combat/resolve.py` entry (V.59).

### Power simulation (`tools/simulation/`, T.25) — balance benchmarking
- `matchup.py` — `run_matchup`, the pure unit of work (safe in worker processes)
- `tournament.py` — battle generators (1v1, team2, sampled teams)
- `runner.py` — CLI entry (`python -m tools.simulation.runner --mode 1v1 ...`)
- `mega.py` — runs every sweep flavour in one parallelized go
- `ratings.py` — win-rate + power-model metrics, incl. cross-weather `weather_metrics`
- `report.py` — CSV / console output
- `stat_edge.py`, `weather_impact.py` — focused single-axis sweeps (stat lead, weather swing)

Root-level dev scripts: `tools/export_roster.py` (dump the roster) and
`tools/gen_role_matrix.py` (role-coverage matrix).

> **Sim metric invariants:** weather-affinity metrics are **cross-weather** (V.16) and
> **treat absent weather as NaN, never 0** (V.30) — averaging missing-as-0 once
> fabricated a balance signal (B.12). Sim outputs land in `results/` (gitignored);
> published analyses live in `reviews/`.

---

## 13. Determinism doctrine (read this before touching combat or content)

Determinism is non-negotiable (V.2, V.14, V.19). The simulation and replay systems
depend on it:

- **No RNG in mechanics.** Any "chance" / "every few hits" effect uses a **deterministic
  cadence counter** (like `crit_counter`), never `random`.
- **All procedural generation** derives from `(run_seed, node_index, channel)`.
- **`resolve_combat` is pure** — same inputs, byte-identical `BattleResult`. Its T.31
  `run_mods` arg defaults to `None`, leaving every existing caller (and every sim)
  byte-for-byte unchanged (V.2).
- **State for a view is recomputed, not recorded (V.55).** The `CombatReplay` forward
  stepper (playback) and `inspect_at_tick` (random seek) drive the same single
  `_step_combat` generator to read any piece's live state at any tick — no per-tick
  keyframes in `BattleResult`. Same purity contract: they clone `run_mods` so the replay
  can't mutate the caller's quest state. This live state is the combat view's resource
  truth, **not** the event stream's partial `hp_after` (V.56/V.57, B.28).
- **Verify with:** fixed seed + `workers=1` → identical output across runs.

---

## 14. "Where do I find X?" — quick index

| I want to… | Go to |
|---|---|
| Change how a fight resolves | `src/game/combat/engine.py` |
| Add/modify what content can do to the world | `src/game/combat/context.py` (mutator API) |
| Add a champion/enemy ability | `src/game/abilities/{champions,enemies}.py` + register |
| Add a boss | `src/game/bosses/data.py` + `src/game/abilities/bosses.py` + `src/game/map_effects.py` |
| Tune stats / scaling | `src/game/content.py`, `src/game/scaling.py` |
| Change weather effects | `src/game/weather_effects.py` |
| Edit the route / cities | `src/game/route.py` |
| Change enemy generation | `src/game/encounter.py`, `src/game/formation.py` |
| Touch the economy / shop | `src/game/economy.py`, `src/game/shop.py` |
| Add / change an augment | `src/game/augments.py` (+ register), `src/ui/views/augment.py` |
| Add / change an item; equip logic | `src/game/items/`, `src/game/inventory.py` |
| Add a data field to game state | `src/game/models.py` (`Run`, `Champion`, …) |
| Change save/load | `src/game/save.py` (run) · `src/app_config.py` (settings) |
| Change weather fetching / caching | `src/api/{weather,cache,refresher}.py` |
| Build / edit a UI screen | `src/ui/views/` (+ `theme.py`, `components/`) |
| Change the run flow / routing | `src/main.py` (menu shell + `_play_node` dispatch) |
| Balance-test a change | `tools/simulation/` |
| Manually try a fight/run | `tools/playtest/` |
| Understand *why* a decision was made | `docs/journal/` |
| Know what rule must hold | [SPEC.md](SPEC.md) §V |

---

## 15. End-to-end: what happens in one fight

1. Player advances to a node; `encounter.py` generates the enemy squad from the seed;
   `formation.py` places them; the node's weather is read from the persisted `Node`
   (`node.weather` — live values written through from the cache while on the Trail, then
   **frozen by the Prep-entry lock**, T.39/V.73).
2. `resolve_combat(team, enemies, weather, run_mods=...)` is called (`run_mods` carries
   the run's active augments + quest state; `None` for sims/Playfight).
3. `compile_loadout` builds runtime `Piece`s (uniquifying duplicate ids, B.65), applies
   **Weather Favor** to base stats, resolves **synergy traits**, folds in augments,
   subscribes passive `Hook`s to a fresh `EventBus`, wires boss phase/death hooks.
4. `CombatContext` wraps the pieces + bus + board; bosses `attach_map_effect`.
5. `engine.run(ctx)` ticks: meters fill → pieces move (BFS pathing) / auto-attack /
   cast abilities; every damage instance applies **Affinity Clash**; statuses tick on
   their cadence; barriers soak; map effects fire; sudden-death timeout guards stalls.
   Every action emits a typed event onto the bus.
6. `BattleResultRecorder` (subscribed to the bus) reconstructs a `BattleResult` —
   outcome, survivors, the full beat stream (move/attack/cast/death + heal/dot/
   status/spawn/despawn, each beat one event with `hp_after`/`barrier_after` for
   HP-changing ones, T.37a) and an `initial_pieces` board snapshot + board dims so
   a combat view can lay out and animate the fight without re-deriving formation.
7. `economy.apply_node_result` folds the outcome into the `Run` — battle log, Amber /
   Tempest income, Hearts on a loss — the Reward view shows the panel (plus any CHALLENGE
   recruit), the producer autosaves (V.65), and the Trail reopens on the next node. (A
   non-fight node instead runs its Augment/Supply pick → `resolve_nonfight_node`.)

---

## 16. Reading order for a newcomer

1. **This file** — the map.
2. [SPEC.md](SPEC.md) §G (goal), §V (invariants) — the rules.
3. `src/game/models.py` — the vocabulary.
4. `src/game/combat/engine.py` + `context.py` — the engine.
5. `src/game/abilities/champions.py` — see content plug into the framework.
6. Run `tools/playtest/sim_fight` — watch a fight resolve.
7. [docs/journal/](docs/journal/) — the "why" behind the non-obvious choices.

For per-system design depth, see the [Documentation Map in CLAUDE.md](CLAUDE.md) and
`docs/design/`. For the status of any task, see [SPEC.md §T](SPEC.md).
