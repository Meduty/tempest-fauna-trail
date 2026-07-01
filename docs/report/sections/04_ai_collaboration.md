# AI-Agent Collaboration

Tempest Fauna Trail was built as a deliberate **vibe-coding case study**: almost
all of the code was written by an AI coding agent (Claude Code) driven by a human
operator, under a process designed to keep that collaboration honest. The project
treats the *how we worked with the agent* as a first-class artifact — every
non-trivial milestone carries a mandatory **"Process notes (AI collaboration)"**
section and a **prompting-strategy reflection** in its journal entry, precisely
because that signal is invisible in the diff and unrecoverable later.

This chapter synthesizes those ~30 journaled reflections into the durable lessons.
It is the part of the documentation that no amount of reading the source can
reconstruct: where the agent drifted, what the process caught, and how the way of
driving the agent evolved over the eight-week build.

## The working model

The collaboration settled into a repeatable shape early and held:

> **The human steers design at the decision forks; the agent runs the mechanical
> build.** The operator resolves genuine forks up front, then lets the agent
> execute against a plan — "resolve the design forks, then let the agent run" is
> described across the later journals as *the* dominant pattern on this project.

Concretely this is enforced by a spec-driven workflow (detailed in the next
chapter): the agent writes a plan doc, the human approves it, the spec is amended,
then the build is a comparatively low-entropy transcription of an already-settled
design. The recurring refrain — *"spend the tokens in planning where a mistake is
cheap to fix, and the build stops being where surprises live"* — is the thesis of
the whole method, and the journals repeatedly record it paying off.

## The recurring lessons

### 1. Design docs lie — verify every primitive against the code

The single most-repeated lesson. Design documents and even the spec contain
**illustrative-but-wrong** examples, and the agent will confidently emit
spec-consistent, code-inconsistent prose. A partial catalogue of what
verification-against-code caught before it shipped:

- `ability_power` / `mana_max` / `attack_damage` — stat keys that **do not exist**
  (the real key is `intelligence`; mana is per-`ActiveSlot`, not a `Piece` stat).
- `resolve_combat(..., run_mods=None)` documented as current — but `run_mods` was
  an **unbuilt future task** (T.31); the real signature had no such argument.
- Hook event names guessed (`on_attack`) rather than grepped (`on_attack_landed`).
- `CombatOutcome.TEAM_WIN` / `BattleResult.winner` in test assertions — the real
  values were `CombatOutcome.WIN` and `BattleResult.outcome`.
- `ft.BarChart` mandated by the spec, but **Flet 0.85 removed the chart widgets
  from core** — the framework's own API had drifted.

The generalized rule the project adopted: **writing and verifying are different
jobs.** For any doc or handler that *describes* or *reads from* code, a
verification-against-code pass must be its own explicit, budgeted step — never
assumed to have happened during authoring. The lesson was eventually extended even
to *test assertion targets* (enum values, dataclass field names), which are easy
to skip because they "obviously" match the interface you just wrote.

### 2. Self-review is a separate, load-bearing step — green tests are not "done"

Repeatedly, an explicit adversarial review pass — prompted by the operator as
*"review the plan for weak spots"* or *"review the changes so far"* — caught real
defects that a **passing test suite did not**:

- A combat-view HP bar that would freeze through ability bursts (caught at *plan*
  time, before implementation — described as the single highest-leverage moment of
  that session).
- A `milli_AS` value that shipped desynced under weather (weather scaled
  `attack_speed` but not its tiebreak twin).
- A save-load path that would leak a raw `ValueError` past the typed-error contract.

The distilled principle: *"tests passing is not 'done'; an explicit adversarial
self-review is a separate step and it keeps earning its keep."*

### 3. Distrust the measurement — a metric reading zero is a claim about the metric

Two of the sharpest bugs were **instrumentation lies**, not system bugs:

- A roster sim reported **0 casts** in a 12,000-tick fight. The first instinct
  ("pre-existing, out of scope") was wrong; the operator pushed *"question your
  sim."* Instrumenting the actual code path showed casts *were* firing — the
  recorder's `_on_cast` was a silent no-op, so every cast was invisible.
- Identical mirror-match cells reading ≠ 50% win rate exposed a genuine engine
  **side-bias** in the tiebreaker, affecting every prior combat result.

Rule adopted: when a metric shows a suspicious extreme (0 / all / exactly 50%),
**wrap the function and instrument the path — do not grep the rendered output.**
A number that "won't move" under a lever is often a *mixed* metric hiding two
problems; slice it one dimension finer before blaming the lever.

### 4. Every bug becomes an invariant — the backprop reflex

