# T37 Plan — Combat Replay/Animation Backend (combat-view prep)

> **Status:** plan — ready for review. (**New §T row** — not in §T yet; needs `/spec` to add **T.37** + amend V.2 + add invariants + §B backprop. Do not edit SPEC inline; §10 lists deltas.)
> **Depends:** T.3/T.20/T.26 (unified tick engine + effect substrate + recorder — **done**). Independent of **T.23** (Prep formation snapshot, planned-not-built) by design — see §3.2. Feeds **T.12** (Combat view), which gains a `depends` on T.37.
> **Resolves:** the backend half of the combat-view animation requirement; clears the four recorder gaps surfaced in the combat-view readiness audit (heals/DOT/summons/statuses dropped from the event stream; init positions discarded).
> **Design source of truth:** [`views_spec.md` §7](../systems/views_spec.md) (Combat view: action-queue look-ahead §7.5, required telemetry §7.4 — HP+mana bars, damage/heal numbers, defeat indicators), [`combat_system_proposal.md`](../systems/combat_system_proposal.md), the LIVING [`docs/live/systems/combat.md`](../../live/systems/combat.md) (recorder + event-stream + HP-trace sections).
> **What this plan adds beyond those:** the **architecture decision** that combat state for the view is *recomputed by re-running the pure deterministic engine* (V.2), not *recorded* — plus the lean event-stream completion + initial-board snapshot that drive the *discrete narrative beats* the replay can't (numbers, icons, defeat markers).

---

## 0. Substep split (`T.37a → T.37b`)

Split along a real seam: **recorded data (pure, ships now)** vs **replay machinery (engine refactor)**. `b` depends on `a` only for the shared models; each ships + tests independently.

- **T.37a — Event-stream completion + initial-board snapshot.** Complete the `BattleResultRecorder` so every animatable *beat* emits exactly one `BattleEvent` (add `heal`, `dot`, `status`, `spawn`, `despawn`); add `hp_after`/`barrier_after` to HP-changing events (exact HP bars without needing `b`); capture `BattleResult.initial_pieces` (post-placement positions + identity + mana profile) and board dims. Pure data; recorder is observer-only ⇒ sims byte-identical (V.2). **Done when:** a fight's `BattleResult` is a complete, self-contained narrative (every beat present, board layout known) and HP bars are exactly reconstructible from it alone.
- **T.37b — Steppable engine + deterministic inspect-at-tick API.** Refactor `engine.run`'s tick loop into a drivable stepper; reimplement `resolve_combat`/`resolve_boss_combat` on it **byte-identically**. Add a pure, UI-free inspect API: `(team, enemies, weather, run_mods, tick) → read-only per-piece state` (effective stats incl. STR/AS ramp, hp, barriers, per-slot mana, statuses, position) by re-running to `tick` on a **cloned** `run_mods`. **Done when:** the view can read any piece's any property at any tick, byte-identical to the resolved fight, storing nothing.

---

## 1. Scope

**In scope (a):** `BattleResultRecorder` event-stream completion; `BattleEvent` + `BattleResult` model additions (`hp_after`, `barrier_after`; `initial_pieces`, `board_width`, `board_height`); a `PieceSnapshot` value type; a `despawn` event from `expire_summon`; `combat_log.py` rendering of the new beats; serialization (`to_dict`/`from_dict`) round-trips. Tests + golden re-baseline.

**In scope (b):** `engine.run` → steppable form (generator/step) with `resolve_combat`/`resolve_boss_combat` reimplemented on top, byte-identical; a new pure inspect/replay module returning UI-friendly read-only piece state at a tick; `run_mods` clone-on-inspect; exports. Determinism guard tests.

**Out of scope (why):**
- **The Flet Combat view itself (T.12)** — this is the headless backend it *calls*; matches the UI-independent-backend principle. No Flet imports (V.1).
- **The action-queue *projection* algorithm / "next ~12s" windowing (views_spec §7.5)** — derivable in the view from the complete event stream; no backend data needed beyond the stream `a` ships.
- **T.23 Prep player-placement** — T.37 captures whatever positions are on the pieces; T.23 later changes their *source* (player-authored vs `assign_spawns` default) without touching the capture. Separate task.
- **Per-tick *state* keyframes in `BattleResult`** — explicitly rejected (§3.3, Option A): bloats every save (T.14) and re-introduces stat-drift. Replay supersedes.
- **Off-cadence mana *events*** — bar values come from replay (`b`) / `hp_after`-style anchors; mana mutations (item refund/grant, trait drain) need no narrative beat. Dropped (§4.3).

