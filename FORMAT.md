# FORMAT — SPEC.md house style

The `spec` and `build` skills read this before mutating `SPEC.md`. It defines the
**encoding** (caveman compression) and the **shape** of each section. This repo's
SPEC.md is the source of truth for the live conventions — when this doc and a
long-standing SPEC.md pattern disagree, **match SPEC.md** and fix this doc.

> The generic `spec` skill ships a terser default table (`T5|.|task|cites`). This
> repo **overrides** it with the richer markdown tables below. Follow this file.

## Encoding (caveman)

Dense, technical, no fluff. Drop articles/filler/hedging; fragments OK. But:

- **Never compress identifiers, paths, code, numbers, or enum values** — `compose_stats`,
  `src/game/content.py:93`, `±10%`, `WeatherState.CLEAR` stay verbatim.
- Cite touch points as `file.py:line`.
- Prefer **percentage** (`×1.08`) over flat when a value scales across tiers/levels.
- One invariant / bug / task = one self-contained entry that reads without its neighbours.
- Tag each invariant/bug with the task that introduced it: trailing `(T.x)` / `(T.x, B.y)`.

## Numbering

- **Monotonic, never reused.** `§V`, `§B` ids only ever increase. A retired invariant
  is struck through or annotated, never renumbered; its number is never recycled.
- New entries append at the **end of their section** in numeric order (V.30 → V.31 → …).

## Sections

SPEC.md sections, in order: **§G** Goal · **§C** Context · **§I** Interfaces ·
**§V** Invariants · **§T** Tasks · **§B** Bugs / Backprop · **§D** Systems Yet To Be
Determined · **Implementation Order** · **Content Inspiration**.

### §V — Invariants
One bullet per rule, numbered, with the introducing task tagged:
```
- V.<N>: <the rule — what MUST hold, stated as an invariant, not a task>. (T.<x>)
```
Bold the load-bearing clause when it aids scanning. Reference related invariants inline
(`extends V.16`, `mirrors V.22`).

### §T — Tasks
A markdown pipe table, **6 columns**:
```
| # | Task | Files (code paths relative to `src/`; `docs/` and `tools/` repo-root relative) | Depends | Est | Status |
```
- **#** — `T.<n>` (split tasks: `T.<n>a` / `T.<n>b` along a real seam).
- **Task** — one-line scope; may pack sub-bullets inline with `;`.
- **Files** — every touched module + the task plan doc `docs/design/tasks/tN_*_plan.md`.
- **Depends** — `T.x, T.y` (state done/planned in the Planning Notes, not the cell).
- **Est** — `S` (<1h) · `M` (1-3h) · `L` (3-6h).
- **Status** — ✅ Done (implemented & tested) · 🔶 Partial · 📋 Plan (designed, not coded) ·
  ❌ Not started. The legend lives above the table; keep it in sync.

Per-task design depth goes in `docs/design/tasks/tN_*_plan.md` (see
`docs/templates/task_plan.md`) and a short note under **§T Planning Notes**, not in the
table cell.

### §B — Bugs / Backprop
One bullet per bug, dated, with cause → fix → guard:
```
- B.<N> [YYYY-MM-DD] <short cause>. **Cause:** <root cause>. **Fix → V.<x> (T.<y>):**
  <what changed + which invariant now prevents recurrence>. Touches <files>.
```
Every bug gets a §B entry; a new §V guard is optional but strongly preferred (the whole
point of backprop — an invariant that stops an agent repeating the mistake). Resolved bugs
may carry a `**RESOLVED [date] (T.x):**` clause.

### §D — Systems Yet To Be Determined
Live backlog of genuinely open design decisions, grouped by area. When an item is decided,
mark it `**LOCKED**` / `**RESOLVED [date] (T.x)**` inline and point to the plan doc that now
owns it — don't delete it (the trail matters).

## Discipline

- `spec` is the **sole mutator** of SPEC.md. Never edit SPEC inline from `build` or by hand
  mid-task; route changes through `/spec`.
- Show the diff, apply on user OK. Never silently rewrite a section the user didn't name.
- A task plan ends with a **"SPEC changes needed"** section enumerating the exact deltas
  (rows, invariants, §B, §D, Implementation Order) — applied only via `/spec`.
