---
name: build
description: |
  Plan-then-execute implementation against SPEC.md. Native single-thread
  loop, no sub-agents. On test or build failure, auto-invokes the backprop
  skill before retrying — a failed verification always considers whether
  a new §V invariant would prevent recurrence. Triggers when the user asks
  to build, implement, execute the spec, or tackle a specific §T task
  (`build §T.3`, `build --next`, `implement next task`, `run the build`).
  Expects SPEC.md to exist; if not, defers to the spec skill.
---

# build — implement spec

Single-thread native plan→execute. You are main Claude. No swarm.

## LOAD

1. Read `SPEC.md`. If missing → tell user to invoke the spec skill first. Stop.
2. Read `FORMAT.md` once if not loaded.
3. Parse invocation args:
   - `§T.n` → that task only
   - `--next` → lowest-numbered row with status `.` or `~`
   - `--all` or empty → every `.` row in §T order

## PLAN

Native plan mode. For chosen task(s):

1. Cite every §V invariant that applies. Plan must respect all.
2. Cite every §I interface touched. Plan must preserve shape.
3. List files to create / edit.
4. List tests to add or update (one per invariant touched).
5. Name verification command (test, build, lint).

Show plan. Wait for user OK unless auto mode.

## EXECUTE

Per task in order:

1. Flip §T.n status cell `.` → `~`. Just write to SPEC.md.
2. Edit code per plan.
3. Run verification command.
4. **Pass** → check `ARCHITECTURE.md` for drift (see "ARCHITECTURE drift"); reconcile if needed. Flip `~` → `x`. Next task.
5. **Fail** → invoke backprop skill. Do NOT retry blindly.

## FAIL → BACKPROP

On test/build failure:

1. Read failure output.
2. Ask: is failure (a) my code bug, (b) spec wrong, or (c) unspecified edge case?
3. If (a) → fix code, re-run. No spec change.
4. If (b) or (c) → invoke spec skill with `bug: <cause>` first, let it update §V and §B, then resume build against updated spec.

Rule: never silently fix root-cause without considering backprop. §B is the memory that stops recurrence.

## WRITE POLICY

- Only flip §T status. No other SPEC.md edits from build.
- Other spec edits → invoke spec skill.
- Commit after each §T completes. Message: `T<n>: <goal line>` + §V cites.

## VERIFICATION

Task `x` only if:
- Verification command exits 0.
- New test(s) added per plan.
- No §V invariant regressed (run full test suite at end).
- `ARCHITECTURE.md` drift checked + reconciled (see "ARCHITECTURE drift").

## ARCHITECTURE drift (post-implementation)

After a task's code lands and tests pass, before marking it `x`, check
`ARCHITECTURE.md` — the system map (how systems work + interact, where each
lives). Grep it for the vocabulary your change touched (renamed primitives,
moved responsibilities, new modules/entry points/fields). Reconcile when the
change:

- added / removed / renamed a module, or moved a responsibility between files;
- changed how a system works or how two systems interact;
- added a first-class data field, entry point, or seam a future reader looks up.

Edit `ARCHITECTURE.md` directly — it is **not** SPEC, so no spec skill is needed.
Fix only statements the change made **false** (a stale path, a deleted
primitive, a renamed seam); generic descriptions that stay true need no edit. A
purely internal change with no map-level effect is a no-op — but the check is
**mandatory**, and the task report states the outcome ("no drift" or what was
reconciled).

## NON-GOALS

- No sub-agents. No parallel workers. Main thread only.
- No progress dashboards. `cat SPEC.md | grep §T` is the dashboard.
- No speculative work beyond chosen task scope.
