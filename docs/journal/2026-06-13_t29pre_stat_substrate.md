# 2026-06-13 — T.29-pre: combat stat substrate (weather→modifiers + attack_speed float)

## What shipped

A prerequisite substep wedged in **before** T.29a, born entirely from a design
conversation (not the original T.29 item plan). Two halves, one commit
(`ad06647`), one determinism re-baseline:

1. **Weather → modifiers (V.42).** `loadout._apply_weather_to_piece` no longer
   folds Weather Favor into `Piece.base_stats`. It now emits
   `source="weather:<state>"` `Modifier`s (`*_mult≠1 → ("<stat>","mul",mult)`,
   `attack_range_delta → ("attack_range","add",delta)`) through `apply_bundle`,
   so weather composes through `compute_stat` `(base+Σadds)×Πmuls` like every
   other source — uniformly attributable and it scales item/augment adds.
2. **`attack_speed` float, `milli_AS` deleted (V.34 amended, B.18).** One float
   carries both cadence (`int(AS)`) and sub-integer order (`round(AS×1000)`),
   so an AS mul moves both together — killing the desync where ability AS muls
   forgot to ride the separate `milli_AS` field.
3. Supporting: `_STAT_FLOORS` clamp in `compute_stat` (`attack_range ≥ 1`, V.43);
   resources reconcile from `stat()` and are never `Modifier` targets (V.43);
   `stat_breakdown(piece)` telescoping helper for the prep-view (V.45); anti-
   runaway snapshot invariant (V.44); standardized `source:` prefix vocab.

1181 tests pass; `sim_run` deterministic; sim layer imports clean.

## Why this exists at all (the "why" the diff hides)

The trigger was T.34 ability tooltips (just merged from `main`). T.34 renders any
`source` with `.stat()`, so combat tooltips already reflect item/passive
modifiers for free. The gap: weather was **baked into `base_stats`**, so it
couldn't be attributed like a modifier in a prep-view "total + hold-for-breakdown"
UI. Chasing "show weather in the breakdown" unspooled into:

- The honest axis is **flow-stat vs resource**, not weather-vs-modifier. Flow
  stats already flow through modifiers; resources (hp/mana) are *never*
  modifier'd — every max-HP change direct-sets + reconciles (traits already did
  exactly this, with a comment literally saying "matches weather behaviour").
  So weather joining the modifier path was natural, and the max_hp "pitfall" I
  raised early was a non-issue.
- Weather was the **inconsistent** one: it pre-rounded and manually rode
  `milli_AS`; abilities truncate-at-read and don't. Modifier-izing weather makes
  it behave like everything else.
- That led to "why does `milli_AS` exist at all?" → float `attack_speed`.

## Process notes (AI collaboration)

**The plan's central claim was wrong, and the build caught it.** The plan (and the
spec rows I wrote from it) asserted Commit 2 (`attack_speed`→float) would be
**"~byte-identical"** because the migration `AS = milli_AS/1000` is "exact." Two
errors:
- I reasoned from a cherry-picked example (`int(142.43)=142 == int(round(142.43))`)
  that happened to have fractional part < 0.5. For frac ≥ 0.5 the old pipeline
  **rounded** `attack_speed` to int for storage, while the float model
  **truncates** at read — so cadence shifts by ≤1. The old `attack_speed` (int,
  rounded) and `milli_AS` were *independent* fields that could be mutually
  inconsistent; one float cannot reproduce an inconsistent pair. Byte-identity
  was impossible, not merely unlikely.
- I verified empirically before believing the plan: captured 6 pre-refactor
  weather baselines, diffed after. **Even clear weather shifted tick timing**
  (±2–12 ticks), damage/structure unchanged. That isolated it cleanly: clear
  divergence = the AS-float cadence (Commit 2); weather divergence stacks on top
  (Commit 1). Determinism held (re-run byte-identical to itself).
- Correction routed back through `/spec`: amended B.18 + the T.29-pre row to say
  **"deterministic re-baseline, NOT byte-identical."** This is the SDD loop
  working as intended — the build is allowed to falsify the plan, and the spec is
  corrected rather than the finding buried.

**`milli_AS` was more entangled than the plan's grep suggested.** The plan listed
models/content/scaling/engine. The build found it was also an **active modifier
target in traits** (`_packs.py`, `mechanics.py` enrage + time_ramp riders) and in
a death-spawn stat whitelist. Lesson reinforced: a "drop field X everywhere"
refactor must grep for X as a *string in Modifier() calls*, not just field decls.

**`stat_breakdown` decomposition bug, caught by my own test.** First implementation
used **marginal** deltas (full − without_this_source). A `test_deltas_sum_to_total`
assertion failed: 146 ≠ 143 — marginals double-count the add×mul interaction term.
Switched to a **telescoping** (ordered-cumulative) decomposition so rows sum
exactly to the effective total — the property a breakdown UI actually needs. The
test I wrote to be thorough is what surfaced it; worth writing the "obvious"
sum-invariant test even when the helper "looks right."

**User course-corrections mid-build, both good:** (1) "no old saves, don't migrate"
→ deleted the `from_dict` migration branch I'd added; (2) "prefer clean code, nobody
should accidentally use legacy" → reinforced deleting `milli_AS` outright rather
than leaving a deprecated alias. The cleaner choice also dodged a trap: keeping a
`milli_AS` shim would have masked the determinism shift behind a fake-compatible
field.

**CLAUDE.md vs reality:** the `compute_stat` fast-path comment said "weather is
folded into base_stats; only passives/abilities add modifiers." That's now false —
weather adds modifiers too. Updated the comment in the same change (a stale
performance-rationale comment is a small drift but exactly the kind `/check` is
meant to catch).

## Prompting-strategy reflection

This task is the strongest case so far in this project for **conversation-as-design-
tool, then skill-chain to execute**. The whole substep didn't exist in any plan; it
emerged from ~6 turns of "what if weather worked like an augment?" The shape that
worked:

- **Drive the model to argue against the user's stated preference when the code
  says so.** When asked to do option (b) (weather as real modifiers, full-fidelity),
  investigating the code surfaced that (b) was a determinism-anchor refactor — and I
  said so plainly, then the *user's next question* ("doesn't max_hp apply to passives
  too?") flipped it back, correctly. The productive pattern was refusing to just
  ratify either side until the code adjudicated. The `traits/__init__.py` re-sync
  comment ("matches weather behaviour") was the single fact that settled it.
- **Measure before believing your own plan.** The byte-identical claim survived
  planning, spec, and into build because it *sounded* rigorous ("migration is
  exact"). Only the baseline diff killed it. Capturing a pre-change baseline as the
  very first build step — before touching code — is now my default for any
  determinism-sensitive change; it converts "I think this is a no-op" into a number.
- **Skill chain held its seams.** `/plan` (doc only) → `/spec` (SPEC only) → `/build`
  (code + status flip) → `/spec` again (correct the falsified claim) → `/check`. The
  re-entry into `/spec` mid-build to fix B.18 is the part I'd have skipped earlier in
  the project (just edit SPEC inline); routing it through the mutator kept the
  caveman encoding + numbering discipline intact and left an honest trail.
- **Tell on yourself in the commit + journal.** The diff shows clean float code; it
  does *not* show that the plan promised byte-identity and was wrong. That signal
  only survives if written down. Same for the marginal→telescoping breakdown fix.

Next: T.29a (item engine) can now author `item:`-tagged modifiers against the
settled `(base+Σadds)×Πmuls` compose contract; `roster_source`/`projected_source`
+ the hold-modifier UI consume `stat_breakdown` later (T.23).
