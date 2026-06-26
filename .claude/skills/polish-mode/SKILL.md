---
name: polish-mode
description: |
  Operator-driven bug-polish loop. You orient on the whole game first
  (SPEC §G/§C, ARCHITECTURE, docs/live), then the operator playtests and
  reports bugs one at a time. Per bug: pin expected-vs-actual via clarifying
  questions, fix on a feature branch committing as you go, run a full review
  loop (the code-review, check, and spec skills), push, open a PR to main.
  Batches related in-context bugs into one branch/PR. Triggers when the user
  says "polish mode", "let's polish", "I'll playtest and report bugs", "start
  a polish session", or invokes `/polish-mode`.
---

# polish-mode — operator-driven bug-polish session

You are main Claude, paired live with a human operator who is **playtesting the
running game**. They find bugs; you fix them to merge. This is a session loop,
not a one-shot: it spans many bugs until the operator calls a wrap-up.

The seam: **operator owns finding + judging behavior** (they see the app), **you
own diagnosis, fix, review, and shipping**. Never claim a bug is fixed from code
reading alone — the operator confirms against the live game.

## PHASE 0 — ORIENT (once per session, before any bug)

Build the big picture so every later fix lands in context. Read, in order:

1. **SPEC.md §G** (goal) + **§C** (context) — what the game *is*, how it's meant
   to be played, the design goals.
2. **ARCHITECTURE.md** — the system map: combat engine, weather/API, run loop,
   prep/trail/shop views, save. How they interact and where each lives.
3. **docs/live/README.md** + skim the `docs/live/systems/` and
   `docs/live/content/` index — current truth for each subsystem.
4. **§V invariants** — scan all of them. These are the rails every fix must keep
   (V.1 game/ pure, V.2/V.14 determinism, V.5 6 weather states, etc.).

Then **`git pull` on main** (`git checkout main && git pull`) so you fix against
the latest merged state. Report a 4-6 line orientation summary (game idea, core
loop, the systems most likely to surface bugs) and tell the operator: **"Oriented
on main. Go playtest — report a bug when you hit one (what you expected vs what
happened)."** Wait.

## PHASE 1 — INTAKE A BUG

Operator reports. Pin it down **before touching code**:

- Restate as **Expected vs Actual** in one block. If either is fuzzy, ask.
- Use `AskUserQuestion` for genuine forks only — repro steps, which view/state,
  which champion/weather/node, intended-vs-bug ("is this wrong, or just
  surprising?"). Don't ask what the code or SPEC already answers.
- Locate root cause in code (Grep/Read; delegate a locator agent only if the
  operator asks). Cite as `file.py:line`. Check §B for prior history near the
  area and §V for the invariant the bug may be breaking.
- State the root cause + proposed fix in 2-4 lines. Get a nod, or surface a
  design fork if the "right" behavior is a judgement call (operator decides).

## PHASE 2 — FIX ON A FEATURE BRANCH

- **Branch first** off main: `git checkout -b <type>/<slug>` — `fix/…` for a
  defect, `polish/…` for a feel/UX tweak. Name from the bug, not the file.
- Fix in dialog. Commit meaningful steps as you go (don't wait for the end) —
  message style per the repo (`caveman:caveman-commit` if loaded; end with the
  `Co-Authored-By: Claude Opus 4.8` trailer per CLAUDE.md).
- Hold the rails: `game/` stays Flet-free (V.1); any cadence/"chance" mechanic
  is a deterministic counter, never RNG (V.2/V.14); theme tokens not hardcoded
  colors; HTTP off the main thread (V.4).
- Add/adjust a test that would have caught it. Run `uv run pytest` — green
  before review. On failure, invoke the **backprop** skill (bug → §B, consider
  a new §V) before retrying.
- **When the matching `docs/live/` doc is affected by the fix, update it in the
  same change** — a stale living doc is itself a bug (CLAUDE.md rule).
- Hand back to the operator to **confirm the fix in the live game** before
  review. If it's not actually fixed, loop here.

## PHASE 3 — FULL REVIEW LOOP

Once the operator confirms behavior, run the review cycle on the branch diff:

1. **code-review** — invoke the `code-review` skill (or `caveman:caveman-review`)
   on the working diff. Address real findings; note dismissed ones.
2. **check** — invoke the `check` skill: LIVING docs (SPEC, ARCHITECTURE,
   docs/live) vs code. Every cited path/symbol must resolve, §V must hold, counts
   must match. Fix drift the change introduced.
3. **spec** — if behavior/contract changed, invoke the `spec` skill to amend the
   relevant §T/§V/§B (and `/backprop` the bug into §B with any new guard
   invariant). Pure code-level fixes with no contract change skip this — say so.

Re-run `uv run pytest` after review edits. Append a `docs/journal/` entry for any
non-trivial fix (with the mandatory "Process notes (AI collaboration)" section)
per CLAUDE.md.

## PHASE 4 — SHIP

- Commit the review/doc edits.
- `git push -u origin <branch>`.
- Open the PR to **main** with `gh pr create` — body states Expected/Actual,
  root cause (`file.py:line`), the fix, tests added, review-loop outcome, and any
  SPEC deltas. End the body with the `🤖 Generated with [Claude Code]` line per
  CLAUDE.md. **Confirm with the operator before pushing/opening** — it's
  outward-facing.

## BATCHING — MULTIPLE BUGS PER BRANCH

The operator may report more bugs that are **in the same context** (same
view/system/branch scope) before you ship. When that happens, **stay on the
branch** and loop Phase 1→2 for each, so one PR catches several improvements.
Only split to a new branch when a bug is unrelated to the current diff (keeps PRs
reviewable + revertable).

## THE DECISION POINT — after each ship (or batched fix)

Whenever a unit of work is done, ask the operator which way to go:

- **New bug** — they keep playtesting; loop back to Phase 1 (new branch if
  unrelated, same branch if in-context per Batching).
- **Wrap-up** — summarize the session: bugs fixed, branches/PRs opened, tests
  added, SPEC deltas, anything left for a follow-up.

Use `AskUserQuestion` for this fork.

## NON-GOALS

- Don't declare a bug fixed without the operator confirming in the live game.
- Don't commit straight to main; don't push or open a PR without the nod.
- Don't bundle unrelated fixes into one PR.
- Don't skip the review loop ("it's a one-liner" is not an exemption — the
  check/spec passes are how drift stays out of the merge).
- Don't edit SPEC.md directly — that's the spec skill's job.
