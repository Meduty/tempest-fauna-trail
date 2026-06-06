---
name: plan
description: |
  Write a §T task plan doc (`docs/design/tasks/tN_*_plan.md`) before any
  build. Native single-thread, no sub-agents. Runs the CLAUDE.md "Planning a
  §T task" loop: required reading → verify every primitive against code →
  content↔design drift check → ask genuine forks first → emit a plan that
  ends in the exact `/spec` deltas. Writes only the plan doc; never mutates
  SPEC.md (that is the spec skill) and never edits code (that is build).
  Triggers when the user asks to plan a task, write a plan, scope a §T row,
  or design the approach before building (`plan §T.29`, `plan --next`,
  `write the plan for items`, `scope T.34`).
---

# plan — write a §T task plan

Single-thread native. You are main Claude. No swarm. Output is one file:
`docs/design/tasks/tN_<topic>_plan.md`. This is the planning half that feeds
the build skill; keep the seam clean — plan reasons + writes the doc, build
executes it, spec mutates SPEC.md.

## LOAD

1. Read `SPEC.md`. If missing → tell user to invoke the spec skill first. Stop.
2. Read `docs/templates/task_plan.md` — the plan doc structure. Mirror it.
3. Parse invocation args:
   - `§T.n` / `T.n` → plan that row.
   - `--next` → lowest-numbered row with status `📋 Plan` (or `.`/`~`) that has no plan doc yet.
   - a description with no row yet → plan a *new* task; the doc's header states it needs a `/spec` row-add.

## REQUIRED READING (mandatory — CLAUDE.md groundwork)

Before writing a line of plan, read in order. This is the contract, not optional context:

1. **SPEC.md** — the target §T row(s), **every §V invariant** that could apply, §B bug history near the area, relevant §D deferrals.
2. **ARCHITECTURE.md** — the system(s) the task touches, how they interact, where they live.
3. **The LIVING doc** — `docs/live/systems/<sys>.md` or `docs/live/content/<x>.md` for the area. Current truth; trust over frozen plans. If a 🔶 stub, fall through to design doc + code.
4. **Prior task plans** — the `docs/design/tasks/tN_*_plan.md` for dependencies + 1-2 recent analogous plans to mirror shape (e.g. `t28_trait_effects_plan.md`, `t30_ability_catalog_plan.md`, `t31_augment_system_plan.md`).
5. **Every design doc in scope** — the `docs/design/{systems,content}/*.md` for the systems/rosters touched. FROZEN — verify against code.
6. **Every code touch point** — read the actual modules + integration seams, not their names.

## VERIFY (design docs lie)

Hard-won rules — a miss here costs a whole build:

- **Grep every primitive/stat/function before citing it.** `effect_systems_design.md` examples use stat keys that don't exist (`ability_power`→`intelligence`; mana is per-`ActiveSlot`, not a `Piece` stat). Confirm the real key/signature. Cite as `file.py:line`.
- **Content↔design drift check.** Diff the code's live vocabulary (tags, registries, rosters) against the `*_catalog.md` / `*_roster.md`. Reconcile in the plan; add a §V-guard so it can't recur. (e.g. `CALLING_TAGS` once carried 4 dead T.5 tags + omitted `Packmate`.)
- **Determinism is non-negotiable (V.2/V.14).** Any "chance"/"every few" mechanic → deterministic cadence counter (like `crit_counter`), never RNG. Sims stay byte-identical.

## ASK (before writing, not after)

Use `AskUserQuestion` for genuine design forks only — scope cuts, vocab
reconciliation, mechanic fidelity, model-location. Investigate origins (git
history, prior plans) **before** asking the user to decide. Don't ask what the
code already answers. Resolved-here proposals are overridable; list them in the
plan's Open Questions.

## WRITE PLAN

Write `docs/design/tasks/tN_<topic>_plan.md` from the template. Required sections:

- Header block: status (new row vs flip), depends (+ which deps are unbuilt and why that gates), resolves (§D/§T), design source-of-truth docs with anchors, what this plan adds beyond them.
- **0. Substep split** (if large) — split along a *real* seam (declarative content vs engine primitives; combat-facing vs meta). Each substep ships + tests independently; `b` depends on `a`.
- **1. Scope** — in/out, with the why for each out.
- **2. The gap today** — table: piece | `file.py:line` | state (✅/🔶/❌/🔴-drift).
- **3. Architecture** — per subsystem: real verified type/shape, plug-in point `file.py:line`, application order, integration wrinkles, cross-task seams. New primitives → fidelity policy (cadence counters; Tier-A full vs Tier-B MVP-proxy).
- **4. Decisions** — thresholds/gating/model-location with proposal + rationale.
- **5. Authored values** — the numbers catalogs left as concepts. Prefer `mul` over flat where stats scale across tiers. Flag first-pass/tunable.
- **6. Content/roster audit + reconciliation** — drift fixes with git-confirmed origin + V-guard.
- **7. Open questions** — resolved-here (overridable) vs still-open/deferred.
- **8. Test plan** — counting/scope/determinism/regression/V-guard. Explicitly test any cadence mechanic is RNG-free (fixed-seed + `workers=1` byte-identical).
- **9. Acceptance criteria** — numbered, checkable; one set per substep if split.
- **10. SPEC changes needed** — the exact `/spec` deltas (see below).
- **11. LIVING docs to update** — which `docs/live/` doc(s) the build must update on landing (+ 🔶→✅ flip).

## §10 — SPEC CHANGES NEEDED (the handoff payload)

Enumerate the precise deltas the spec skill will apply *on user OK only*:

- §T row(s): id, goal line, files-cell, depends, est, status.
- New §V invariants (with the recurrence each guards).
- §B backprop entries for any drift caught while planning.
- §D updates (resolved/added).
- Implementation Order placement.

The plan **proposes** these; it does **not** touch SPEC.md. Applying them = a
separate `/spec` call after the user approves.

## WRITE POLICY

- Write exactly one file: the plan doc under `docs/design/tasks/`.
- **Never** edit SPEC.md — propose deltas in §10, user runs the spec skill.
- **Never** edit code — that is the build skill.
- Don't write a journal entry (that's a build/landing step).

## HANDOFF

End by telling the user the two next moves, in order:
1. `/spec` to apply the §10 deltas (add/flip the §T row, new §V, §B).
2. `/build §T.n` to execute the approved plan.

## NON-GOALS

- No sub-agents. No parallel workers. Main thread only.
- No code edits, no SPEC edits, no test runs.
- No speculative scope beyond the chosen task + its honest substeps.