## 2. The gap today

| Piece | Where (`file.py:line`) | State |
|---|---|---|
| Recorder subscribes attack/damage/death/cast/end only | `recorder.py:62-92` | 🔴 — no `on_heal`, `on_spawn`, `on_status_*` handlers |
| `EVENT_HEAL`/`EVENT_STATUS`/`EVENT_SPAWN` constants defined, unused | `recorder.py:31-33` | 🔶 — declared, no producers |
| DOT damage tracked in totals but **no `BattleEvent`** | `recorder.py:_on_damage_dealt` (~159) | 🔴 — DOT HP loss invisible in stream |
| HP-by-subtraction over-counts barriers | `context.py:272` (full pre-barrier `amount` fired, `to_hp` applied) per V.28 | 🔴-drift — subtraction ≠ actual HP |
| Summon despawn fires **no event** | `engine.py:860` → `context.expire_summon` (no `bus.fire`) | 🔴 — invisible board removal |
| `on_heal` / `on_spawn` / `on_status_*` **are** fired by engine/context | `context.py:312`,`:483`,`:382`,`:390`; `engine.py:632` | ✅ — producers exist, just unconsumed by recorder |
| Initial positions computed then discarded | `assign_spawns` `engine.py:754`; recorder built after, captures `piece_max_hp` only `recorder.py:51-58` | 🔴 — positions gone after the run |
| Positions are final before recorder ctor (both paths) | `resolve.py` (compile→assign→recorder), `_common.py:127` | ✅ — clean single capture point |
| No engine state-at-tick reader | `engine.run` is a closed `for tick in range(...)` loop `engine.py:828` | ❌ — can't pause/inspect |
| Board dims live only as engine constants | `context.py:67-68` (`BOARD_WIDTH=10`, `BOARD_HEIGHT=7`) | 🔶 — view must import; result not self-describing |

## 3. Architecture

### 3.1 The spine — recompute state, record beats (one sim, two read modes)

Combat is pure + seeded + byte-identical for the same `(team, enemies, weather, seed, run_mods)` (V.2). The view exploits this:

- **Timeline (recorded once):** `resolve_combat` runs the whole fight → `BattleResult.events` is the complete, deterministic event list. Drives **look-ahead** (action queue reads *forward* in the list — the fight is already resolved) and **discrete beats** (floating damage/heal numbers, status icons, spawn/despawn, defeat markers).
- **State (recomputed):** the same engine, same seed, stepped to tick T, yields exact live piece state (hp, barriers, per-slot mana, *effective stats* incl. STR/AS ramp, statuses, position). Drives **continuous** visuals (bars) + **click-to-inspect** tooltips.

Not two sims — **one** sim, run-to-completion for the timeline and stepped for live state. The action queue is "future events from the computed stream"; the board is "engine state at the cursor tick."

### 3.2 T.37a — event-stream completion + initial snapshot

**New beats** (recorder subscribes the already-fired hooks; all observer-only, no combat-math change):

| Beat | Event type | Hook / call site | Payload → `BattleEvent` |
|---|---|---|---|
| Heal | `EVENT_HEAL` | `on_heal` (`context.py:312`, `HealEvent(source,target,amount)`) | actor=source, target, `amount`=actual healed, `hp_after`=target.hp |
| DOT tick | `EVENT_DOT` (new const) | `on_damage_dealt` where `attacker is None` (environmental) **or** a status-sourced tag | target, `amount`, `note`=status_id, `hp_after`=target.hp |
| Status apply/expire | `EVENT_STATUS` | `on_status_applied`/`on_status_expired` (`context.py:382/390`, `engine.py:632`, `StatusEvent(target,status_id,duration_ticks,stacks)`) | target, `note`=status_id, `amount`=stacks, plus an applied/expired discriminator (`is_crit` reuse rejected — add `note` prefix `+`/`-` or a small `flag`; **decision §4.1**) |
| Summon spawn | `EVENT_SPAWN` | `on_spawn` (`context.py:483`, `SpawnEvent(piece,position)`) | actor=piece.id, `note`=`"q,r"` (mirrors MOVE), enough identity to lazily extend the board (see snapshot shape) |
| Summon despawn | `EVENT_DESPAWN` (new const) | **new** `bus.fire("on_despawn", …)` added to `context.expire_summon` (`context.py:485`) | actor=piece.id — distinct from `death` so the view fades vs death-animates |

