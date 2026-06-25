# T.15 Plan — Routing + reward step + Continue (combat-result-out seam)

> **Status:** `T.15 🟡 WIP` (flipped by `t10_mvp_run_loop_plan.md`). This is the
> **focused** T.15 plan; the MVP-slice doc covers it at slice level (§3.4 reward,
> §3.6 routing) — this one verifies every seam against current code and splits
> 15a/15b, with the **commit-on-start exit semantics** resolved with the user.
> **Depends (state):** T.9 (menu ✅), T.10 (RunStart ✅), T.11 (Trail ✅),
> T.23a (Prep ✅), T.14 (save ✅), T.3/T.26 (combat + `BattleResult` ✅).
> **T.13 (run-summary) is 🟡 unbuilt** and gates the *terminal* routing — so the
> build order is **15a → T.13 → 15b** (15a closes the per-node loop without the
> summary screen; 15b wires victory/defeat → Summary once T.13 lands).
> **Resolves:** the combat-result-out gap (combat exit currently drops the result,
> `main.py::_open_combat`); the disabled menu **Continue**; the open per-node loop.
> **Design source-of-truth:** SPEC §V.64 (result-out seam), §V.65 (autosave),
> §V.66 (refresher lifecycle), §G "Core game loop",
> [`views_spec.md`](../systems/views_spec.md) §7 (Reward) + §8 (Summary),
> [`docs/live/systems/ui.md`](../../live/systems/ui.md) (CombatSession + nav),
> [`t10_mvp_run_loop_plan.md`](./t10_mvp_run_loop_plan.md) §3.4/§3.6.
> **What this plan adds beyond the MVP doc:** the verified `on_exit` call-site list
> (3 sites), the **testable game-side reward applier** `economy.apply_node_result`
> (the 15a engine residue, mirroring T.23a's `validate_team_positions`), the
> commit-on-start exit decision, and the 15a/15b ship order around the T.13 gate.

---

## 0. Substep split

Real seam = **per-node loop closure (15a)** vs **terminal + resume routing (15b,
needs T.13)**. Each ships + tests independently; 15b depends on 15a + T.13.

| Sub | Scope | New code | Ships |
|---|---|---|---|
| **15a** | Combat-result-out seam (`on_exit(result)`, V.64) + **`economy.apply_node_result(run, result)`** (income/tempest/battle_log/mark-cleared/advance or DEFEAT) + reward panel (`ui/views/reward.py`) + node-boundary autosave (V.65). Win/Continue → Trail; terminal → menu (interim until 15b). | `ui/views/reward.py`, `game/economy.py` (`apply_node_result`), edit `ui/views/combat.py` + `main.py` | Closed per-node loop |
| **15b** | Terminal routing → **Summary** (T.13 view) on victory/defeat; **Continue** = `save.load_run` → Trail (enable the menu button); full `page.views` routing review + `on_view_pop` lifecycle (stop combat autoplay + Trail refresher, V.66). | edit `main.py`, `ui/views/menu.py` | Whole menu→…→menu loop incl. resume |

Build order: **15a → (T.13 build) → 15b.**

---

## 1. Scope

**In (15a):** the result-out callback signature change + its 3 call sites; the
game-side reward applier; the reward panel; per-node autosave. **In (15b):** terminal
→ Summary, Continue resume, the routing/lifecycle pass.

**Out (with why):**
- **No combat math / re-resolve** — V.64/V.56: the view already holds the resolved
  `BattleResult`; the producer applies progression off it, never re-resolves.
- **No new economy *rules*** — `apply_node_result` only *orchestrates* the existing
  `apply_node_income`/`grant_fight_tempest` + `Run` progression methods (V.63).
- **No Summary view** — that's T.13 (`viz/run_summary.py` + `ui/views/summary.py`);
  15b only *routes to* it.
- **No combat-view-internal rework** (autoplay §D.28) — only the `on_exit` signature
  changes; playback untouched.
- **No abandon/re-prep path** — exit semantics are **commit-on-start** (§4 D1).

---

## 2. The gap today

| Piece | `file.py:line` | State |
|---|---|---|
| Combat view exit callback | `ui/views/combat.py:262 on_exit: Callable[[], None]` | 🔴 drops the result (V.64 wants `on_exit(result)`) |
| `on_exit()` call sites (all have `result` in scope, resolved at `combat.py:276/282`) | `combat.py:838` (end-panel Continue), `:984` (control-bar Exit), `:1053` (Escape key) | 🔶 0-arg |
| `BattleResult` outcome | `result.outcome` ∈ `CombatOutcome.{WIN,LOSS,DRAW}` (`combat.py:821`) | ✅ |
| Per-node income | `economy.apply_node_income(run, won, node_index) -> int` (`economy.py:195`) | ✅ |
| Fight tempest | `economy.grant_fight_tempest(run)` (always `TEMPEST_PER_FIGHT`; `economy.py:173`) | ✅ |
| Run progression | `Run.mark_current_node_cleared()` / `advance_to_next_node()` (→ `VICTORY` if last) / `status` (`models.py:791-827`) | ✅ |
| Battle log | `Run.battle_log: list[BattleResult]` (`models.py:706`; serialized `:848`) | ✅ |
| Autosave | `save.save_run(run, path)` atomic (`save.py:54`), `default_save_dir()` (`:121`) | ✅ (Trail Save&Exit uses it) |
| Resume | `save.load_run(path) -> Run` (`save.py:80`) | ✅ but menu Continue → `_continue` placeholder (`main.py:153`) |
| Combat producers (must take 1-arg) | `main.py:132` (Playfight `_open_combat`), `main.py:64` (run-loop `_open_combat`) | 🔶 pass 0-arg lambda |
| Reward applier (orchestrator) | `game/economy.py` | ❌ create (15a) |
| Reward view | `ui/views/reward.py` | ❌ create (15a) |
| Summary view | `ui/views/summary.py` / `viz/run_summary.py` | ❌ **T.13** (gates 15b terminal) |

---

## 3. Architecture

`ui/` imports `game/`, never the reverse (V.1). The **producer** (run-loop wiring in
`main.py`) owns progression; the combat view stays pure presentation (V.56/V.64).

### 3.1 Combat-result-out seam (15a)
- Change `build_combat_view(..., on_exit: Callable[[BattleResult], None])`. The 3
  call sites (`combat.py:838/984/1053`) call `on_exit(result)` — `result` is already
  in scope (resolved once at build, `:276/:282`), so **every** exit (Continue / Exit /
  Escape) carries the same resolved result.
- **Commit-on-start (D1):** the run-loop producer applies the result on *any* exit;
  the reward panel is the explicit post-fight gate. No "abandon" branch (would be
  save-scumming a deterministic fight, V.2).
- **Back-compat:** non-loop producers pass a result-ignoring 1-arg lambda. Update both
  `main.py` callers + any test that builds the combat view (§8) to `lambda _result:
  …` / `lambda result: …`.

### 3.2 Reward applier — `economy.apply_node_result(run, result)` (15a, the engine residue)
The testable game-side orchestrator (Flet-free; mirrors T.23a's `validate_team_positions`
seam). Proposed in `game/economy.py` (it already owns `apply_node_income`/`grant_fight_tempest`):

```python
@dataclass(frozen=True)
class NodeResultSummary:
    won: bool
    amber_gained: int
    tempest_gained: int
    terminal: bool          # run.is_complete() after applying
    status: RunStatus       # IN_PROGRESS | VICTORY | DEFEAT

def apply_node_result(run: Run, result: BattleResult) -> NodeResultSummary:
    """Apply one fought node's outcome to `run` (V.64). Appends `result` to
    `battle_log`, grants income (win bonus only on a win, V.2-seeded) and fight
    tempest, then on a win marks the node cleared + advances (→ VICTORY if last);
    on a non-win sets DEFEAT. Pure progression — no Flet, no re-resolve, no I/O
    (autosave is the caller's job, V.65)."""
```

- `won = result.outcome == CombatOutcome.WIN`; **DRAW/LOSS ⇒ not won ⇒ DEFEAT** (draws
  are rare timeouts; MVP treats them as a loss for the run).
- Income before progression so `interest` reads pre-advance Amber (matches
  `apply_node_income`'s contract). `node_index = run.current_node_index` at call time.
- Idempotency note: it mutates `run` once; the caller calls it exactly once per fight
  (the single `on_exit`). No guard needed beyond that (V.64 = one producer apply).

### 3.3 Reward panel — `ui/views/reward.py` (15a)
- `build_reward_view(page, run, summary, *, on_continue) -> ft.View` (route `/reward`).
  Pure presentation off the `NodeResultSummary` + `run` (no recompute, V.63): outcome
  banner (Victory/Defeat), Amber gained, tempest/rank progress, nodes cleared. One
  **Continue** button → `on_continue()`.
- The producer decides where Continue goes: non-terminal → Trail; terminal → menu
  (15a interim) / Summary (15b).

### 3.4 Wiring (15a) — `main.py`
- `_open_combat` (run-loop) becomes `on_exit=lambda result: _finish_combat(page, run,
  node, result)`:
  ```
  summary = economy.apply_node_result(run, result)
  save_run(run, default_save_dir()/f"{run.run_id}.json")   # node-boundary autosave (V.65)
  push reward view; on_continue:
      pop reward (+ combat) back to a clean stack
      if summary.terminal: → menu (15a) / Summary (15b)
      else:                → Trail (refreshed at the new current node)
  ```
- The Playfight producer (`main.py:132`) just gains the 1-arg ignore: `lambda _r:
  _pop(page)`.

### 3.5 Terminal + resume (15b)
- **Terminal → Summary:** `summary.terminal` ⇒ push the T.13 Summary view (BarChart of
  `run.battle_log` damage-per-battle) instead of the menu; its return → menu.
- **Continue:** menu `on_continue` = `load_run(latest save) → _push_trail(page, run)`;
  enable the button when `save_exists` (already plumbed, `menu.py`). Trail rebuilds at
  the saved `current_node_index` and restarts its refresher (V.66).
- **Lifecycle:** `_pop`/`on_view_pop` already stops combat autoplay (`view.data`) +
  the Trail refresher (V.66); the routing pass confirms each pushed view carries its
  stop-handler and the stack unwinds cleanly menu→…→menu.

### 3.6 Cross-task seams / wrinkles
- **Boss nodes:** the result flows the same; `apply_node_result` is node-type-agnostic
  (a boss win advances like any node; the last node → VICTORY).
- **Determinism:** `win_bonus`/`node_income` are seeded by `(run.seed, node_index)`
  (`economy.py:1`) ⇒ re-applying after a Continue reproduces the same income (V.2).
- **Autosave timing (D3):** once per node boundary (after `apply_node_result`), plus
  the existing Save&Exit — not per shop action (re-derivable; keeps saves cheap).

---

## 4. Decisions

1. **Commit-on-start exit semantics (user-confirmed):** any combat exit applies the
   resolved result; no abandon/re-prep. Single `on_exit(result)` (V.64); reward panel
   is the gate. *Rationale:* the replay backend fixes the outcome at Start-Combat;
   re-prep-after-result = save-scumming a deterministic fight (V.2). **Decided.**
2. **Reward applier in `game/economy.py`** (`apply_node_result` + `NodeResultSummary`)
   — the existing economy/progression home; Flet-free + testable. *(Alt: new
   `game/run_loop.py`; economy.py is the better fit — it already owns the income/tempest
   primitives.)* **Proposed.**
3. **DRAW ⇒ DEFEAT** for the run (non-win). *Rationale:* a draw is a timeout, not a
   clear; advancing on a non-clear is wrong. **Proposed.**
4. **15a terminal → menu (interim); 15b → Summary** (after T.13). Keeps 15a shippable
   before the summary screen exists. **Proposed.**

---

## 5. Authored values
- No new economy constants — `apply_node_result` orchestrates existing
  `apply_node_income` / `grant_fight_tempest` (income base/bonus/interest + tempest all
  already authored, T.22). This task authors **wiring + one orchestrator**, not balance.

---

## 6. Content / roster audit + reconciliation
- No content/roster vocabulary in scope (routing + reward orchestration only).
- **Seam-signature drift (caught):** `build_combat_view(on_exit)` is 0-arg today but
  V.64 already specifies `on_exit(result)`; the live code lags the invariant. 15a brings
  the code to the spec (not a §B bug — the invariant was authored ahead of the wiring,
  by design of the MVP-slice plan). **Reconcile:** update the 3 call sites + both
  producers + tests in one change; no new invariant.

---

## 7. Open questions

**Resolved here (overridable):** reward applier in `economy.py` (D2); DRAW⇒DEFEAT (D3);
15a→menu / 15b→Summary interim (D4). **Decided with user:** commit-on-start (D1).

**Still open / confirm early in build:**
- **Q1:** does `grant_fight_tempest` fire on a **loss** too, or win-only? (Lean win-only
  — on a loss the run ends DEFEAT so tempest is moot; cleaner to grant only on a clear.
  Confirm against the T.22 intent when building 3.2.)
- **Q2:** which save does Continue load — a single `run_id`-named slot or "latest by
  mtime"? (Lean: the run's own `{run_id}.json` written by autosave; menu Continue picks
  the most-recent save dir entry. Verify `save_exists`/`default_save_dir` plumbing in
  `menu.py`/`main.py` before 15b.)

**Deferred:** abandon/re-prep (rejected, D1); Summary richness (T.13); combat-view
autoplay rework (§D.28).

---

## 8. Test plan

Logic is testable; views are not (CLAUDE.md). Targets:

**15a — `tests/game/test_economy.py` (or `test_progression.py`):**
- `apply_node_result` **win**: `battle_log` grows by 1; Amber +income (with win bonus,
  seed-deterministic); tempest +`TEMPEST_PER_FIGHT`; current node CLEARED; advanced (or
  `status == VICTORY` on the last node); `summary` fields match.
- **loss/draw**: `status == DEFEAT`; not advanced; income applied without win bonus;
  `summary.terminal is True`.
- **Determinism (V.2/V.14):** same `(seed, node, result)` ⇒ identical Amber/tempest
  across two applies (fixed seed, `workers=1`).
- **last-node win ⇒ VICTORY** terminal.
- **Combat-seam regression:** the combat view + dev-harness still open with the new
  `on_exit(result)` signature (1-arg lambda) — existing `tests/ui/test_combat_playback.py`
  / harness construction stay green.

**15b — `tests/game/`:** a scripted full run (`new_run` → loop `apply_node_result` per
node → reaches `VICTORY`/`DEFEAT`) round-trips through `save_run`/`load_run` identically
(V.36/V.2), and Continue-after-load reproduces the same next fight.

**View smoke (optional, mirrors `tests/ui/test_prep.py`):** `build_reward_view`
constructs + its Continue button fires `on_continue`.

---

## 9. Acceptance criteria

**15a:**
1. `build_combat_view` exit callback is `on_exit(result: BattleResult)`; all 3 sites
   pass `result`; both `main.py` producers + tests updated (1-arg). Combat tests green.
2. `economy.apply_node_result(run, result)` applies income/tempest/battle_log +
   mark-cleared/advance (win) or DEFEAT (non-win), returns a correct `NodeResultSummary`;
   deterministic; tested incl. last-node VICTORY.
3. A fought node: combat exit → reward panel (outcome + Amber + tempest) → Continue →
   Trail at the new current node; the run autosaves through `save.save_run` (V.65).
4. Terminal (victory/defeat) routes somewhere clean (menu, 15a interim).

**15b:**
5. Terminal → Summary (T.13) → menu.
6. Menu **Continue** loads the latest save → Trail and resumes; refresher restarts.
7. The stack unwinds menu→…→menu with no leaked autoplay/refresher threads (V.66);
   full-run save/load round-trip test green.

---

## 10. SPEC changes needed (for `/spec`)

- **§T row T.15** — refresh files-cell to landed reality + note the 15a/15b split +
  the new `economy.apply_node_result` seam. Add `game/economy.py`,
  `tests/game/test_economy.py`, `docs/design/tasks/t15_routing_reward_plan.md` to the
  cell. Status stays `🟡` until 15b lands (gated on T.13), then `✅`.
  *(Optional: split into rows `T.15a`/`T.15b` mirroring T.23a/b — recommended for parity.)*
- **New §V invariant (reward applier seam):** *the run-loop reward step applies a fought
  node's outcome **only** through `economy.apply_node_result(run, result)` — the single
  game-side orchestrator that grants income/tempest, appends `battle_log`, and runs
  mark-cleared/advance-or-DEFEAT; the producer calls it exactly once per fight and never
  re-resolves (extends V.64).* Guards ad-hoc progression in views + double-apply.
- **§B backprop:** none (no runtime bug; the `on_exit` 0-arg→1-arg is invariant-ahead-of-
  code, reconciled in §6).
- **§D:** mark the loop-shell / combat-result-out gap **RESOLVED** on 15b land; note the
  abandon/re-prep path explicitly rejected (commit-on-start, D1).
- **Implementation Order:** confirm `T.23a → T.15a → T.13 → T.15b` (15b after the summary
  view exists).

---

## 11. LIVING docs to update (build must touch on landing)

- **`docs/live/systems/ui.md`** — add the Reward section + the combat-result-out seam
  (`on_exit(result)`, the `apply_node_result` producer step), the autosave/Continue path,
  and the full `page.views` run-loop nav map; flip Reward 🔶→✅ (15a), Continue/terminal
  (15b). Update the `CombatSession` seam note (`on_exit` now carries the result).
- **`ARCHITECTURE.md`** — the view-stack/run-loop map (menu→run_start→trail⇄prep→combat→
  reward→(trail|summary)→menu) + which `game/` modules each step calls.
- Journal entry on landing (Process notes + prompting-strategy section, CLAUDE.md mandate).
