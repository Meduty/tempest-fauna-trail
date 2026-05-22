# Journal - 2026-05-22 (T5 Plan Update + T18 Power Scaling)

## Scope and User Intent

Continuation session. The prior conversation had designed the `ChampionDef` +
`stat_overrides` authoring pattern but exhausted its context budget before
writing anything. This session resumed from that end state:

- T5 plan had two stale items: a line attributing `ability_int_coeff` as
  "derived at combat time" (the field was gone entirely), and a `_make_champion`
  function in §5.2 that predated the stat-override design.
- T18 plan §4 described the roster as "derived, not hand-tuned" — inaccurate
  now that per-unit `stat_overrides` are authored deltas, not pure computation.
- T18 implementation had not been started.

Session goals: apply the plan updates, implement T18 (`src/game/scaling.py`),
then review the result.

## Chronological Protocol

1. **Context recovery.** Read the tail of the T5 plan (§4.4 compose_stats
   section, §5.2 generation pattern, §6-8) and the full T18 plan to locate the
   exact stale text and understand what the implementation needed to produce.

2. **T5 plan — §4.4.** Removed the stale `ability_int_coeff` line. Replaced it
   with a note clarifying that `compose_stats()` returns the **archetype
   baseline** — the budget-correct starting point — and that per-unit
   `stat_overrides` are applied on top in `_build_champion`. The axis system
   guarantees equal power budgets across same-archetype units; overrides
   redistribute within it.

3. **T5 plan — §5.2.** Replaced the `_make_champion` keyword-argument function
   with the two-piece `ChampionDef` + `_build_champion` pattern:
   - `ChampionDef`: plain dataclass recording axes, identity fields, and
     `stat_overrides: dict[str, int]`. The four axis fields are separate strings
     (`primary_stat`, `range_`, `durability`, `playstyle`) rather than a single
     tuple — clearer to read at the call site.
   - `_build_champion`: calls `compose_stats()` for the baseline, applies
     overrides with a dict comprehension, then constructs `Champion` with
     `max(..., 0)` / `max(1, ...)` guards on scalable stats.
   - `_assert_budget`: module-level guard; aborts import if any champion's
     override sum exceeds ±15% of the baseline's total scalable-stat budget.
     Enforces budget-neutral authoring as a convention without baking it into
     the model.

4. **T5 plan — §7.2 and §8.** Updated the enemy generation section to use the
   same `EnemyDef` + `_build_enemy` pattern. `EnemyDef` replaces `traits` with
   a `tags` field (`frozenset[str]`) used only by T24/augment matchers.
   Updated the module structure tree to show `ChampionDef`, `EnemyDef`,
   `_assert_budget`, `_build_champion`, `_build_enemy` in place of the old
   `_make_champion` / `_make_enemy` entries. Removed the T18 reference from the
   `compose_stats` doc note (T22 is the remaining consumer).

5. **T18 plan — §4.** Rewrote the "derived, not hand-tuned" paragraph to
   describe the actual two-step model: `compose_stats(archetype, tier)` produces
   the baseline; each unit then carries `stat_overrides` (additive deltas)
   authored in T5. Added a note that level-up re-applies `stat_multiplier` to
   the *pre-override* baseline — overrides do not compound with level-ups.

6. **T18 implementation.** Created `src/game/scaling.py`:
   - `TIER_STEP = 1.5**0.5`, `LEVEL_STEP = 1.5` — named constants for the
     per-step ratios on the raw power scalar P.
   - `SCALABLE_STATS` tuple: the five stats scaled by `stat_multiplier`. Flat
     stats not present (attack_speed, mana_regen, move_speed, attack_range,
     threat, ability_cost).
   - `power(tier, level)` — exponent `(T-1)/2 + (L-1)`, returns `1.5**E`.
   - `stat_multiplier(tier, level)` — `sqrt(power(T, L))`.
   - `scale_stat(base, tier, level)` — `round(base * stat_multiplier(T, L))`.

7. **T18 tests.** Created `tests/game/test_scaling.py` (24 tests in four
   classes): `TestPower`, `TestStatMultiplier`, `TestScaleStat`,
   `TestScalableStats`. Covered all §7 invariants: T1L1 baseline, level/tier
   step ratios, the "two tiers == one level" identity across all valid (T, L)
   pairs, T10L3 ≈14× spread, sqrt-coupling, integer output, rounding contract,
   monotonicity (weak ≤ due to rounding plateaus at small bases), and flat-stat
   exclusion. Full suite: 224 passed.

8. **Review.** User asked: "review the implementation of T18." Three real
   issues found:
   - `TIER_STEP` comment read `"added per tier increment"` — `TIER_STEP` is a
     *multiplier* (ratio), not an additive delta.
   - No input bounds validation: `power(0, 1)` silently returned ≈0.816,
     contradicting the `≥ 1.0` guarantee in the docstring. No `ValueError` was
     raised.
   - Two `test_deterministic` tests (one in `TestPower`, one in `TestScaleStat`)
     asserted `f(x) == f(x)` — trivially true for any pure function, zero
     signal. Also flagged `test_specific_identity_t3_l1_eq_t1_l2` as fully
     covered by `test_two_tiers_equal_one_level`.

