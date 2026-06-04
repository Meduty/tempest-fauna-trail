# 2026-06-04 — Documentation sweep: ARCHITECTURE.md, journal mandate, agent reading-gate

A documentation-only session (no `src/` changes). Audited the repo's doc state, then
closed the gaps: backfilled missing journals, authored the big-picture system map,
mandated process-reflection in journals, wired a required-reading gate across every
agent surface, and cleaned repo cruft. Companion to the same-day
[barriers/engine/weather-metric backfill](2026-06-04_barriers_engine_unification_weather_metric_fix.md).

## What changed

1. **`ARCHITECTURE.md`** (new, repo root) — the system map: layered architecture +
   isolation invariants, combat-engine deep-dive (`compile_loadout → CombatContext →
   loop_new.run → recorder`), the ability/passive/status framework, the two weather
   systems, content/scaling/route/encounter/economy, data models, API layer, dev
   tooling, determinism doctrine, a "where do I find X" index, and an end-to-end fight
   trace. Linked from README + CLAUDE.md. Positioned as the third source of truth after
   SPEC and the per-system design docs.
2. **Journal template + mandate** — new [docs/templates/journal_entry.md](../templates/journal_entry.md);
   CLAUDE.md now requires every entry to carry a **Process notes (AI collaboration)**
   section + a **prompting-strategy reflection**.
