# Task Plan Template

Fill `{{...}}`. Drop optional sections if unused. Mirrors the structure of
`t28_trait_effects_plan.md` / `t30_ability_catalog_plan.md` / `t31_augment_system_plan.md`.

**Before writing:** complete CLAUDE.md → "Required reading before any task work"
(SPEC.md, [ARCHITECTURE.md](../../ARCHITECTURE.md), the **LIVING doc** for the area
[`docs/live/`](../live/README.md), prior task plans, the touched design docs, the
touched code). Then grep every primitive/stat/function you cite
(design-doc examples lie — see CLAUDE.md "Planning a §T task"). Run a content↔design
drift check. Ask genuine open questions (`AskUserQuestion`) *first*. Investigate
origins (git history) before asking the user to decide anything.

---

# {{TASK_ID}} Plan — {{TITLE}}

> **Status:** plan — ready for review. ({{is the §T row new, or a status flip? state it}})
> **Depends:** {{T.x (state — done/planned), …}}. {{note which deps are unbuilt and why that gates content}}
> **Resolves:** SPEC §{{D.n / T.x half / …}}.
> **Design source of truth:** {{catalog.md, roster.md, effect_systems_design.md §n, …}} — list every doc, with section anchors.
> **What this plan adds beyond those:** {{authored values the catalog left as concepts; new primitives; reconciliations; fidelity policy}}.
> **Not a §T row yet / status flip** — needs `/spec` to {{add row / flip status}}; §{{last}} lists the deltas. Do not edit SPEC inline.

## 0. Substep split (optional — `{{TASK_ID}}a → {{TASK_ID}}b`)
_If the task is large, split along a real seam (declarative content vs engine
primitives; combat-facing vs meta/cross-task). Define each substep's scope,
deps, files, and "done when". b depends on a._

## 1. Scope
**In scope:** {{modules + outputs + tests}}.
**Out of scope:** {{what belongs to which other task, and why}}.

## 2. The gap today
_Table: piece | where (`file.py:line`) | state (✅/🔶/❌/🔴-drift). What scaffolding
exists vs what's missing. Note any drift in red._

## 3. Architecture
_Per subsystem: the type/shape (ported from the substrate doc, **with real stat
keys verified against code**), where it plugs into existing code (`file.py:line`),
application order, and integration wrinkles (things known at compile time vs via
events, mana-per-slot vs base-stat, etc.). Cross-task seams called out._

### 3.x New primitives + fidelity policy (if any)
_Determinism mandatory: cadence counters, never RNG. Tier-A (build full) vs
Tier-B (MVP-proxy now, flagged) if the user chose to simplify._

## 4. {{Decisions that need stating}}
_Thresholds, gating, model-location choices — with the proposal and rationale._

## 5. Authored values
_The numbers the catalog left as "concepts only". Prefer percentage (`mul`)
modifiers over flat where stats scale across tiers. Flag as first-pass/tunable._

## 6. Content / roster audit + reconciliation
_Vocabulary drift fixes (with git-confirmed origin), completeness audit, V-guard._

## 7. Open questions
**Resolved here (proposals, overridable):** {{…}}
**Still open / deferred:** {{…}}

## 8. Test plan
_Counting/scope/determinism/regression/V-guard. Explicitly test that any cadence
mechanic is RNG-free (fixed-seed + `workers=1` byte-identical)._

## 9. Acceptance criteria
_Numbered, checkable. One per substep if split._

## 10. SPEC changes needed (for `/spec`)
_Enumerate exact deltas: §T row(s) + status + files + depends + est; new §V
invariants; §B backprop entries for any drift caught; §D updates; Implementation
Order. Applied only on user OK._

## 11. LIVING docs to update
_Which `docs/live/` doc(s) this task must update on landing (and whether it flips a
🔶 stub → ✅). The doc must match the new code in the code's own taxonomy; `/check`
must pass. FROZEN docs (`docs/design/`) are left as-is._
