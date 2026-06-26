# T.39 Plan — Persistent live node weather + Prep-entry lock

> **Status:** plan — ready for review. **New §T row** (T.39) — needs `/spec` to add it. Not a status flip.
> **Depends:** T.7 (cache + refresher, done), T.11 (Trail view + live weather, done), T.14 (save/load, done), T.38 (node rewards / `generate_node_reward`, done). All built — this is a behaviour correction + persistence layer over them, no unbuilt deps.
> **Resolves:** the reported bug — Trail weather does not persist (resets to `?` on every Trail re-open, never saved). Implements the long-dormant **V.12/V.13** lock that T.7 specced but no code ever wired, reconciled with the T.11 **V.66** display contract.
> **Design source of truth:** `docs/design/tasks/t4_city_route_plan.md` §1.1 (stage-affinity vs node-weather), §2 (`default_weather` = placeholder, T6 overwrites with live); `docs/design/tasks/t7_cache_refresher_plan.md` §3.3–3.4 (locking into `Run`, advance-to-unknown); `docs/design/tasks/t19_encounter_generation_plan.md` §3.4 (squad theming reads **stage affinity**, not live weather); SPEC §V.9–V.13, V.66, V.67, V.69, V.70, V.71; `docs/journal/2026-06-24_t11_trail_view.md` (the V.66 deviation).
> **What this plan adds beyond those:** the actual lock wiring (never built), the **persisted node-weather lifecycle** (`weather_state` + `weather_locked` on `Node`, save round-trip), the **cache→Run write-through** that makes weather survive navigation + Save&Exit, and the proof that locking is **load-bearing for V.70** once `node.weather` becomes mutable.

## 1. Scope

**In scope**
- `game/models.py` — `Node` gains a persisted weather lifecycle (`weather_state: NodeWeatherState`, `weather_locked: bool`); `to_dict`/`from_dict` round-trip (back-compat `.get` defaults, no schema bump); `Run` gains pure mutators `set_node_live_weather(...)` + `lock_node_weather(...)`.
- `game/` write-through helper so the refresher's fetched values land on the `Run` (V.10-safe: a game-side function does the write, the cache never touches game state).
- `ui/views/trail.py` — `_weather_status` reads the **persisted `Node`** (source of truth) instead of the ephemeral cache; on each refresher tick + kickstart, write-through cache→`Run` for **unlocked** nodes; lock the current node at the Trail→Prep transition (`on_play_next`).
- `main.py` — ensure the lock + a save fire at the Prep-entry boundary (the locked value must be durable, V.65).
- Tests: lifecycle/persistence round-trip, lock semantics, refresher-skips-locked, V.70 byte-identity under a mid-fight refresh, determinism (sims byte-identical).
- `docs/live/systems/ui.md` + `docs/live/systems/weather_api.md` updates.

**Out of scope (why)**
- **Per-tick disk autosave.** Weather write-through mutates the in-memory `Run` only; disk persistence rides the existing autosave points (node boundary, Save&Exit, on-lock — V.65). Per-fetch `save_run` would hammer the disk every ~20 s for no gain (a crash just re-fetches).
- **Changing FIGHT squad generation.** FIGHT theming already reads `stage.affinity` only (`encounter.py:382`); live weather never touched it and won't now.
- **Sync-fetch-on-lock as a hard requirement.** The Trail's open-time kickstart already eagerly fetches the current node (`trail.py:355`), so by Prep-entry it is normally LIVE/SUBSTITUTE. Mandatory sync fetch at lock is proposed as an overridable refinement (§7), not MVP — it would plumb the `WeatherClient` into the transition for a rare edge.
- **Stage affinity.** Authored, fixed, unaffected.

## 2. The gap today

