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
resolve_combat(team, enemies, weather, *, node_id="") -> BattleResult
```

Identical inputs → byte-identical output. No RNG, no clock, no globals. (SPEC V.2 also
specifies an optional `run_mods: RunModifiers` arg for active augments — that's the
planned **T.31** extension and is *not yet in the code*; today's signature is the one
above.) It internally delegates through a fixed chain:

```
compile_loadout(team, enemies, weather)      # content ↔ combat boundary
        │  → (pieces, EventBus)
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
and before `run()` (see `tools/playtest/_common.py::resolve_boss_combat`, the canonical
wiring).

### 3.1 Where each piece lives

| Concern | File |
|---|---|
| Public entry (`resolve_combat`) — wires loadout → context → engine → recorder | `src/game/combat/resolve.py` |
| Package re-exports (`resolve_combat`, `CombatContext`, `run`) | `src/game/combat/__init__.py` |
| **The tick loop** (energy meters, pathing, attacks, casts, statuses, map effects, sudden death) + tuning constants (coeffs, tick sizes) | `src/game/combat/engine.py` |
| **Mutator API** — the *only* way content touches the world | `src/game/combat/context.py` |
| Event → `BattleResult` reconstruction | `src/game/combat/recorder.py` |
| Compile models → combat `Piece`s + wire passives/weather | `src/game/loadout.py` |

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
- **Registries** (`registries.py`) — `ABILITY_REGISTRY` + `PASSIVE_REGISTRY` are
  populated; `ITEM_REGISTRY` / `TRAIT_REGISTRY` / `AUGMENT_REGISTRY` exist as empty
  scaffolds awaiting their content (T.28 / T.29 / T.31). Content factories self-register
  via `@register_*` decorators; importing the content package triggers them. Lookups are
  by **string id**.

> **V.15 / V.22 / V.17 — every id resolves.** Any `ability_id`, `passive_id`, `trait`
> tag, or augment id referenced by content data must resolve in its registry, enforced
> by CI guard tests. A typo'd id fails the suite, not silently no-ops.

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
| Synergy traits (Kinship / Calling / Affinity) | `docs/design/content/trait_catalog.md` → `game/traits/` (T.28, planned) |
| Items, augments | `game/items/` (T.29), `game/augments.py` (T.31) — planned |

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
| Amber income, interest, Tempest team-size progression | `src/game/economy.py` |
| Stage-gated tier rolls, buy / sell / reroll | `src/game/shop.py` |

Currency is **Amber**; team-size XP is **Tempest** (rank = deployable board cap, 1→10,
**monotonic non-decreasing**, V.20). Shop offers are seed-deterministic
`(run_seed, visit_index, reroll_count)` (V.19). These are the **headless economy
substrate** the (planned) Prep UI will drive.

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

---

## 11. UI & visualization (mostly planned)

| Concern | File | Status |
|---|---|---|
| Design tokens (colors, type, spacing, animation) | `src/ui/theme.py` | ✅ T.8 |
| Shared components (champion card, weather badge, meter bar, chips) | `src/ui/components/` | ✅ T.8 |
| Playtest admin panel (dev) | `src/ui/views/admin.py` | dev tool |
| Flet entry point | `src/main.py` | placeholder shell + admin |
| Menu / Trail / Prep / Combat / Summary views | `src/ui/views/` | 📋 T.9–T.15 |
| Route map (Canvas), run summary (BarChart) | `src/viz/` | 📋 T.11, T.13 (stub) |

**The game logic is essentially complete; the player-facing Flet UI is the largest
remaining build.** `main.py` today is a placeholder counter + an admin panel
(`TEMPEST_ADMIN=1`). See [SPEC §I Flet Routes](SPEC.md) and `views_spec.md`. Flet
conventions live in [.claude/rules/flet-ui.md](.claude/rules/flet-ui.md) and CLAUDE.md.

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
`_common.py` holds shared helpers incl. `resolve_boss_combat` (the canonical
map-effect wiring).

### Power simulation (`tools/simulation/`, T.25) — balance benchmarking
- `matchup.py` — `run_matchup`, the pure unit of work (safe in worker processes)
- `tournament.py` — battle generators (1v1, team2, sampled teams)
- `runner.py` — CLI entry (`python -m tools.simulation.runner --mode 1v1 ...`)
- `mega.py` — runs every sweep flavour in one parallelized go
- `ratings.py` — win-rate + power-model metrics, incl. cross-weather `weather_metrics`
- `report.py` — CSV / console output

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
- **`resolve_combat` is pure** — same inputs, byte-identical `BattleResult`. When the
  T.31 `run_mods` arg lands it must default to `None`, leaving every existing caller (and
  every sim) byte-for-byte unchanged (V.2).
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
| Add a data field to game state | `src/game/models.py` (`Run`, `Champion`, …) |
| Change weather fetching / caching | `src/api/{weather,cache,refresher}.py` |
| Build a UI screen | `src/ui/views/` (+ `theme.py`, `components/`) |
| Balance-test a change | `tools/simulation/` |
| Manually try a fight/run | `tools/playtest/` |
| Understand *why* a decision was made | `docs/journal/` |
| Know what rule must hold | [SPEC.md](SPEC.md) §V |

---

## 15. End-to-end: what happens in one fight

1. Player advances to a node; `encounter.py` generates the enemy squad from the seed;
   `formation.py` places them; the node's weather is read (from `Run`'s frozen snapshot,
   or fetched + locked via the API layer).
2. `resolve_combat(team, enemies, weather)` is called.
3. `compile_loadout` builds runtime `Piece`s, applies **Weather Favor** to base stats,
   subscribes passive `Hook`s to a fresh `EventBus`, wires boss phase/death hooks.
4. `CombatContext` wraps the pieces + bus + board; bosses `attach_map_effect`.
5. `engine.run(ctx)` ticks: meters fill → pieces move (BFS pathing) / auto-attack /
   cast abilities; every damage instance applies **Affinity Clash**; statuses tick on
   their cadence; barriers soak; map effects fire; sudden-death timeout guards stalls.
   Every action emits a typed event onto the bus.
6. `BattleResultRecorder` (subscribed to the bus) reconstructs a `BattleResult` —
   outcome, survivors, full event stream.
7. The result flows to `Run.battle_log`; rewards (Amber / items / Tempest) are applied;
   the next node opens.

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
