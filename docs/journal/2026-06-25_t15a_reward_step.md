# 2026-06-25 — T.15a: combat-result-out seam + reward step

## Overview

Closed the per-node run loop. The combat view now surfaces its resolved
`BattleResult` to the producer (`on_exit(result)`, V.64); the run-loop producer
applies progression through a single game-side orchestrator and shows a reward
panel. Trail → Prep → Combat → **Reward** → Trail now runs end-to-end over the
finished backend.

## What landed

- **`economy.apply_node_result(run, result) -> NodeResultSummary`** — the one
  reward-step orchestrator (V.69). Appends to `battle_log`, grants seeded income
  (win bonus on a win only) + fight tempest (cascades rank-ups), then on a win
  marks-cleared + advances (→ `VICTORY` if last node), else `DEFEAT` (draw counts
  as non-win). Pure, no I/O.
- **`ui/views/combat.py`** — `on_exit: Callable[[BattleResult], None]`; all 3 exit
  sites (`838` end-panel Continue, `984` control-bar Exit, `1053` Escape) pass the
  up-front-resolved `result` (commit-on-start).
- **`ui/views/reward.py`** — post-fight panel off `NodeResultSummary` + live `Run`.
- **`main.py`** — `_finish_combat` producer: `apply_node_result` → autosave
  (`save_run`, V.65) → reward panel; Continue pops the stack to the menu and pushes
  a fresh Trail (or stays on the menu when terminal — 15b wires Summary). Playfight
  producer updated to the 1-arg ignore.
- **Tests** — `tests/game/test_economy.py` (5: win/loss/draw/last-node-VICTORY +
  determinism), `tests/ui/test_reward.py` (1: construct + Continue). Suite **1419**.

## Process notes (AI collaboration)

- **Invariant-ahead-of-code reconciliation, not a bug.** V.64 already specified
  `on_exit(result)` (authored during the MVP-slice plan) while the live code still had
  the 0-arg `on_exit`. The focused T.15 plan flagged this as drift to *reconcile* in
  15a (bring code to spec), explicitly **not** a §B entry — the gap was designed, not a
  regression. Knowing the difference kept §B clean.
- **Cycle check before importing.** `economy.py` guarded `Run` behind `TYPE_CHECKING`,
  which looked like a hard import cycle. Grepped first: `models` does **not** import
  `economy` (the cycle is `economy → content → models`, one-way), so importing
  `CombatOutcome`/`RunStatus` at module top is safe. Verified instead of cargo-culting
  the deferred-import pattern.
- **Read the call sites, don't assume scope.** The plan claimed `result` was in scope at
  all 3 exit sites; confirmed it's resolved once at `combat.py:276/282` inside
  `build_combat_view`, so every nested handler closes over it. The 3-site change was
  mechanical once verified.
- **Determinism held for free.** `node_income`/`win_bonus` are seeded by `(seed,
  node_index)`, so the reward test asserts identical Amber across two fresh runs — and a
  Continue-after-load will reproduce the same income (V.2). No RNG introduced.
- **Visual self-verify interrupted.** Started a deep-link reward screenshot; the user
  interrupted (the scratch `shoot.py` still pointed at the prep port 8556 — would've shot
  the wrong page anyway). Fell back to the construction smoke test, which already
  exercises the render path + Continue wiring. Lesson: parameterize the screenshot port
  per preview, or the reused harness lies.

## Prompting-strategy reflection

The plan→spec→build chain paid off again: because the focused T.15 plan had already
verified the 3 `on_exit` sites, the cycle question, and the economy signatures, the build
was a straight execution with one user fork (exit semantics) resolved up front. The
`AskUserQuestion` on commit-on-start vs abandon was the right call to surface — it's a
roguelike-feel decision the code couldn't answer, and the determinism argument (re-prep =
save-scumming a fixed fight) made the recommendation land cleanly. Pattern holding: spend
the tokens in planning to verify seams against code, and the build stops being where
surprises live.