| Piece | Where (`file.py:line`) | State |
|---|---|---|
| `WeatherCache` rebuilt fresh every Trail open → all nodes back to UNKNOWN `?` | `ui/views/trail.py:78` | 🔴 root cause |
| `_weather_status` reads the **ephemeral cache**, not the `Run` | `ui/views/trail.py:85-96` | 🔴 no persistence source |
| Live weather **never written back** to `Run`; cache discarded on pop | `ui/views/trail.py` (no write-through) | ❌ missing |
| `Node.weather` set once to `city_def.default_weather`, never overwritten by live | `game/route.py:370`, `game/models.py:361` | 🔴 T4 §2 says T6 should overwrite with live |
| Node has **no** persisted weather lifecycle (can't tell "fetched live" from "default placeholder") | `game/models.py:356-397` | ❌ missing |
| **Lock** (V.12/V.13) — snapshot weather into `Run`, freeze, refresher-skip | nowhere — grep clean | ❌ never built |
| Combat/encounter/reward all read `node.weather` (= static default) | `prep.py:149,314`, `encounter.py:919,975` | 🔶 works, but pinned to default not live |
| V.66 decouples display from logic, pins logic to `default_weather` | SPEC L152; `journal/2026-06-24_t11_trail_view.md` | 🔶 deliberate T.11 deviation, now superseded |

## 3. Architecture

### 3.1 The corrected weather model (matches T4 §1.1, the original intent)

Two independent properties, never conflated:

| Property | Granularity | Source | Read by |
|---|---|---|---|
| **Stage affinity** | per stage (6) | authored, fixed | boss/challenge theming + the 50% squad slot (`encounter._affinity_slots`, `generate_challenge`) |
| **Node weather** | per node (~50) | **live** OpenWeather; `default_weather` = placeholder until fetched | combat Weather Favor; CHALLENGE 30% live-weather slot; CHALLENGE reward roll |

`node.weather` **is** the live value (T4 §2: "T6 overwrites each node's weather with live data"). The static-default combat path is the T.11 (V.66) deviation we are now correcting. **Systems stay unaware of the lock** — they read `node.weather` exactly as today; locking only changes *when that value stops mutating*.

### 3.2 `Node` lifecycle (new, `game/models.py:356`)

```python
class NodeWeatherState(str, Enum):   # new enum, game-local (do NOT import api.cache.CacheState — cycle)
    UNKNOWN = "unknown"      # never fetched; node.weather holds the default placeholder → display "?"
    LIVE = "live"            # last successful fetch
    SUBSTITUTE = "substitute"  # fetch failed → holding default_weather, display flags "fallback"

@dataclass(slots=True)
class Node:
    ...
    weather: WeatherState                      # EFFECTIVE game weather. default → live → frozen on lock.
    weather_state: NodeWeatherState = NodeWeatherState.UNKNOWN   # display + lifecycle marker (persisted)
    weather_locked: bool = False               # frozen: refresher skips; value is final for the run (persisted)
```

- **Display keys off `weather_state`** (tri-state, V.66 preserved); **game logic keys off the `weather` value** (always a valid `WeatherState`, defaulting safely even at UNKNOWN — V.13 fallback). The decouple V.66 introduced stays; only the *logic value* is now allowed to be live.
- `to_dict` adds the two fields; `from_dict` reads them with `.get` defaults (`UNKNOWN` / `False`) → **pre-T.39 saves load unchanged**, re-fetch live on next Trail open. **No `CURRENT_SCHEMA_VERSION` bump** (the `.get` back-compat path, `save.py:112`).

### 3.3 Mutators (pure, `game/`, V.1/V.10-safe)

Two `Run` methods (or a `game/` helper module) — the **only** sanctioned weather mutators (extends V.63's "UI mutates `Run` only through `game/` functions"):

- `set_node_live_weather(node_index, weather, *, is_substitute)` — for an **unlocked** node: set `node.weather = weather`, `node.weather_state = SUBSTITUTE if is_substitute else LIVE`. **No-op on a locked node.** Idempotent, no I/O.
- `lock_node_weather(node_index)` — if not already locked: set `weather_locked = True`. If `weather_state is UNKNOWN` (never fetched — no key / fetch not landed), freeze the default placeholder as a fallback: `weather_state = SUBSTITUTE` (V.13 fail path, no client needed). Returns the frozen `WeatherState`.

The **cache/refresher never call these** — a game-side caller does (V.10 intact: `api/` stays stateless re: game). The write happens from the Trail's `on_tick`/kickstart (which already runs game-side glue).

### 3.4 Write-through + display switch (`ui/views/trail.py`)

- `_weather_status(node)` now reads **`node.weather_state` + `node.weather`** (the persisted `Run`), **not** `cache.get(...)`. → fixes the reset bug directly: on Trail re-open the `Run` still holds last-known weather, so already-fetched nodes never flash back to `?`.
- On each refresher tick (`on_tick`) and the kickstart fetch: for every fetched city, read `cache.get(city_id)` and `run.set_node_live_weather(node_index, entry.result.state, is_substitute = entry.state is SUBSTITUTE)`. Locked nodes are skipped by the mutator. Then `_schedule_render()` (V.67 marshalling unchanged).
- The cache keeps its T.7 role (3-stream scheduling, `fetched_at` freshness, dedup); it just feeds the write-through. It may still be rebuilt per Trail open (harmless now — the `Run` is the source of truth; the cache re-warms while the display already shows persisted values).

### 3.5 Lock trigger — at Trail→Prep (`on_play_next` / `main._push_prep`)

The lock fires when the player commits to the current node's fight — **entering Prep** (user's refined timing: only the current node, only on Prep-entry; all other nodes keep refreshing). Wiring:

- In the Trail's `on_play_next(node)` handler (Trail still owns cache+client here), call `run.lock_node_weather(run.current_node_index)` **before** handing off to Prep.
- `main._push_prep` (or the Save&Exit path) triggers a `save_run` so the locked value is durable (V.65: the boundary save must capture every mutation that boundary produces — the lock is one).

Refresher write-through thereafter skips the locked node, so its weather is final for the rest of the run, even across reload (saved) and replay.

### 3.6 Why the lock is load-bearing for V.70 (not just UX)

Once `node.weather` is **mutable/live**, a refresher tick landing **between** `node_encounter` (CHALLENGE squad built at Prep, `encounter.py:919`) and `generate_node_reward` (reward rolled at resolve, `encounter.py:975`) would change `node.weather` and make the CHALLENGE squad's 30% live-weather slot disagree with the reward roll — **violating V.70's byte-identical guarantee**. **Locking the current node at Prep-entry is precisely what re-establishes V.70:** both reads see the same frozen value. This converts the lock from a nice-to-have into an invariant requirement, and is the core reconciliation of this task.

### 3.7 Determinism / reproducibility (V.2/V.14 hold)

- `resolve_combat(team, enemies, weather)` purity unchanged — it is a function of its inputs; the producer just passes the (now possibly live, locked) `node.weather`.
- **Combat-view replay (V.55)** re-runs `resolve_combat` with the **saved** `node.weather` → byte-identical.
- **Continue-after-load (V.69)** — income/tempest/reward are seeded off `(seed, node_index)`, weather-independent; CHALLENGE reward reads the **saved locked** `node.weather` → reproduces exactly.
- **Sims / balance (V.14/V.16/V.25)** pass explicit weather and never touch the live cache or `Run` node weather → **byte-identical, untouched**.
- FIGHT previews on the Trail stay deterministic (stage affinity). **CHALLENGE previews now track live weather** (intended per T19 §3.4) — a knowing, documented change to V.66's "deterministic preview" clause for challenge nodes only.

## 4. Decisions that need stating

1. **`node.weather` is the live/effective value (mutated in place); a separate `weather_state` marks freshness.** Rationale: honours "systems read `node.weather` unaware of the lock" with zero churn at the ~6 read sites; the marker carries the only thing the value can't (never-fetched vs real). Alternative (separate `live_weather: WeatherState|None` + accessor) rejected — forces every reader to switch to an accessor, contradicting "systems unaware."
2. **Lock at Trail→Prep transition, freezing the node's current weather; no mandatory sync-fetch.** Rationale: Trail kickstart already eagerly fetches the current node; lock-existing is deterministic and keeps Prep client-free. Sync-fetch-on-lock left as overridable refinement (§7).
3. **In-memory write-through always; disk persistence at existing autosave points + on-lock.** Rationale: matches V.65 cadence; avoids per-fetch disk I/O; a crash merely re-fetches.
4. **No schema-version bump.** `.get` back-compat defaults (UNKNOWN/False) load every pre-T.39 save unchanged.
5. **Mutators live in `game/` (Run methods).** Extends V.63 (UI mutates `Run` only through `game/` surfaces) to weather; the cache/refresher remain stateless re: game (V.10).

## 5. Authored values

None — no new tunable numbers. Lifecycle defaults: `weather_state=UNKNOWN`, `weather_locked=False`. Heart/economy untouched.

## 6. Content / roster audit + reconciliation

No roster/vocabulary drift. One **doc/spec drift caught + reconciled here** (→ §B): SPEC **V.12/V.13** described a lock that **no code ever implemented** (grep clean across `src/`, `tests/`); **V.66** then silently superseded the "node.weather = live" intent of T4 §2 by pinning combat to `default_weather`. This task makes V.12/V.13 real and reconciles them with V.66 instead of leaving two contradictory invariants. V-guard: the new lifecycle invariant (§10) + a test asserting refresher-skips-locked and V.70 byte-identity under mid-fight refresh.

## 7. Open questions

**Resolved here (proposals, overridable)**
- Lock at Prep-entry freezing existing weather, no sync-fetch (Decision 2). *Override:* add a one-shot sync fetch of the current node in `on_play_next` (Trail owns the client) before locking, for the rare "no fetch landed yet + key present" case.
- In-memory write-through, disk at autosave points (Decision 3). *Override:* also `save_run` on each tick if durable-per-fetch is wanted (heavier).
- CHALLENGE preview now tracks live weather (§3.7). *Override:* keep CHALLENGE preview on a fixed value if the shifting preview is undesirable.

**Still open / deferred**
- Should a **locked** node show a small lock glyph in the Trail focus panel? Cosmetic; default = show the weather badge as-is (LIVE/SUBSTITUTE styling). Deferred.

## 8. Test plan

- **Lifecycle round-trip:** `Node.to_dict`/`from_dict` preserves `weather_state` + `weather_locked`; a pre-T.39 payload (fields absent) loads with UNKNOWN/False.
- **`set_node_live_weather`:** sets value + LIVE/SUBSTITUTE; **no-op on a locked node**; idempotent.
- **`lock_node_weather`:** freezes; UNKNOWN→SUBSTITUTE(default) on lock-without-fetch; second call is a no-op.
- **Refresher-skips-locked:** simulate a tick after lock → locked node's weather unchanged, unlocked nodes update.
- **V.70 byte-identity (regression):** with `node.weather` mutated mid-cycle, assert that locking before `node_encounter` makes `node_encounter`'s CHALLENGE squad and `generate_node_reward`'s reward read the **same** weather → payloads byte-identical (the property V.70 guards).
- **Determinism (V.2/V.14):** a fixed-seed sim + `workers=1` run is **byte-identical** before/after this task (sims never read live weather). Snapshot tests unchanged.
- **Persistence (UI-free):** drive the write-through helper over a `Run`, serialize, reload → weather survives (no `?` reset for fetched nodes).
- No UI tests (per repo policy) — Trail wiring covered via the game-side helpers it calls.

## 9. Acceptance criteria

1. Trail re-open shows previously-fetched weather (no `?` reset); weather survives Save&Exit → Continue.
2. All ~50 nodes' fetched weather is persisted in the save and keeps refreshing while unlocked.
3. The **current** node's weather locks **on entering Prep** and never changes thereafter (refresher skips it); other nodes keep refreshing.
4. Combat Weather Favor, CHALLENGE squad (30% slot), and CHALLENGE reward all read the locked `node.weather` — byte-identical between Prep build and resolve (V.70 holds).
5. Pre-T.39 saves load unchanged; no schema bump.
6. Fixed-seed sims byte-identical to pre-task (V.2/V.14).
7. Display tri-state (V.66) intact: UNKNOWN `?`, SUBSTITUTE flagged, LIVE plain — now sourced from the persisted `Run`.

## 10. SPEC changes needed (for `/spec`)

**New §T row**
- `T.39 | Persistent live node weather + Prep-entry lock — Node weather lifecycle (`weather_state: NodeWeatherState` {UNKNOWN/LIVE/SUBSTITUTE} + `weather_locked: bool`, save round-trip, back-compat `.get`, no schema bump); `Run.set_node_live_weather`/`lock_node_weather` pure mutators; Trail reads persisted Node (not ephemeral cache) + cache→Run write-through on tick/kickstart for unlocked nodes; lock current node at Trail→Prep; combat/encounter/reward read live-locked `node.weather` (default = placeholder, T4 §2) — stage affinity still drives squad theming; locking is load-bearing for V.70 byte-identity once weather is mutable | files: game/models.py, game/route.py, ui/views/trail.py, main.py, tests/game/test_models.py, tests/game/test_encounter.py, tests/game/test_run_loop.py, docs/live/systems/ui.md, docs/live/systems/weather_api.md, docs/design/tasks/t39_persistent_node_weather_plan.md | depends T.7,T.11,T.14,T.38 | est M | status 📋 Plan`

**New §V invariant**
- `V.73: **Node weather has a persisted live lifecycle, frozen by a Prep-entry lock; game systems read `node.weather` lock-unaware.** Each `Node` carries `weather: WeatherState` (the EFFECTIVE game weather — `default_weather` placeholder until a live fetch overwrites it, T4 §2), `weather_state: NodeWeatherState ∈ {UNKNOWN, LIVE, SUBSTITUTE}`, and `weather_locked: bool` (all save-persisted; pre-T.39 saves default UNKNOWN/False, no schema bump). The Trail write-through copies fetched cache values into the `Run` via the pure game-side mutators `set_node_live_weather`/`lock_node_weather` only (cache/refresher stay stateless re: game, V.10); **`set_node_live_weather` is a no-op on a locked node**, so the refresher keeps refreshing unlocked nodes and **skips locked ones**. The **current** node locks at the **Trail→Prep transition** (freezing its current value; an UNKNOWN node freezes `default_weather` as SUBSTITUTE, V.13 fail path) and never changes thereafter. **All game systems (combat Weather Favor, CHALLENGE 30% live-weather slot, CHALLENGE reward) read `node.weather` transparently, unaware of the lock**; squad *theming* still reads **stage affinity** (V-of T19 §3.4), not weather. **The lock is load-bearing for V.70:** because `node.weather` is now mutable, freezing it before `node_encounter` is what keeps the CHALLENGE squad roll and `generate_node_reward` byte-identical. Determinism (V.2/V.14) holds — `resolve_combat` purity unchanged, replay/Continue read the saved locked value, sims pass explicit weather and never touch live. Display tri-state by `weather_state` (V.66) now reads the persisted `Run`, not the ephemeral cache. (T.39)`

**Amendments**
- **V.12** — replace the "engine ignores cache and reads `Run`" framing with V.73: locked weather is frozen on the `Node` in `Run`; refresher skips locked nodes; systems read `node.weather` lock-unaware. (cross-ref V.73)
- **V.13** — relocate the lock trigger from "advance-to-unknown" to **Prep-entry** for the current node; the mandatory sync-fetch becomes optional (Trail kickstart eagerly fetches); UNKNOWN-at-lock freezes `default_weather` as SUBSTITUTE. (cross-ref V.73)
- **V.66** — note the display source is now the persisted `Run` (not the ephemeral cache), and game-logic weather is the **live-locked `node.weather`** (no longer pinned to `default_weather`); the "deterministic preview" clause now holds for FIGHT nodes (stage affinity) but **CHALLENGE previews track live weather** by design. (cross-ref V.73)
- **V.70** — add: the byte-identity between `node_encounter` and `generate_node_reward` is preserved **because the current node's weather is locked before the fight** (V.73); both read the same frozen `node.weather`.
- **V.63** — note weather mutation is a sanctioned `game/` surface (`Run.set_node_live_weather`/`lock_node_weather`), so the Trail mutating weather is not a violation.

**§B backprop**
- `B.<next>: V.12/V.13 lock specced in T.7 but never implemented; T.11/V.66 then pinned combat weather to `default_weather`, silently dropping the T4 §2 "node.weather = live" intent → Trail weather never persisted (reset to `?` every open, never saved). Fixed by T.39 (V.73). Guard: V.73 + refresher-skips-locked + V.70-under-mid-fight-refresh tests.`

**Implementation Order:** append T.39 after T.38 (run-loop polish; all deps built).

## 11. LIVING docs to update

- `docs/live/systems/weather_api.md` — add the **node-weather lifecycle** section (persisted `weather_state`/`weather_locked`, write-through cache→`Run`, lock-skip); clarify the cache is fetch-scheduling, the `Run` is the persisted source of truth.
- `docs/live/systems/ui.md` — Trail weather now reads the persisted `Node` (not the cache); lock at Prep-entry; tri-state unchanged. Flip any 🔶 weather note → ✅ where this makes it true.
- No FROZEN-doc edits (`docs/design/` left as-is).
```