**`hp_after` / `barrier_after` on `BattleEvent`** (`models.py:400`): recorded for every HP-changing beat (attack/cast/heal/dot). `on_damage_dealt` fires *after* `to_hp` is applied (`context.py:272-283`), so `target.hp`/`target.barrier_total` are the post-event truth — trivially read. This makes **HP bars exactly reconstructible from `BattleResult` alone** (handles barrier/DOT/heal/grievous uniformly) **without** needing `b`. (Supersedes the earlier "delta-summation" idea — we record the resulting value, not the delta.)

**Initial board snapshot** — captured in `BattleResultRecorder.__init__` (`recorder.py:51`), where `self._pieces` already carry final positions (`assign_spawns` ran in both `resolve.py` and `_common.py:127` *before* the recorder is built). New `PieceSnapshot` value type per piece:

```
PieceSnapshot(id, is_enemy, affinity: WeatherState, q, r, max_hp,
              mana: ManaProfile | None, summon: bool)
ManaProfile(start_mana, mana_regen, slots: list[(mana_cost, max_mana, priority)])
```

Stored as `BattleResult.initial_pieces: list[PieceSnapshot]` + `board_width`/`board_height` (stamped from `context.BOARD_WIDTH/HEIGHT`) so the result is self-describing for static board + roster-panel render *without* spinning the engine. **Names are not stored** — the view joins display names from the `Champion`/`Enemy` roster it holds (keyed by `id`); summons (no roster entry) fall back to `id` (**decision §4.2**).

**T.23 independence:** the snapshot captures *whatever positions are on the pieces*. Today that's `assign_spawns`' left-column team pack + role-aware enemy formation; post-T.23 it's player-authored Prep coords. Capture point is unchanged either way → T.37 neither depends on nor conflicts with T.23.

### 3.3 T.37b — steppable engine + inspect-at-tick (why not record state)

**Rejected — Option A (state keyframes):** snapshot every piece's full state per event into `BattleResult`. ~50–300 events × ~20 pieces × ~30 values × 50 nodes ⇒ multi-MB run saves (T.14), and the recorder would have to know *every* stat — add a stat, forget the snapshot, it's invisible. That is the precise content↔code drift the project forbids. Rejected.

**Chosen — deterministic replay.** Refactor the `engine.run` loop (`engine.py:828`, already a flat `for tick in range(1, HARD_CAP_TICKS+1)`) into a **stepper**: a generator yielding control each tick (or a `step()` that advances one tick). `resolve_combat`/`resolve_boss_combat` are reimplemented to *drain* the stepper to completion + build the result — **same loop body, byte-identical output** (no determinism re-baseline; guarded by golden + sim byte-equality).

New pure module (`game/combat/replay.py` or `inspect.py`):

```
inspect_at_tick(team, enemies, weather, *, run_mods=None, tick) -> list[PieceView]
```

Re-runs `compile_loadout → assign_spawns → step to `tick`` and returns **read-only** `PieceView`s (plain value structs: `id`, `hp`, `max_hp`, `barrier_total`, per-slot `current_mana`/`max_mana`, **effective stats via `piece.stat(name)`** — STR/INT/AS/move/range/armor/etc., active statuses with remaining duration/stacks, position). **No Flet, raw `Piece` never escapes** (V.1). For sequential playback the view holds one stepped instance and reads `PieceView`s as it advances; for random scrub/inspect it calls `inspect_at_tick` (microseconds — short fights, pure int math).

**Wrinkle — `run_mods.augment_state` is mutable** (quest trackers, T.31). An inspect re-run must take a **deep clone** so replay stays side-effect-free and byte-identical to the original resolve (otherwise quest counters double-apply). Constraint, not a blocker.

**Optional (not v1):** periodic keyframes (snapshot full state every K ticks) to make scrub = nearest-keyframe + short replay, if random access ever bites. Start with re-run-from-0.

### 3.x Determinism (V.2/V.14)
- `a` is observer-only: new subscriptions/events/fields never feed combat math. Damage totals + `turns` (filtered to attack+cast) unchanged ⇒ **sims byte-identical**. Only `combat_log` golden snapshots re-baseline (new beat lines) — and any test asserting exact event counts.
- `b` reuses the identical loop body via the stepper ⇒ `resolve_combat` output unchanged. Guard: a test asserts `resolve_combat` and "drain the stepper" produce byte-equal `BattleResult` on a fixed seed; sim sweep stays byte-identical (`workers=1`).
- No RNG introduced anywhere (no cadence mechanics added).

## 4. Decisions