The project's most distinctive discipline: a bug fix is not complete until the
team asks *"what invariant would have caught this?"* and, where possible, adds one
that turns the failure into a **red test**. This "backprop" reflex converted
one-off patches into durable guards throughout — a NaN-weather averaging bug became
an invariant; a dead-stat balance hole became a CI axis↔scaling guard that
*immediately* flagged two more dead-stat units a hand-audit had missed; a
mana-per-slot duplication became a slot-count-invariance guard. The invariants
double as **agent guardrails**: they encode, in an executable form, the exact
drifts a future agent would otherwise re-introduce.

### 5. The human catches the hacks and redirects the method

The operator's interventions were consistently high-leverage, and the journals are
candid that the human was often right against the agent's in-flight approach:

- *"This seems more like a hack… one logic that handles single/null/multi"* —
  forced a materially cleaner multi-slot architecture than the agent's planned
  `secondary=` kwarg.
- *"Blast is big, blast is big"* — vetoed the agent's twice-proposed scope
  shortcuts in favour of the full, correct refactor.
- *"Just run normal sims, compare win-rates across roles"* — beat the agent's
  synthetic-harness instinct; the right experiment design emerged from the
  operator's domain corrections, not the agent's first plan.
- *"If the issue is developing blind, can you change that?"* — flipped a
  self-imposed constraint (see below).

The emergent rule: **when the user smells a hack, stop and re-derive the seam — do
not defend the in-flight approach.** The recommendations the agent surfaced existed
largely so they could be *cheaply overridden*; the operator overrode roughly half,
which is the point of making forks legible.

### 6. Ask after a cheap investigation, not instead of one

`AskUserQuestion` forks worked best when the agent **verified a premise first**,
then posed the decision with a recommendation and the concrete trade-off. Twice,
feeding the user a code fact *mid-question* flipped their answer (a "does this
already work?" turned into a real bug fix once the agent showed the helper didn't
filter the gate; a "build it now" reversed to "defer" once the agent showed the
content already existed). The pattern: **verify → state the fact → re-pose the
fork.** For the rote decisions (dozens of invented stat magnitudes), a
**decide-and-flag** approach kept momentum — default the value, log it as a numbered
flag for later review, rather than blocking on each one.

### 7. Headless UI: the operator is the visual oracle — until it isn't

The agent cannot see rendered Flet output, so early UI work treated the human's
screenshots as the only test oracle. Mitigations that worked: a **fake `Page`
harness** to catch import/attribute/exception errors, and leaning on pure,
testable playback models for the parts that *are* testable. But the most important
lesson was to **not bake a constraint into the recommendation before checking it
is real** — when pushed, the agent found it *could* self-verify via `flet run -w`
plus Playwright screenshots, which flipped the entire interaction model. The
subtler traps were environmental: **web ≠ desktop** for background-thread→UI safety
(a repaint that renders in the web build silently no-ops on desktop), and a stale
**service-worker** frame that nearly sent the agent chasing a phantom bug.

## How the collaboration evolved

The journals show a clear trajectory across the eight weeks:

- **Early entries** are build- and bug-post-mortems written *after* the work.
- **Mid-project**, the discipline of writing process notes for a *plan* (before any
  code) began surfacing drifts — an axis-count discrepancy, a dead-field audit — as
  first-class findings rather than incidental discoveries during a later build.
  Plan-time journaling proved worth keeping.
- **Later**, the dominant mode became **conversation-as-design-tool, then
  skill-chain to execute**: entire subsystems emerged from a handful of "what if
  X worked like Y?" turns, were locked into the plan and spec, and only then built.
  The skill chain (`/plan` → `/spec` → `/build` → `/check`, re-entering `/spec`
  to correct a falsified claim) held its seams — routing even mid-build spec
  corrections through the sole mutator kept the encoding and numbering discipline
  intact and left an honest trail.

Two organizational lessons round it out. **Scope is escalated, not half-built**:
when a task's real size exceeded its estimate, it was split along a real seam
(traits became T.28 a/b/c/d, each shipping green) rather than left perpetually
"80% done." And **concurrency demands blast-radius discipline**: a two-agent
parallel experiment succeeded only because the *shared test baseline* — not just
file ownership — was made explicit, and a careless `git add -A` in a shared
worktree once swept another stream's spec edits into the wrong commit (producing a
duplicate invariant), yielding the standing rule to **stage your own paths
explicitly, never `-A`, in a shared tree.**

The through-line: the process exists to compensate for the agent's specific failure
modes — confident-but-unverified prose, trust in green tests, trust in its own
measurements — by making verification, self-review, and human design authority into
explicit, load-bearing steps rather than assumed ones.
