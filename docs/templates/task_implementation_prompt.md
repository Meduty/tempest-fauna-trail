# Task Implementation Prompt Template

Fill `{{...}}` placeholders. Drop optional sections if unused.

---

# {{TASK_ID}} Implementation Prompt

## Primary Objective

Implement {{TASK_ID}} according to the plan document, applying the amendments
specified below before beginning implementation.

## Amendments

{{AMENDMENTS}}
_Bullet list of deltas vs plan doc. Write "None" if plan stands as written._

## Pre-Implementation Research

Complete the **Required reading before any task work** checklist from CLAUDE.md.
For {{TASK_ID}} that means, in order:

- SPEC.md rows for {{TASK_ID}} (§T, §V, §C as applicable) — the contract
- [ARCHITECTURE.md](../../ARCHITECTURE.md) — the system(s) {{TASK_ID}} touches + where they live
- The {{TASK_ID}} plan document: [{{PLAN_PATH}}]({{PLAN_PATH}})
- Any other specialized design docs referenced by {{TASK_ID}}
  ({{LIST_REFERENCED_DOCS}})
- The existing code at every integration touch point — read it, don't trust names
  ({{LIST_TOUCH_POINTS}})

Treat this review as mandatory groundwork, not optional context. Verify every
primitive/stat/function against the code — design-doc examples are illustrative and
sometimes wrong.

## Implementation Constraints

- Adhere to SPEC §V invariants (game/ pure, combat pure, no API key logging, etc.)
- Match existing module conventions and import boundaries
- Tests alongside code — unit tests minimum, integration where API touched
- No scope creep beyond {{TASK_ID}} + listed amendments

## Post-Implementation Tasks

- Update SPEC.md (§T row → done, new §V invariants if surfaced, §B entries for
  bugs caught mid-build) via `/spec`
- **Update the matching LIVING doc** (`docs/live/systems/<sys>.md` or
  `docs/live/content/<x>.md`) in this same change — it must match the new code, using
  the code's own taxonomy (real file/symbol names, not generic prose). A stub you just
  made true → flip its 🔶 to ✅ in `docs/live/README.md`.
- Leave FROZEN docs as records — do **not** retro-edit {{PLAN_PATH}} / `docs/design/`
  to match new code; distil the durable "how it works" into the living doc instead.
- Write a journal entry at `docs/journal/{{YYYY-MM-DD}}_{{topic}}.md` from
  [docs/templates/journal_entry.md](journal_entry.md) — capturing the why, key
  decisions, deviations from plan, follow-ups, and the **mandatory Process notes (AI
  collaboration) + prompting-strategy reflection** sections
- Run `uv run pytest` — all green before declaring done
- Run `/check` to confirm no LIVING-doc drift (SPEC, ARCHITECTURE, `docs/live/` —
  every cited path/symbol resolves; §V invariants + content counts hold)
