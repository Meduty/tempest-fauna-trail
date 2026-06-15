# 2026-06-15 — T.29c: mana primitive + the invisible-caster bug

## What shipped

T.29c — the combat mana primitive (resolved plan §3.1a), built on top of the
already-shipped T.29a item engine:

- **Per-ability mana statline** (`ActiveSlot.mana_cost`/`max_mana`/`start_mana`/
  `priority`). Cost is authored **on the ability def** via a new `ABILITY_MANA`
  registry (Tension 1 = Option A); the per-piece `ability_cost` FLAT stat is
  **removed** entirely (model field, `_BASE_STATS`, `FLAT_STATS`, serialization,
  6 boss values + 2 summon sentinels migrated). `max_mana` defaults to `2×cost`.
- **Weighted-rank charge cycle** (Tension 3): one slot charged the full
  `mana_regen` per tick, cycle length `sum(priority)`, skip-if-full → throughput
  is slot-count-invariant. Deterministic cadence (`Piece.mana_charge_cursor`).
- **≤1 cast per action window + unified `priority`** (Tension 4): highest-priority
  ready slot casts, tie → lowest index; `-= mana_cost` so overflow banks.
- **Item retrofit** (B.21): `springtear`/`deepwell`/`everbloom_staff` no longer
  cut `mana_cost` — they grant `mana_regen` (Modifier) + `start_mana`.
- **Recorder fix** (B.22, V.50): `_on_cast` was a `pass` stub → registered casts
  emitted no event. Implemented it; casts now show in log/sims/turn-count.

→ SPEC V.48/V.49/V.50, B.21/B.22, V.34/V.35 amended, T.29c ✅. Full suite
green (1143 passed); +9 mana unit tests.

## Why

The §3.1a model was reworked *after* T.29a shipped (Copilot PR #41), so the item
engine landed on a mana model that no longer existed. The rework's intent: cost
is the **ability** knob, `mana_regen` the **piece** knob; multi-active pieces are
primary+secondary spells (one budget, weighted), not N parallel bars. Overflow
banking + `max_mana=2×` give items headroom without a cost-reduction stat (which
stacks to negative-cost degeneracy).

Determinism: chose overflow-carry (`-= mana_cost`) over zero-on-cast — a real
re-baseline, but reproducibility tests + the full suite stayed green (baseline
`mana_regen=100` divides `cost=300_000` exactly; divergence only at scaled-MR
tiers, which no golden snapshot pins).

## Process notes (AI collaboration)

- **The headline miss was a sim that lied.** Roster sims showed **0 casts** even
  in a 12 061-tick fight. First instinct: "pre-existing, out of scope." The user
  pushed back hard — "casters are a garbage class, *question your fighting sim*."
  Instrumenting `cast_ability` directly showed casts **were firing** (Coral cast
  5×); the recorder's `_on_cast` was a no-op, so every registered cast was
  invisible. **Lesson: a metric reading zero is a claim about the metric, not
  just the system.** I had grepped the *rendered log* for "casts" and trusted the
  count instead of instrumenting the actual code path. The user's "question your
  sim" was the correct epistemics; my stash-compare ("0 == 0, no regression") was
  technically true but answered the wrong question.
- **Scope discipline came from the user, twice.** I twice proposed lower-blast
  shortcuts (keep `ability_cost` as a fallback seed; amend the spec to Option B).
  Both times the user said "don't deviate from plan, if blast is big, blast is
  big." The full Option-A removal touched ~12 source files + 10 test files and
  was the right call — the hybrid would have left a dead stat as a foot-gun.
- **Confirm-before-behavior-change paid off.** Before editing combat, I stopped
  to confirm the overflow-carry/re-baseline decision via `AskUserQuestion`. The
  user picked carry+re-baseline explicitly, so the snapshot churn was sanctioned,
  not a surprise.
- **CLAUDE.md vs reality drift caught mid-task:** the plan doc said §3.1a folds
  into T.29a, but SPEC marked T.29a ✅ Done (Copilot had built it). Reconciled by
  splitting the mana primitive into its own row (T.29c) rather than retconning a
  shipped task. The plan doc's "T.29c"(multi-slot) was renamed to T.29d.
- **Copilot artifact quality:** PR #41 built a clean item engine but against a
  stale mana model (the rework post-dated it by one plan commit). Not "imbecile"
  — a synchronization gap: an async agent built to a spec snapshot that moved.
  The guard (V.48 + `test_items` assertions) now prevents the regression class.

### Prompting-strategy reflection

What worked: instrumenting the real code path (`cast_ability` wrapper) the moment
a metric looked wrong, instead of arguing from logs. What I'll do earlier next
time: when a sim shows a suspicious extreme (0 / all), distrust the *measurement*
first — wrap the function, don't grep the output. The user's terse corrections
("question your sim", "blast is big") were higher-signal than long deliberation;
I over-deliberated scope twice before being told to just do the planned thing.
Default toward the planned blast radius unless the user opened the door to cut it.
