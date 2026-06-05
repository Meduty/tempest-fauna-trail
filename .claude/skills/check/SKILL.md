---
name: check
description: |
  Read-only drift detector. Diffs the always-current docs (SPEC.md,
  ARCHITECTURE.md, docs/live/) against the actual code and reports
  violations grouped by severity. Writes nothing — it only reports, then
  suggests the spec or build skills as the remedy. Triggers when the user
  asks to check drift, audit the docs/spec, verify invariants, or ask
  whether code still matches the docs. Phrasings: "check drift", "audit
  the spec", "audit docs/live", "does the code still match §V", "check
  invariants", "is the living doc stale", "docs vs code".
---

# check — read-only drift detector

You audit the project's **LIVING docs** against the code and report drift.
You **write nothing** — no edits, no commits. You end by pointing at the
remedy (the spec or build skill, or a direct edit), never by applying it.

LIVING docs (must match code — auditing them is the whole job):
- `SPEC.md` — the contract (§G/§C/§I/§V/§T/§B).
- `ARCHITECTURE.md` — the system map.
- `docs/live/**` — per-system / per-content living references.

FROZEN docs (point-in-time records — **do not** flag as drift):
- `docs/design/**` (task plans, proposals, as-designed rosters)
- `docs/journal/**`
Each FROZEN doc carries a `Status: FROZEN (…)` header; if one is missing the
marker, that itself is a 🟡 finding (it could be mistaken for living).

## SCOPE (args)

- no args / `--all` → audit every LIVING doc.
- `--spec` → SPEC.md only.
- `--arch` → ARCHITECTURE.md only.
- `--live [glob]` → docs/live/ (optionally one file/glob).

## PROCEDURE

Read `FORMAT.md` once if auditing SPEC. Then, for the chosen scope:

### 1. Code-reference resolution (mechanical, do this first)

Every LIVING doc cites code in backticks. Extract and verify each citation
resolves in the current tree. Use grep/Read — do not trust memory.

- `path/to/file.py` → file exists.
- `file.py:NN` → file exists **and** has ≥ NN lines (and, when feasible, the
  symbol named alongside it is near that line — line drift is 🔵, a missing
  file/symbol is 🔴).
- `` `module.func` `` / `` `ClassName` `` / `` `CONSTANT` `` → a matching
  `def`/`class`/assignment exists somewhere in `src/`.
- A doc claim "X is the only/sole place …" → grep proves it is singular.

Helper sweep (run, then read the misses):
```
grep -rhoE '`[A-Za-z_][A-Za-z0-9_./]*\.py(:[0-9]+)?`' docs/live SPEC.md ARCHITECTURE.md \
  | tr -d '`' | sort -u
```
For each path token, confirm it exists; for `:NN`, confirm line count. Report
every unresolved token.

### 2. Invariant / interface drift (SPEC, judgement)

- For each §V invariant in scope: find the code that should enforce it; confirm
  it still holds. (e.g. V.2 determinism → resolve_combat is pure & seeded; V.29
  → exactly one tick loop; grep proves no second `def run(ctx`.)
- For each §I interface: confirm the real signature/shape matches.
- For §T rows marked ✅ Done: spot-check the named files exist and do the thing.

### 3. Content-count drift (docs/live/content + SPEC §V counts)

Where a doc asserts a count ("60 champions", "6 weather states", "648 role
combos"), compute it from code/registries and compare.

## SEVERITY

- 🔴 **broken** — a cited path/symbol does not exist, or a §V invariant is
  violated by current code, or a doc states something the code contradicts.
- 🟡 **drift** — likely-stale prose, a missing `Status:` marker, a count that
  no longer matches, a FROZEN doc referenced as if living.
- 🔵 **note** — line-number skew, cosmetic, or "verify by hand" items.

## OUTPUT

One finding per line:

```
<doc>:<line?> <emoji> <severity>: <what's wrong>. → <remedy>
```

End with a 3-line summary: counts per severity, and the single suggested next
action (invoke the spec skill for SPEC fixes, the build skill for code, or a
direct edit for docs/live prose). **Do not perform the remedy.**

## NON-GOALS

- No writes, no commits, no sub-agents.
- Don't audit FROZEN docs for staleness (only for a missing marker).
- Don't re-derive the spec; only compare what's there to the code.