9. **Fixes.** User: "fix all three." Applied with a single
   `multi_replace_string_in_file` call:
   - Comment: `"added per tier increment"` → `"per-tier power multiplier (ratio)"`.
   - Bounds: added `ValueError` guards inside `power()` for `tier` outside
     `[1, 10]` and `level` outside `[1, 3]`. `stat_multiplier` and `scale_stat`
     inherit validation by delegating to `power()` — no duplication.
   - Tests: removed both `test_deterministic` cases and the redundant identity
     test. Added `test_out_of_range_tier_raises` and
     `test_out_of_range_level_raises` to cover the new guards.
   - 23 tests, all passing.

## Repo Changes Summary

- Modified: `docs/design/tasks/t5_content_plan.md`
  — §4.4 stale line removed, archetype-baseline note added
  — §5.2 `_make_champion` → `ChampionDef` + `_build_champion` + `_assert_budget`
  — §7.2 `_make_enemy` → `EnemyDef` + `_build_enemy`
  — §8 module structure tree updated
- Modified: `docs/design/tasks/t18_power_scaling_plan.md`
  — §4 "derived, not hand-tuned" replaced with baseline + overrides model
- Added: `src/game/scaling.py`
- Added: `tests/game/test_scaling.py`

## Dialog: What Worked

**Short commands were unambiguous.** "Fix all three" after a numbered review
list required zero clarification — the reference was exact and execution was a
single tool call. This is the cleanest interaction pattern of the session.

**The plan-update phase was front-loaded correctly.** Both plans were read in
full before any code was written, and the code was structurally simple precisely
because the plan was clear. Implementation was about 15 minutes of wall time
and produced a first-pass module with no architectural issues.

**The review pass caught real problems, not invented ones.** All three flagged
issues were genuine: a wrong word in a comment, a missing contract enforcement,
and dead test code. None were stylistic preferences or hypothetical edge cases.
The review did not overreach into "consider adding X" or restructuring advice.

**Bounds validation was placed at the right level.** Adding the guard only in
`power()` and letting `stat_multiplier`/`scale_stat` inherit it by delegation
followed DRY without introducing indirection. A guard in all three would have
been noisy; a guard in none would have left silent wrong-result bugs.

## Dialog: What Didn't Work

**The initial implementation introduced the mistakes it then found in review.**
The misleading `TIER_STEP` comment and the absent bounds validation were both
written by the agent in step 6 and only caught in step 8 when the user asked
for a review. The agent did not self-review before reporting "24 tests, all
passing" — passing tests are not the same as a correct implementation. A
mandatory self-review pass before declaring a task complete would have caught
both before the user had to ask.

**Two no-value tests were written and had to be removed.** `test_deterministic`
in both `TestPower` and `TestScaleStat` asserted that a pure function returns
the same result when called twice. This adds test count without adding
confidence. It suggests the test suite was padded to fill out coverage classes
rather than derived from actual invariants.

**The `test_specific_identity_t3_l1_eq_t1_l2` test was redundant from
inception.** `test_two_tiers_equal_one_level` already iterates all valid (T, L)
pairs and subsumes it. The separate test existed only because it was
quick to write. Recognising that "X is a special case of Y which I already
test" before writing X is a discipline worth applying more consistently.

## Key Technical Outcomes

- `power(T, L) = 1.5 ** ((T−1)/2 + (L−1))` — two tier steps equal one level
  step exactly; exponent is rational arithmetic, no floating-point surprise.
- `stat_multiplier = sqrt(P)` — preserves the Lanchester `HP×DPS ∝ P` budget.
  T1L1 = ×1.0; T10L3 = ×3.73; spread ≈ 14× in combat value.
- Flat stats (attack_speed, mana_regen, move_speed, attack_range, threat,
  ability_cost) are explicitly excluded from `SCALABLE_STATS`. Scaling them
  would double-count DPS growth and create tempo/identity problems at high tier.
- `scale_stat` monotonicity is weak (≤) by design: at very small base values
  rounding can produce identical outputs for adjacent tiers. The test correctly
  uses `<=`; this was noted in the review but not flagged as a bug.
- Bounds guards in `power()` propagate to all callers — adding validation to
  only one function and delegating throughout is the preferred pattern for
  this codebase.

## Continuation State

- T18: complete. `src/game/scaling.py` locked; `SCALABLE_STATS` is the
  canonical list for T5/T22 consumers.
- T5 plan: updated and consistent with the `ChampionDef` + `stat_overrides`
  design. Implementation not started.
- Next natural step: T5 (`src/game/content.py`) — axis weights, `compose_stats`,
  `ChampionDef`/`EnemyDef` declarations, the full 60-champion + 60-enemy
  roster.