- **§4.1 Status apply vs expire discriminator.** `EVENT_STATUS` needs to distinguish applied from expired. **Proposal:** a small explicit field over overloading `note`/`is_crit` — reuse `amount` for stacks and add `note=status_id`; carry applied/expired in a dedicated `BattleEvent` flag (or `+`/`-` sentinel in a new `kind` sub-note). Keeps the stream self-describing for the icon layer. *Overridable.*
- **§4.2 Summon display names.** Snapshot/events carry `id` only; the view roster-joins names for starting pieces and shows `id` for summons (e.g. `steam_turret`). `SummonSpec` (`registries.py:520`) could later carry a label; not needed for v1. *Overridable.*
- **§4.3 No off-cadence mana events.** Bar *values* come from `hp_after`-style anchors + replay, not from mana deltas, so item-refund/grant/trait-drain need no beat. Drops a brittle 3-site emission. *Overridable.*
- **§4.4 Capture in recorder ctor, not `resolve_*`.** Snapshot lives in `BattleResultRecorder.__init__` (positions already final there) so both resolve paths get it for free without touching `_common.py`. *Firm.*

## 5. Authored values
None — this task adds telemetry + a read API, no balance numbers. `BOARD_WIDTH=10`/`BOARD_HEIGHT=7` are *read* from `context.py:67-68`, not re-authored.

## 6. Content / roster audit + reconciliation
No roster vocabulary touched. Two **mechanism-drift** items caught while planning (→ §B in §10):
- Summon despawn (`expire_summon`) fires no event — the lifecycle is asymmetric vs `spawn` (which fires `on_spawn`). New `on_despawn` restores symmetry; V-guard so a future lifecycle path can't go silent again.
- DOT/heal HP changes are absent from the event stream while damage *totals* count them — the stream silently under-represented combat. V-guard: every HP-changing beat emits exactly one event (the V.50 "one cast = one event" shape, generalized).

## 7. Open questions
**Resolved here (overridable):** §4.1 status discriminator field; §4.2 summon names = `id`; §4.3 no mana events; §4.4 capture site.
**Still open / deferred:** keyframe scrub optimization (deferred, §3.3); whether T.12 wants the action-queue projection helper in `game/` or computes it view-side (leaning view-side — deferred to T.12).

## 8. Test plan
- **a — stream completeness:** a crafted fight exercising heal (medic), DOT (poison), status apply+expire, summon spawn+despawn produces exactly one `BattleEvent` per beat (new `test_recorder.py` or extend `test_combat.py`); `hp_after` equals the engine's `piece.hp` at each HP-changing beat incl. a **barrier** case (Primordial second-wind / `grant_barrier`) where `amount` (pre-barrier) ≠ HP delta — asserts subtraction would have drifted but `hp_after` is exact.
- **a — snapshot:** `initial_pieces` covers every starting piece with correct post-`assign_spawns` `(q,r)`, `max_hp`, mana profile; `board_width/height` == engine constants; `to_dict`/`from_dict` round-trips (incl. legacy results without the fields → empty defaults, mirroring `piece_max_hp`).
- **a — determinism:** a fixed-seed sim sweep is **byte-identical** to pre-T.37 for damage totals/outcome/`turns`; `combat_log` golden re-baselined once (new beat lines) and pinned.
- **b — byte-equality:** `resolve_combat` vs draining the stepper → identical `BattleResult` (fixed seed); boss path too; sim sweep unchanged (`workers=1`).
- **b — inspect fidelity:** `inspect_at_tick(..., tick=T)` for a STR-ramp piece (e.g. granite_gorilla Stone Charge / Aurion Ascendance) returns the same `piece.stat("strength")` the live run had at T (compare against a one-off instrumented run); `run_mods` clone leaves the caller's `augment_state` untouched (quest counter unchanged after inspect).
- **b — isolation:** `inspect`/replay module imports only `src/game/` (V.1/V.14); no Flet, no raw `Piece` in the returned type.

## 9. Acceptance criteria
**T.37a**
1. Heal, DOT, status (apply+expire), spawn, despawn each emit exactly one `BattleEvent`; no double-count, no drop.
2. Every HP-changing event carries `hp_after` (and `barrier_after`) equal to engine truth; HP bars reconstruct exactly from `BattleResult` alone, barriers included.
3. `BattleResult.initial_pieces` (post-placement positions + identity + mana profile) + `board_width/height` present and serialization round-trips; legacy results decode with empty defaults.
4. Sims byte-identical (totals/outcome/turns); `combat_log` golden re-baselined + pinned.

