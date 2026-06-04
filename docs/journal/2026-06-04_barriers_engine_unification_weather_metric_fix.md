# 2026-06-04 — Barriers, percentage DOT decay, engine unification finalized, weather-metric NaN fix

Backfill entry. Four things landed across commits `8d71a0d → 89e7287` (Jun 3)
that never got a journal — written now while the "why" is still recoverable.
Companion to [2026-06-03_dot_cadence_and_focus_fire.md](2026-06-03_dot_cadence_and_focus_fire.md),
which covered the DOT *cadence* half; this covers the rest.

## What changed

1. **Barrier system** (V.28) — a temporary damage-absorb pool distinct from HP and
   distinct from "shield". `Piece.barriers: list[BarrierSegment]`, soaked **before**
   HP inside `deal_damage` via `absorb_with_barrier` (absorbs post-mitigation
   `final`; remainder hits HP). Multi-segment, **FIFO**, each segment with optional
   tick expiry (`expires_at_tick=None` → lasts until consumed), pruned in
   `expire_modifiers` next to TIMED modifiers. Granted only through
   `ctx.grant_barrier(target, amount, duration_ticks)`. `on_damage_*` events still
   fire the **full pre-barrier** amount so DPS accounting is unchanged.
   (`piece.py`, `combat/context.py`, `combat/loop_new.py`; commit `6a618c3`.)
2. **Glade Heron reworked** — `Toxic Volley` → `Quickening` (attack-speed haste),
   `Venom Tip` → a poison **burst scaled by current stacks**. The first content
   consumer that needed barriers + the new poison model. (`abilities/champions.py`,
   `abilities/enemies.py`.)
3. **Percentage poison-stack decay** (the second half of V.25) — decaying statuses
   now shed `max(1, trunc(stacks · decay_fraction))` per DOT tick (`poison`
   `decay_fraction = 0.2`) instead of a flat `1`. (`status.py`.)
4. **`combat/loop.py` deleted** (V.29) — the pre-T.26 partial loop, dead production
   code kept alive only by one test import, is gone. `loop_new.py` is now the **sole**
   tick engine; tests import loop internals from `combat.loop_new`. (275 lines
   removed in `6a618c3`.)
5. **Sim weather-metric NaN fix** (B.12 / V.30) — `weather_metrics` zero-filled
   `own_weather_wr` / `counter_weather_wr` for weathers a piece never played, and
   downstream aggregates averaged those fabricated 0s. Absent weather is now `NaN`,
   CSV writes an empty cell, every cross-weather aggregate skips NA. (`ratings.py`,
   `mega.py`, `report.py`; commit `e4fd0b1`, + report pipeline in `89e7287`.)

## Why (the part SPEC compresses out)

### Barrier ≠ shield — a naming trap we walked into on purpose

The roster already used the word **"shield"** in ids (`enemy_hierarch.shield`) for
what is really an **armor/resistance buff** — a mitigation multiplier, not an HP
pool. When Glade Heron wanted a real absorb pool, overloading "shield" would have
made `enemy_hierarch.shield` and a new `*.shield` mean two different mechanics. So
the absorb pool got a distinct name (**barrier**) and V.28 nails the distinction
down in writing precisely because the codebase had already primed the confusion.
The invariant exists to stop a future agent (or us) from "unifying" the two.

The subtle design point: barriers absorb **post-mitigation** damage and `on_damage_*`
still reports the **full pre-barrier** number. A barrier therefore changes *survival*
without distorting *DPS accounting* — the sim's damage-dealt stats stay honest, which
matters because the balance pipeline (mega sweeps) reads those numbers.

### Percentage decay — the anti-runaway equilibrium

Flat `-1`/tick decay in a continuous tick auto-battler (V.29) is **linear runaway**:
continuous auto-application + constant decrement has no natural ceiling, so poison
either does nothing (decay outruns apply) or grows unbounded (apply outruns decay),
with the knife-edge depending on attack speed. Percentage decay gives a **soft
equilibrium** `stacks_eq ≈ apply_rate / decay_fraction` — it rises with AS / level /
INT / number of poison sources but never runs away, and crucially needs **no hard
stack cap**. That last point is deliberate and recorded as a standing balance
principle: see memory *no-hard-caps-prefer-emergent-plateaus*. Hard caps wall off a
build instead of letting it come online; PoE/StS DOT philosophy over TFT's
anti-stack refresh.

### Deleting loop.py — one engine, by force

T.26 unified combat onto `loop_new.py`, but `loop.py` lingered as "kept in sync"
because a single test still imported it. "Kept in sync" is a lie that decays: the
two loops *will* drift, and a per-tick mechanic (barrier prune!) added to one and
not the other is a silent correctness fork. The barrier work was the forcing
function — rather than add `absorb_with_barrier` to two loops, we deleted the dead
one and repointed the test. V.29 now forbids reintroducing a parallel engine.