3. **Required-reading gate** — one canonical list in CLAUDE.md ("SPEC → ARCHITECTURE →
   task plan → touched design docs → touched code"), referenced (not copied) from the
   three `.claude/rules/*` path guardrails, both `docs/templates/*`, and a new
   `.github/copilot-instructions.md` aligned to CLAUDE.md.
4. **Backfilled journals** — the barrier/engine-unification/weather-metric entry that
   four prior commits had skipped.
5. **Cleanup** — untracked + gitignored LaTeX byproducts (`*.aux`/`*.out`) and ~10 MB of
   regenerable R caches (`*.rds`) under `reviews/`; fixed SPEC §T path drift
   (`game/combat.py` → `game/combat/` in T.3/T.23/T.24); fixed stale README Status
   (claimed shipped systems — cache-refresher T.7, encounter-gen T.19 — as "planned").

## Why (the part SPEC compresses out)

The repo had **strong contract docs (SPEC) and strong design fragments, but no map**.
A newcomer (human or agent) could read every `docs/design/` file and still not know how
combat actually wires together at runtime, or which file to open to change weather.
SPEC is deliberately a *plan/contract* — it says what must hold, not how the pieces
connect or where they live. ARCHITECTURE.md fills that exact hole: navigation + runtime
behavior, verified against code.

The **journal process-mandate** exists because this repo is a vibe-coding case study,
and the most valuable, least-recoverable signal — where the agent drifted, what the
spec saved, how prompting evolved — lives nowhere in the diff. Making it a required
section is the only way it survives.

The **required-reading gate** exists because the failure mode it prevents already
happened *in this very session* (see Process notes): a doc that paraphrases the spec
inherited the spec's unbuilt claims. Forcing "read SPEC + ARCHITECTURE + plan + touched
code, and verify against code" before any edit is the systemic fix.

## Decisions

- **ARCHITECTURE.md is a separate root doc, not a README section.** README stays the
  pitch/quickstart; the system map is too long to bloat it and wants its own stable
  anchor for cross-linking. Best-practice default; README links to it.
- **Single canonical reading-gate, thin pointers everywhere else.** The full 5-item list
  lives once (CLAUDE.md). Rules files and templates *reference* it. Copilot is the one
  exception — it gets a self-contained copy because GitHub Copilot won't read CLAUDE.md
  automatically, but it explicitly declares "CLAUDE.md and SPEC.md win" so it can't
  silently fork.
- **`.rds` caches removed from git** (user call): the committed reports are the durable
  artifact; the caches regenerate from sim runs. `*.rds` now gitignored.
- **Did not "fix" the reviews md split** — `build_pdf.py` (mega3) reads its md from
  `mega_sim/` while mega6/7 builders read from `reviews/` root. The split is
  builder-dictated; moving md would break a builder. Left as-is.

## Process notes (AI collaboration)

- **Agent error caught in self-review — the big one.** The first draft of ARCHITECTURE.md
  documented `resolve_combat(team, enemies, weather, run_mods=None)` and an "optional
  `run_mods` defaults to None" determinism note — straight from SPEC V.2. But `run_mods`
  is the **T.31 augment system, which is `📋 Plan`, not built**. The real signature is
  `(team, enemies, weather, *, node_id="")`. Same class of error in two more places:
  `CombatContext(pieces, bus, board)` (real: `(pieces, bus, weather, seed,
  board_state=None)`) and hook event names (`on_attack` → real `on_attack_landed`; the
  whole event vocabulary was guessed, not grepped). All four were caught only because the
  user demanded a "very deep review against the actual code", which forced a file-by-file
  verification pass.
- **Root-cause / guardrail.** SPEC §V invariants routinely **bundle unbuilt tasks** —
  V.2 describes the T.31 `run_mods` contract years before it exists, tagged `(T.31)`. A
  system map that paraphrases SPEC therefore inherits aspirational claims as if shipped.
  This is the *same* failure the CLAUDE.md planning rules already warn about for design
  docs ("design-doc examples lie — grep them"). ARCHITECTURE.md is now a **third doc that
  can lie unless code-checked**, and the new required-reading gate makes "verify against
  the code" mandatory for exactly this reason. ARCHITECTURE.md now labels every
  built-vs-planned boundary explicitly (e.g. "run_mods is the planned T.31 extension, not
  yet in code").
- **Drift caught in shipped docs.** README Status listed `cache-refresher` and
  `encounter generator` as "planned" — both are `✅ Done` in SPEC §T. Docs that aren't
  on the `/spec` backprop path rot silently; only SPEC stays current because the workflow
  forces it.
- **User pre-empted a dupe.** Mid-task the user asked to check for an existing "Required
  reading" instruction before adding one, and to align Claude + Copilot. Good instinct:
  the natural move (paste the gate into every rules file) would have created five copies
  that drift. The reference-one-canonical-source pattern was the result.
- **Dogfooding.** The journal template authored this session was immediately used by the
  backfill entry and by this one — the format got a real test the moment it shipped.

### Prompting-strategy reflection

- **Highest-leverage prompt of the session: "review ARCHITECTURE deeply, check against
  the actual code and design docs."** That single instruction converted a
  plausible-sounding doc into a verified one and caught the `run_mods` error that would
  otherwise have shipped as authoritative. Lesson reinforced: for any doc that
  *describes* code, verification-against-code must be its **own explicit step**, never
  assumed to have happened during authoring. Writing and verifying are different jobs;
  the model will happily emit confident, spec-consistent, code-inconsistent prose.
- **Iterative narrowing worked.** The session went investigate → 4-part directive →
  "check README too" → "review architecture deeply" → "wire the reading gate" → "check
  dupes / align Claude+Copilot" → "journal". Each refinement caught something the prior
  scope missed (README drift, the run_mods bug, the dupe risk). The takeaway is not
  "under-specify on purpose" but that **a review/verification turn after a generate turn
  is where most defects die** — budget for it explicitly rather than treating the first
  artifact as done.
- **Evolving heuristic for this project:** treat the doc layer with the same suspicion
  the planning rules already apply to design docs. SPEC = contract (may describe the
  future), ARCHITECTURE = map (must match present), journal = narrative (must be honest
  about misses). Each has a different truth-horizon; conflating them is the recurring
  trap.

## Files

New: `ARCHITECTURE.md`, `docs/templates/journal_entry.md`,
`.github/copilot-instructions.md`, this entry + the barrier/engine backfill entry.
Modified: `CLAUDE.md`, `README.md`, `SPEC.md` (§T paths), `.gitignore`,
`.claude/rules/{api,game-logic,flet-ui}.md`,
`docs/templates/{task_plan,task_implementation_prompt}.md`.
Removed from git: `reviews/mega_sim/*.{aux,out,rds}`.

## Follow-ups

- Consider a lightweight CI/doc check that flags ARCHITECTURE.md claims citing symbols
  absent from `src/` (catch built-vs-planned drift mechanically).
- Re-verify ARCHITECTURE.md after each system task lands (especially T.28/29/31 — the
  trait/item/augment registries and `run_mods` it currently marks "planned").
- Backfill is now caught up; keep the one-section-per-conceptual-change discipline so the
  next sweep isn't another archaeology dig.