**T.37b**
5. `engine.run` is steppable; `resolve_combat`/`resolve_boss_combat` reimplemented on it, byte-identical (guarded).
6. `inspect_at_tick(...)` returns read-only per-piece state (hp, barriers, per-slot mana, effective stats incl. STR/AS, statuses, position) at any tick, byte-identical to the resolved fight, storing nothing.
7. Inspect runs on a cloned `run_mods` — zero side effects on the caller's `augment_state`.
8. Replay/inspect module is UI-free and `src/game/`-only (V.1/V.14); raw `Piece` never escapes.

## 10. SPEC changes needed (for `/spec`)

**§T — add two rows** (after T.36c; before the T.9–T.15 UI block conceptually):
- `T.37a | Combat replay backend — event-stream completion (heal/dot/status/spawn/despawn beats, one-event-per-beat) + hp_after/barrier_after on HP-changing events + initial_pieces snapshot (post-placement positions/identity/mana profile) + board dims; recorder observer-only, sims byte-identical; combat_log renders new beats | game/combat/recorder.py, game/combat/context.py, game/combat/engine.py, game/models.py, game/combat_log.py, tests | T.3, T.20, T.26 | M | 📨 (new)`
- `T.37b | Steppable engine + deterministic inspect-at-tick API — refactor run loop into a stepper, reimplement resolve_combat/resolve_boss_combat byte-identically, pure UI-free inspect(team,enemies,weather,run_mods,tick)->PieceView reading effective stats/hp/barriers/mana/statuses/position by re-running on a cloned run_mods | game/combat/engine.py, game/combat/resolve.py, game/combat/replay.py(new), game/combat/__init__.py, tests | T.37a | M | 📨 (new)`
- **Amend T.12** `depends` → add `T.37` (combat view consumes the completed stream + inspect API).

**§V — new invariants:**
- **V.x (event-stream completeness):** every animatable combat beat that changes visible state — move, attack, cast, **heal, dot, status (apply/expire), spawn, despawn**, death — emits **exactly one** `BattleEvent` (one producer path per beat; no double, no drop). HP-changing beats carry `hp_after`/`barrier_after` = engine truth, so HP/barrier bars reconstruct from `BattleResult` alone. Generalizes V.50 ("one cast = one event") to the whole stream; guards the B.22-class silent-drop. Recorder is observer-only ⇒ sims byte-identical (V.2/V.14).
- **V.y (replay determinism + inspect purity):** combat state for the view is **recomputed**, never recorded as per-tick keyframes. The engine exposes a stepper; `resolve_combat` is implemented on it byte-identically (single entry preserved, V.2). `inspect_at_tick(team,enemies,weather,run_mods,tick)` is pure + UI-free (extends V.1): it re-runs the deterministic engine on a **clone** of `run_mods` (mutable `augment_state` ⇒ no side effects) and returns read-only value structs — raw `Piece`/Flet never escape `src/game/`.

**§B — backprop (drift caught while planning):**
- **B.x (summon despawn invisible):** `expire_summon` (`engine.py:860`/`context.py:485`) ends a summon's life without firing any event — asymmetric vs `spawn`'s `on_spawn`, so the board could never learn an expired summon left. Fix → new `on_despawn` + `EVENT_DESPAWN` (T.37a); guard V.x.
- **B.y (HP-changing beats absent from stream):** DOT ticks and heals changed `hp` but emitted no `BattleEvent` (only damage *totals* tracked); combined with V.28 barriers firing full pre-barrier `amount`, any HP-by-subtraction reconstruction drifted/over-counted. Fix → emit heal/dot beats + `hp_after`/`barrier_after` (T.37a); guard V.x.

**§D:** none new. (Combat view stays T.12; this is its backend prerequisite.)

**Implementation Order:** insert `T.37a → T.37b` immediately **before T.12** in the UI-phase order (`… T.23 → **T.37a → T.37b** → T.12`); both are headless/backend, fit the UI-independent-backend principle, and unblock the animated view.

## 11. LIVING docs to update
- [`docs/live/systems/combat.md`](../../live/systems/combat.md) — extend the **recorder / event-stream** section (new beat types + `hp_after`/`barrier_after`), the **`BattleResult` shape** (`initial_pieces`, board dims), and add a **replay/inspect** subsection (stepper + `inspect_at_tick`, determinism). Update the HP-trace note (combat_log can now read `hp_after` instead of subtracting). `/check` must pass (every cited symbol resolves).
- [`ARCHITECTURE.md`](../../../ARCHITECTURE.md) — combat section: note the "record beats, recompute state" split + the inspect entry point as a second (byte-identical) engine driver alongside `resolve_combat`.
- No FROZEN docs edited.
