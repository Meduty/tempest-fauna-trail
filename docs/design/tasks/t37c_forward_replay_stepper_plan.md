# T.37c Plan — Resumable forward combat-replay stepper + move-coords hardening

> **Status:** plan — ready for review. (**New §T row** — `T.37c` does not exist in §T yet; needs `/spec` to add it. The supporting invariant edits **V.55/V.56/V.57** + bug **B.28** were already applied to SPEC by the `/spec bug:` backprop that surfaced this task — this plan re-confirms them and adds only the row + any deltas below.)
> **Depends:** **T.37a** (event stream + `initial_pieces`, ✅ done), **T.37b** (`inspect_at_tick` + `PieceView` + `build_combat` wiring, ✅ done). No unbuilt deps — both seams exist; this task realigns them with the live-advance design the T.37b plan specified but did not ship.
> **Resolves:** SPEC **B.28** (combat-view bars would freeze through registered-ability damage; the forward stepper the T.37b plan promised was never built). Unblocks **T.12a** (combat view drives this stepper for live bars).
> **Design source of truth:** [`t37_combat_replay_backend_plan.md` §3.3 (lines 85-101)](t37_combat_replay_backend_plan.md) — *"the view holds one stepped instance and reads `PieceView`s as it advances"* (the live-advance API this task finally builds). LIVING: [`docs/live/systems/combat.md` §Replay (lines 162-197)](../../live/systems/combat.md). Invariants: **V.55** (replay recompute), **V.56/V.57** (view resource truth = live replay), **V.29** (single tick loop), **V.2/V.14** (determinism), **V.28** (barriers), **V.48** (per-slot mana).
> **What this plan adds beyond those:** the concrete **single-loop-two-drivers** refactor (a generator loop body drained by `run`, stepped by `CombatReplay`), the `CombatReplay` holder contract, the `inspect_at_tick`-on-`CombatReplay` unification (kills the parallel read path), and the `move`-beat `dest_q`/`dest_r` structured-coords hardening (deprecates the `note=f"{q},{r}"` parse).

---

## 1. Scope

**In scope:**
- **`game/combat/engine.py`** — refactor the monolithic `run` `for tick` loop into a **single generator loop body** (`_step_combat`) that yields once per processed tick; `run(ctx, recorder=None)` becomes a thin **drain** of that generator (same loop body → byte-identical). **Drop the `stop_after_tick` kwarg** (the half-built T.37b hook the real stepper replaces — no parallel path left behind, V.29).
- **`game/combat/replay.py`** — new **`CombatReplay`** class: holds one live `ctx` (no recorder) + the generator; `.step_to(tick)` advances **forward only**; `.tick`, `.winner`, `.pieces() -> list[PieceView]` (reusing the existing `_view`). Reimplement **`inspect_at_tick`** as a one-shot over `CombatReplay` (build → `step_to(tick)` → read) so both read paths share one driver.
- **`game/models.py`** — add `BattleEvent.dest_q: int = -1`, `dest_r: int = -1` (+ `to_dict`/`from_dict` round-trip, legacy default `-1`).
- **`game/combat/recorder.py`** — `record_move` populates `dest_q`/`dest_r` (stop writing the dest into `note`); `_on_spawn` likewise (same fragile pattern — §4.4).
- **`game/combat_log.py`** — `_format_event` renders move/spawn coords from `dest_q`/`dest_r` (output text **byte-identical** → no golden re-baseline).
- **Tests** — `tests/game/test_combat_replay.py` (forward-stepper fidelity, the B.28 guard), `tests/game/test_combat.py` (move-coords round-trip + determinism).

**Out of scope (why):**
- **The combat view / `combat_playback` / harness** — that is **T.12a**; this task is the headless backend it consumes (same split as T.37a/b: backend headless, view separate).
- **Boss replay** (`resolve_boss_combat` boss-aware stepping) — **T.12b** (needs the `tools/`→`src/` promotion first).
- **Backward stepping inside `CombatReplay`** — forward-only by design; back-scrub/random-seek uses `inspect_at_tick` (re-run-from-0), which this task keeps (§4.3). Periodic keyframes remain the deferred optimization the T.37b plan flagged (§3.3 "Optional").
- **Any combat-math change** — observer-only / read-only; sims stay byte-identical (V.2/V.14).

