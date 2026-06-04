# 2026-06-04 — Weather-impact density sim + side-A engine bias found

New dev sim `tools/simulation/weather_impact.py` measures how hard the two weather
systems swing 8v8 outcomes, by *affinity density* rather than per-piece power.
Probing it surfaced a latent combat-engine bug: a deterministic side-A advantage
on attack-speed ties. Touches T.25 (sim layer), relates to T.2 (weather), T.3/T.20
(engine ordering). No SPEC change applied yet — the engine bug is a pending §B/§V.

## What changed

1. New `tools/simulation/weather_impact.py` — three probes, all on equal-budget
   teams (both sides draw the *same tier multiset*, so only affinity-per-slot
   varies). `CLEAR` affinity is the inert isolator (identity in Weather Favor,
   1.0 in Affinity Clash):
   - **System A** (Weather Favor): enemy all-clear, sweep k own-weather pieces;
     control run at CLEAR weather subtracted → pure Favor.
   - **System B** (Affinity Clash): CLEAR weather, mono-X vs mono-Y matrix + a
     density curve (j predator pieces vs mono-prey).
   - **System AB**: node weather X, mono/own-density vs mono-prey — both compound.
2. Primary metric is the continuous **HP margin** `(hp_a-hp_b)/(hp_a+hp_b)`, not
   win/loss — see Why.
3. `--both-sides` (default on): each matchup also played swapped and folded
   (margin negated, outcome flipped) to cancel an engine side bias.
4. Parallelised via the existing `tournament.run_tournament` pool.
5. Tests `tests/tools/simulation/test_weather_impact.py` (13) — index coverage,
   clear-inertness in both systems, fold math, metrics.

## Why (the part SPEC compresses out)

- **Margin over win-rate.** An 8-piece team must span 8 distinct tiers (roster has
  one champ per (affinity,tier)), so the top piece is ~5× the bottom (2^((T-1)/3)).
  Binary win/loss is then dominated by the strongest piece's duel and is high
  variance — it measures "did weather tip the top duel?", not "how much does
  weather matter?". The normalised surviving-HP margin is continuous: every piece's
  buff feeds it, so the systematic weather effect shows as a low-variance mean shift.
  The user steered this directly ("most win carried by higher-tier pieces … drown
  it by high variance of individual pieces").
- **Density is the real question.** "How many champs drawn for the own weather"
  *is* the independent variable. A sweeps it natively; B/AB got explicit density
  curves added after the user asked whether intensity-over-density was covered.
- **Clear-roster confound.** B-density's j=0 anchor is 74%, not 50%: at j=0 it is
  clear-roster vs ring-roster (same tiers, different identities) and clear champs
  are statlined stronger on average. The delta-vs-j=0 column isolates the clash
  contribution from this roster bias.

## Findings (8v8, side-bias cancelled)

- Weather Favor (A) full-team swing: **+0.98 margin / +48pp win** (0→8 own-weather).
- Affinity Clash (B) at saturation: primary-predator **99%**, secondary **82%**,
  secondary-prey **17%**, primary-prey **4%**. Clash density delta +0.51 / +25pp.
- Overlap (AB): Clash dominates Favor — rain-under-rain still loses **0%** to snow
  (its predator); Favor ≈ cancels only a *secondary*-prey clash gap (rain vs
  thunder ≈ 57%). Compounded, **~5/8 on-affinity pieces saturate to 100% win**.

## Decisions

- Kept tier-mirror equal-budget construction (not the encounter generator) — its
  affinity logic is too opaque for clean isolation; the user OK'd either.
- `--both-sides` defaults ON: correctness (side independence) over the 2× cost.
- `--tier-lo/--tier-hi` added so the signal can be re-confirmed on a near-equal
  power band, proving it's the weather system not tier skew.

## Process notes (AI collaboration)

- **Agent error / wrong turn:** first pass measured win-rate only and used a tuple
  as a `random.Random` seed (TypeError on 3.14). The win-rate-only design was the
  bigger miss — the user caught that tier-dominance would mask the weather signal
  before it wasted a big run. Fixed by switching the primary metric to HP margin.
- **Drift / bug caught:** the sim's mirror cells reading ≠50% exposed a real engine
  bug — `legacy.py:469` sets `speed_tiebreaker = index` over a team-then-enemy
  ordering, and `_event_sort_key` (loop_new.py:378) breaks equal attack-speed by
  that index, so the whole team acts first on ties. Identical mirror = deterministic
  side-A win. Design intent is side-independent (first mover by AS/MS only). Affects
  every prior combat result and sim report. Saved to agent memory; engine fix
  deferred pending a determinism-changing decision.
- **Guardrail added:** tests assert clear-affinity inertness in *both* weather
  systems — the isolation premise the whole sim rests on, so a future weather-table
  edit that breaks it fails loudly.
- **Conflict:** none between docs and code here; the weather_effects module matched
  its design doc. The conflict was code-vs-*design-intent* (the tiebreaker).

### Prompting-strategy reflection

High-leverage this session was the user injecting methodology mid-build rather than
upfront: "watch for tier-piece dominance", "are you sweeping density", "why is there
a side-A advantage". Each arrived as a small course-correction that reshaped the
deliverable more than any upfront spec could have — because the flaws only became
visible once early numbers existed. Lesson: for measurement/analysis tasks, ship a
*small fast run first* and read it together before scaling samples; the cheap run is
the prompt. Low-leverage would have been launching the full 8v8 sweep before the
metric was right (a 590s timeout already burned once). The side-bias question is the
template case for "don't just fix it" — tracing *why* the mirror wasn't 50% turned a
sim cosmetic into a real engine bug + a memory + a deferred §B, which is exactly the
SDD backprop reflex the repo wants.

## Files

- `tools/simulation/weather_impact.py` (new)
- `tests/tools/simulation/test_weather_impact.py` (new)
- agent memory `combat-side-a-tiebreaker-bias.md` (new)