### The weather-metric bug — a measurement lie, not a game bug

This one never touched gameplay; it corrupted the **analysis** that drives balance
decisions. A piece that played zero games in (say) Snow had its Snow win-rate
recorded as `0.0` — indistinguishable from "played Snow, lost every game". The
mega7 report then averaged those phantom zeros into the own-vs-counter weather
swing and printed `+0.18` (a headline "weather matters a lot" number). True value
with NA-skipping: `≈ +0.01`. We almost balanced the *game* against a bug in the
*ruler*. V.30 (extending V.16) makes "absent ≠ 0" an invariant of the sim layer.

## Decisions

- **Barrier granted only via `ctx.grant_barrier`** (no direct `piece.barriers`
  mutation from content) — keeps the absorb pool inside the same mutator-API
  discipline as statuses/modifiers, so determinism and expiry stay centralized.
- **FIFO segment consumption** — oldest barrier soaks first; matches intuition
  ("the shield you cast first breaks first") and makes per-segment expiry
  well-defined.
- **Decay stays `max(1, …)`** — percentage decay never rounds to 0, so a large
  stack still bleeds and can't get *stuck* permanently high under low decay.
- **NaN, not a sentinel** — `weather_metrics` returns real `NaN`, CSV writes an
  empty cell, R reads it back as `NA`. No `-1`/`999` magic number that a later
  `mean()` could swallow. The representation enforces the invariant.

## Process notes (AI collaboration)

_New mandatory section — see [docs/templates/journal_entry.md](../templates/journal_entry.md).
Captures the vibe-coding reality: where agent + spec + code disagreed, and why._

- **Drift caught: "kept in sync" was already false in spirit.** The prior journal
  (2026-06-03) explicitly noted `loop.py` was "kept in sync — still imported by
  test_abilities.py". One day later it was deleted. Lesson reaffirmed: a duplicated
  engine annotated "keep in sync" is tech debt with a fuse, not a stable state. If
  you find yourself writing "keep X and Y in sync" in a comment, that's the signal
  to delete one — not to document the duplication.
- **Naming collision the agent had to be steered around.** An agent extending
  combat will reach for "shield" for an absorb pool because that's the genre-default
  word. The roster's prior, *different* use of "shield" (armor buff) is a landmine.
  This is why V.28 spends a full sentence on the vocabulary, not just the mechanic —
  invariants here double as agent guardrails against plausible-but-wrong wording.
- **A bug in the measurement layer outranks bugs in the game.** The mega7 `+0.18`
  number was about to feed a balance pass. Backprop discipline (B.12 → V.30) is the
  thing that caught it: the question "what invariant would have prevented this?"
  forced us to look at *how* the metric was computed, not just patch the number.
- **Backfill cost is real.** Four journal-worthy changes shipped without entries and
  this reconstruction leaned on commit messages + SPEC backprop to recover intent.
  Commit messages were good enough to do it — but only because B.11/B.12 and
  V.25–V.30 had already captured the "why". The journal is the *narrative* layer; the
  spec is the *contract* layer. Skipping the narrative is recoverable; skipping the
  spec backprop would not have been.

### Prompting-strategy reflection

The high-leverage move this stretch was **letting the spec's `/backprop` protocol
drive**: rather than "fix the weather number", the effective prompt shape was "this
number looks wrong — trace the cause and decide if an invariant should catch
recurrence". That reliably converts a one-off patch into a durable guard (V.30). The
weaker move was **batching too much per commit without journaling** — `6a618c3`
alone carried a Heron rework, the barrier system, percentage decay, *and* a 275-line
engine deletion. Each deserved its own paragraph at the time; bundling them is what
created this backfill. Going forward: one journal section per conceptual change, even
when they ride the same commit.

## Files

`piece.py`, `combat/context.py`, `combat/loop_new.py`, `combat/loop.py` (deleted),
`status.py`, `abilities/champions.py`, `abilities/enemies.py`,
`tools/simulation/ratings.py`, `tools/simulation/mega.py`, `tools/simulation/report.py`.
Docs/spec: SPEC V.28, V.29, V.30 + B.12; `reviews/mega7_analysis_report.md` and the
`reviews/mega_sim/` pipeline.

## Follow-ups

- Finalize the provisional DOT magnitudes (burn 40 / poison 18) against a clean
  mega8 sweep now that the weather metric is trustworthy.
- Audit other `*.shield` ids for the buff-vs-barrier ambiguity and rename any that
  actually want a barrier.
- Consider a CI assertion that no module under `combat/` other than `loop_new.py`
  defines a tick loop (mechanize V.29).