## 2. The gap today

| Piece | Where (`file.py:line`) | State |
|---|---|---|
| `run` tick loop — flat `for tick in range(1, HARD_CAP_TICKS+1)` | `engine.py:842` | ✅ (monolithic; not yet a reusable body) |
| `stop_after_tick` bound (T.37b's "stepper") — re-runs from `on_combat_start` each call | `engine.py:849`, used `replay.py:122` | 🔴 **drift** — NOT a resumable stepper; the T.37b plan §97 ("hold one instance, advance") was never built ⇒ stepping a fight = O(N²) |
| `inspect_at_tick` + `PieceView` + `_view` | `replay.py:104/50/67` | ✅ (random-access re-run; the reuse substrate) |
| `build_combat(..., with_recorder=False)` shared wiring | `resolve.py:42` | ✅ |
| `_clone_run_mods` (deep-clone mutable `augment_state`, V.55) | `replay.py:91` | ✅ (reused) |
| `record_move` stores dest as parsed string `note=f"{q},{r}"` | `recorder.py:180` | 🔴 **fragile** (B.28) — string-parse coords |
| `_on_spawn` stores spawn coords as `note=f"{q},{r}"` | `recorder.py:343` | 🔴 same fragile pattern |
| `BattleEvent` has no structured position fields | `models.py:400` | ❌ |
| `_format_event` move/spawn render reads `event.note` | `combat_log.py:53/94` | 🔴 consumes the string |
| HP bar reconstruction from stream — incomplete for registered-ability burst | `recorder.py:244/279-288` | 🔴 **B.28** — `_on_cast` stamps `hp_after=-1`; `_on_damage_dealt` emits only on `tag==dot` |
| `CombatReplay` resumable forward holder | `game/combat/replay.py` | ❌ (this task) |

**No regression check (user-raised):** `git log -S "CombatReplay" --all` is empty and the #49 cleanup (`2fabb37`) only stripped unused imports from `engine.py` — it did **not** delete a stepper. The forward holder was never built; this is an original gap, not a cleanup casualty.

## 3. Architecture

### 3.1 Single loop body, two drivers (V.29-safe)

V.29 forbids a second tick loop. So the loop body lives in **exactly one place** and is driven two ways:

```
# engine.py
def _step_combat(ctx, recorder=None) -> Generator[int, None, str]:
    # current pre-loop: fire on_combat_start; immediate-resolution early-out
    for tick in 1 .. HARD_CAP_TICKS:
        ... the current per-tick body verbatim ...
        yield tick            # control returns AFTER tick fully processed
        if <ended this tick>: break
    ... current post-loop finalize (timed_out, set_duration, winner) ...
    return winner             # → StopIteration.value

def run(ctx, recorder=None) -> str:        # the DRAIN driver (resolve path)
    gen = _step_combat(ctx, recorder)
    try:
        while True: next(gen)
    except StopIteration as e:
        return e.value
```

- **`yield tick` placement:** once per tick, **after** all of that tick's processing (statuses → meters → movement/action → casts), so a consumer reading state after `yield` sees the post-tick board — exactly the `stop_after_tick=N` semantics today ("runs ticks 1..N inclusive"). The killing-blow tick must `yield` **before** the loop breaks so the view can render the final state, then finalize runs on drain.
- **Finalize stays out of the stepping path.** A `CombatReplay` that stops early simply stops pulling → the post-loop finalize never runs → no `end_combat`/`set_duration` mutates the mid-fight state being inspected (this is exactly why the current `stop_after_tick` path `return`s early at `engine.py:849-852`; the generator gets it for free by not draining).
- **`run` keeps its `(ctx, recorder=None)` signature** → `resolve_combat` (`resolve.py:38`), `_common.py:134`, and the test callers (`test_ability_catalog.py:309`, `test_abilities.py`) are **untouched**. Only the `stop_after_tick` kwarg is removed (sole caller is `replay.py`).

**Determinism:** byte-identical because it is *literally the same loop body* — a generator is control-flow sugar over the existing `for`. No statement reordered, no RNG, no cadence touched. Guarded by the existing `resolve_combat` golden + sim byte-equality (§8).

### 3.2 `CombatReplay` — the forward holder (`replay.py`)

```
class CombatReplay:
    def __init__(self, team, enemies, weather, *, run_mods=None):
        ctx, _ = build_combat(team, enemies, weather,
                              run_mods=_clone_run_mods(run_mods),  # V.55 side-effect-free
                              with_recorder=False)
        self._ctx = ctx
        self._gen = _step_combat(ctx, None)
        self._tick = 0
        self._winner = None
        # prime: run on_combat_start + reach tick 0 state (drive to first yield-able point)
    @property
    def tick(self) -> int: ...
    @property
    def winner(self) -> str | None: ...      # set once the gen is exhausted
    def step_to(self, tick: int) -> "CombatReplay":   # forward-only; tick < self.tick → ValueError
        while self._tick < tick and not exhausted:
            advance one yield
        return self
    def pieces(self) -> list[PieceView]:     # reuse _view; raw Piece never escapes (V.1)
        return [_view(p) for p in self._ctx.all_pieces()]
```

- **Forward-only.** `step_to(t)` with `t < self.tick` raises (caller must use `inspect_at_tick` or a fresh `CombatReplay` for back-scrub). This is the whole performance win: a full playthrough drives the generator **once** (O(total ticks)) instead of `inspect_at_tick`'s O(N²) per-step re-run.
- **Live state is complete.** Because `pieces()` reads the live engine pieces (not the event stream), every HP change is present — including registered-ability burst the stream omits (B.28). This is the V.57 truth source.
- **No recorder.** The holder is observer-free; it never builds a `BattleResult`. The view gets its `BattleResult` (cues + action-queue) from the separate `resolve_combat` call (T.12a wiring).

### 3.3 `inspect_at_tick` unified onto `CombatReplay` (kills the parallel path)

`inspect_at_tick` keeps its exact signature but is reimplemented as a one-shot:

```
def inspect_at_tick(team, enemies, weather, *, run_mods=None, tick) -> list[PieceView]:
    return CombatReplay(team, enemies, weather, run_mods=run_mods).step_to(max(0, tick)).pieces()
```

One driver (`_step_combat`), one holder (`CombatReplay`), two entry shapes (held-instance for sequential, one-shot for random). **No second read path, no duplicated stepping logic** — directly answers the no-parallel-paths constraint and V.29's spirit. The current `run(ctx, None, stop_after_tick=tick)` call (`replay.py:122`) is deleted along with the kwarg.

### 3.4 Move/spawn structured coords (B.28 hardening)

- `BattleEvent` gains `dest_q: int = -1`, `dest_r: int = -1` (after `barrier_after`; defaults keep legacy events + saves valid). `to_dict`/`from_dict` round-trip with `.get(..., -1)`.
- `recorder.record_move` sets `dest_q`/`dest_r` instead of `note`; `_on_spawn` likewise (§4.4 — same pattern, folded in to avoid a second B-entry later).
- `combat_log._format_event` renders `f"({event.dest_q},{event.dest_r})"` for move/spawn → **identical output string** ⇒ no golden snapshot churn. (If any golden references the old `note`, it re-baselines; verify in build.)
- Observer-only telemetry field → combat math untouched ⇒ sims byte-identical.

### 3.5 Invariant posture
- **V.29** — one loop body (`_step_combat`); `run` + `CombatReplay` are drivers, **not** parallel loops. The refactor *removes* the half-built `stop_after_tick` branch ⇒ fewer paths, not more.
- **V.2/V.14** — generator is the same statements; no RNG/cadence change. Guard: `run`-drain == pre-refactor `BattleResult` byte-equal on fixed seed; sim sweep `workers=1` byte-identical.
- **V.55** — `CombatReplay` deep-clones `run_mods` (reuses `_clone_run_mods`); raw `Piece`/Flet never escape `src/game/`.
- **V.57** — `pieces()` is the live engine truth, the view's resource source; the event stream is cues+queue only.

## 4. Decisions
- **§4.1 Generator loop body (not an extracted `_run_one_tick` + external cursor).** A generator captures the loop-carried state (`duration`/`timed_out`/`ended_early`/`tick`) for free and is provably the same control flow → lowest byte-identical risk. An extracted-function-+-manual-state-machine would re-thread that state by hand (more drift surface). *Proposal, overridable.*
- **§4.2 Drop `stop_after_tick` from `run`.** It was T.37b's stand-in for the real stepper; keeping it alongside `CombatReplay` = two ways to bound the loop = the parallel path we're told to avoid. Remove it; `CombatReplay` is the one bound. *Proposal, overridable.*
- **§4.3 Forward-only stepper; back-scrub stays `inspect_at_tick`.** Monotonic playback is the hot path (drive once). Random seek is rare (click-at-arbitrary-tick) and already O(tick) via re-run; not worth a keyframe cache yet (the T.37b "Optional" deferral stands). *Proposal, overridable.*
- **§4.4 Fold `_on_spawn` into `dest_q`/`dest_r` too.** Spawn carries the identical `note=f"{q},{r}"` fragility; migrating it in the same edit costs ~2 lines and prevents a future duplicate bug. *Proposal, overridable — could keep spawn on `note` if minimizing diff.*
- **§4.5 Minimal `CombatReplay` API (`step_to`/`tick`/`winner`/`pieces`).** No `.advance()` sugar unless a consumer needs it — YAGNI / no-dead-code (the SPEC row draft mentioned `.advance()`; drop it in the row, §10). T.12a's `combat_playback` selects the next event-bearing tick from the `BattleResult` and calls `step_to(that_tick)`. *Proposal, overridable.*

## 5. Authored values
None — no balance numbers. `HARD_CAP_TICKS` (`engine.py:47`), `BOARD_*`, `ROUND_TICKS` are read, not authored.

## 6. Content / roster audit + reconciliation
No rosters/tags/abilities touched. One mechanism-drift caught + fixed here: the `note`-string coords (`recorder.py:180/343`) → structured fields (B.28). No new vocabulary.

## 7. Open questions
**Resolved here (proposals, overridable):** §4.1 (generator), §4.2 (drop `stop_after_tick`), §4.3 (forward-only + `inspect_at_tick` for seek), §4.4 (spawn folded in), §4.5 (minimal API).
**Still open / deferred:** periodic keyframes for O(1) random seek (deferred per T.37b §3.3 "Optional" — only if scrub ever bites); boss-aware stepping (**T.12b**).

## 8. Test plan
- **B.28 guard (the headline):** a fight with a **registered-ability burst** caster — assert at **every event-bearing tick** that `CombatReplay.step_to(t).pieces()[id].hp` equals `inspect_at_tick(..., tick=t)[id].hp` (the two replay paths agree), **and** that this differs from a naive stream-`hp_after` reconstruction on at least one burst tick (proves the stream alone would lie). Include a **barrier case** (V.28: `hp ≠ Σdamage`).
- **Forward-stepper fidelity:** `CombatReplay` stepped monotonically through ticks `[t0<t1<...]` yields the same `PieceView`s as independent `inspect_at_tick` calls at each `ti` (held instance == re-run).
- **Forward-only contract:** `step_to(t)` with `t < self.tick` raises `ValueError`.
- **Determinism (V.2/V.14):** `run`-drain produces a `BattleResult` **byte-equal** to the pre-refactor `resolve_combat` on a fixed seed (golden); the `tools/simulation` sweep stays byte-identical at `workers=1`. Existing `test_combat_replay.py` cases (lines 19-105) still pass unchanged (signature preserved).
- **Move/spawn coords:** `record_move`/`_on_spawn` populate `dest_q`/`dest_r`; `to_dict`→`from_dict` round-trips them; a **legacy** event (no `dest_*` in payload) loads with `-1` defaults; `combat_log` move/spawn lines render identical text (no golden churn — or re-baseline if the golden keyed on `note`).
- **No Flet import** in `replay.py` (import in a no-display test); raw `Piece` never returned (only `PieceView`).
- **Single loop (V.29):** a test/grep asserts `engine.py` has exactly one `for tick in range(` (no duplicate loop reintroduced).

## 9. Acceptance criteria
1. `engine.run(ctx, recorder=None)` returns a `BattleResult` byte-identical to pre-T.37c on fixed seeds; sim sweep byte-identical (`workers=1`). One tick loop remains (V.29).
2. `CombatReplay(team, enemies, weather, run_mods=…)` drives **forward** via `step_to(tick)`; `pieces()` returns live `PieceView`s; a full playthrough steps the generator **once** (no per-step re-run).
3. `CombatReplay` HP/mana/stats/positions match `inspect_at_tick` at every event tick, **including registered-ability burst** (B.28 closed); back-scrub via `inspect_at_tick` still works.
4. `stop_after_tick` is gone from `engine.run`; `inspect_at_tick` is reimplemented on `CombatReplay` (one driver, no parallel read path).
5. `move` (and `spawn`) beats carry structured `dest_q`/`dest_r`; serialization round-trips; legacy events default to `-1`; `combat_log` output text unchanged.
6. `replay.py` is Flet-free; raw `Piece` never escapes (V.1); `run_mods` deep-cloned (V.55).
7. `docs/live/systems/combat.md` updated (Replay section: forward `CombatReplay` + `inspect_at_tick` on it; drop `stop_after_tick`); `/check` passes.

## 10. SPEC changes needed (for `/spec`)

**§T — add one row** (after `T.37b`):
- `T.37c | Resumable forward combat-replay stepper + move-coords hardening (combat-view prep, headless). Refactor engine.run's for-loop into a single generator loop body (_step_combat) driven two ways — run() drains it (byte-identical, V.29 one-loop preserved), CombatReplay steps it forward (.step_to(tick) + .pieces() live PieceViews) — O(total ticks) playback vs inspect_at_tick's O(N²) per-step re-run (kept for random seek; reimplemented on CombatReplay → one read driver, no parallel path). Drop the half-built stop_after_tick kwarg. Live state complete incl. registered-ability burst the stream omits (B.28). Replace move/spawn BattleEvent note=f"{q},{r}" string with structured dest_q/dest_r int fields (recorder + combat_log + serialization round-trip, legacy → -1). Observer-only/read-only ⇒ sims byte-identical (V.2/V.14) | game/combat/engine.py, game/combat/replay.py, game/models.py, game/combat/recorder.py, game/combat_log.py, tests/game/test_combat_replay.py, tests/game/test_combat.py, docs/design/tasks/t37c_forward_replay_stepper_plan.md | T.37a, T.37b | M | 📋 Plan`
- (The provisional `T.37c` row added by the earlier backprop should be reconciled to this exact text — note it drops the `.advance()` mention per §4.5 and adds the spawn migration + V.29 framing.)

**§V — confirm already-applied edits** (no new numbers needed):
- **V.55/V.56/V.57** already describe the forward stepper + view-truth split (applied during the B.28 backprop). Re-read after this plan to ensure they name `CombatReplay`/`step_to` consistently; tweak wording only if drifted (no renumber).
- **V.29** unaffected — explicitly reaffirmed (single loop body; `run`/`CombatReplay` are drivers).

**§B:** **B.28** already recorded (the bug this plan fixes). On landing, the build appends `**RESOLVED [date] (T.37c)**` to B.28.

**§D:** none.

**Implementation Order:** already updated to `… T.37a → T.37b → T.37c → T.12a → T.12b`. No change.

## 11. LIVING docs to update
- **`docs/live/systems/combat.md`** (Replay section, lines 162-197 + the table at 196-197): replace the `stop_after_tick`-hook narrative with the **forward `CombatReplay`** (one loop body, drained by `run` / stepped by the holder) + `inspect_at_tick` reimplemented on it; update the engine-layer table row (drop `stop_after_tick` hook). Line 147 ("view reads ability-hit HP from replay, not the cast marker") already anticipates this — keep + sharpen to cite V.57. `/check` must pass.
- **`ARCHITECTURE.md`** — if the combat-replay paragraph names `stop_after_tick`, update to `CombatReplay`. FROZEN docs (`docs/design/`, incl. `t37_combat_replay_backend_plan.md`) left as-is — this plan is the dated record that the live-advance design from that frozen plan was finally built.
```
