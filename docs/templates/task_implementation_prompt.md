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

Before writing any code, thoroughly review:

- The code (existing modules touched by {{TASK_ID}})
- The {{TASK_ID}} plan document: [{{PLAN_PATH}}]({{PLAN_PATH}})
- SPEC.md rows for {{TASK_ID}} (§T, §V, §C as applicable)
- Any other specialized documentation referenced by {{TASK_ID}}
  ({{LIST_REFERENCED_DOCS}})
- Existing code at integration touch points to ensure clean integration
  ({{LIST_TOUCH_POINTS}})

Treat the design document review as mandatory groundwork, not optional context.

## Implementation Constraints

- Adhere to SPEC §V invariants (game/ pure, combat pure, no API key logging, etc.)
- Match existing module conventions and import boundaries
- Tests alongside code — unit tests minimum, integration where API touched
- No scope creep beyond {{TASK_ID}} + listed amendments

## Post-Implementation Tasks

- Update SPEC.md (§T row → done, new §V invariants if surfaced, §B entries for
  bugs caught mid-build) via `/spec`
- Update any other affected design documentation
  ({{PLAN_PATH}}, content rosters, system designs) to reflect changes made
- Write a journal entry at `docs/journal/{{YYYY-MM-DD}}_{{topic}}.md` capturing:
  the why, key decisions, deviations from plan, follow-ups
- Run `uv run pytest tests/` (or `pytest tests/`) — all green before declaring done
- Run `/check` to confirm no SPEC drift introduced
