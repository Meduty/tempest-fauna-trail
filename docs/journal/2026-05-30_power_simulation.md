# 2026-05-30 — T.25 power simulation shipped

## Why team-sim over pure 1v1

The original plan ([docs/design/tasks/t25_power_simulation_plan.md](../design/tasks/t25_power_simulation_plan.md))
framed everything as 1v1 sweeps. That measures duelist strength but bakes
in two biases that distort balance reads on a team-based game:

1. **Tank/healer pieces look weak in 1v1.** A piece designed to soak damage
   for a 2-piece backline trades poorly alone — its raw win rate
   undervalues it relative to its real role.
2. **Strong duelists look universal.** Pieces optimised for sustained 1v1
   trades over-perform when the simulation never asks "how does it cover a
   teammate?".

The amendment expands to full team-vs-team sims. Same engine, same
deterministic resolution; just more configurations.

## Attribution rule chosen — binary on winning team

Decision locked at session start. Considered alternatives and why this one
won:

| Rule | Why rejected |
|---|---|
| Surviving HP fraction | Rewards tanks; over-credits stat-stick pieces that survive without contributing |
| Damage share | Under-credits supports/tanks; biases toward DPS roles |
| Composite | Weights are arbitrary — no principled way to choose 0.4/0.4/0.2 vs other splits |

Binary attribution (every piece on winning team scores 1 vs every piece
on losing team; draws 0.5) trades signal-per-battle for clarity:

- No hidden weighting assumptions.
- Maps cleanly into the deterministic power-threshold expected WR model.
- Higher sample count to converge, but engine determinism means the marginal
  cost of more battles is just CPU time — there's no statistical reason
  to economise on samples.

## Sampling strategy chosen — implementer judgment within locked scope

User-locked scope: full 1v1 + full N=2 (opt-in, ~25M pairs) + sampled
N=3..max. Implementation:

- **`1v1`** — `itertools.combinations(pieces, 2)` over the full
  120-piece roster (60 champions + 60 enemies). C(120,2) = 7140 battles.
  ~5 minutes single-threaded, sub-minute parallel.
- **`team2-full`** — full Cartesian disjoint-pair enumeration. ~25M
  battles per weather. Gated behind `--i-know-what-im-doing` so a casual
  invocation does not accidentally launch an overnight job.
- **`team-sample`** — `random.Random(seed)` draws of `2 * team_size`
  distinct pieces, split into team_a / team_b. Default 1000 battles per
  call. Optional `--tier-stratified` draws both teams from one tier so
  the matchup stays at a comparable power budget.

The plan suggested per-tier `--mode tier-normalized` for power-function
calibration. Since the shipped roster carries only `level = 1`, the
"tier-normalised" mode collapses into 1v1 + `team-sample --tier-stratified`.
Re-expand when L2/L3 are added.

## Observed behavior vs `power(T, L)`

Empirical reads from 500-battle non-stratified 2v2 samples at `clear`
weather:

- BT β anchors correctly at the weakest piece (`enemy_picket`, T1, β = 1.0).
- Tier ordering holds on average — T7+ pieces consistently land at higher
  β than T1-T3.
- **Individual within-tier spread is high.** Best T1 piece can have β > 9
  while the worst T1 has β = 1.0; sparse opponent overlap at 500 battles
  amplifies the per-piece noise. Need ~10× the samples for stable
  individual reads.
- Sergeant-at-Arms (T3) consistently over-performs across runs — flagged
  for content review.

The deviation column (`β / power(T, L)`) currently shows large
percentages on individual pieces. This is expected with the
weakest-anchored normalisation (plan §6.2): the bottom of the scale is
pinned to 1.0 but the top is unconstrained, so a T1 piece with β = 9
shows +800% deviation even though absolute β is small. If we want a
metric where deviation reads ≈ 0% on the "average" piece, anchor BT to
the geometric mean of T1L1 pieces instead. Held off — plan §6.2 is
explicit about weakest-anchored.

## Deterministic power-threshold model (replaces Bradley-Terry)

The expected win rate uses a step function: higher team power → 1.0,
lower → 0.0, equal → 0.5. This correctly reflects the deterministic
engine where outcomes are forced by power advantage, not random.

The previous Bradley-Terry implementation was removed because it
modelled win probability as a logistic curve (P(win) = β_A / (β_A + β_B)),
which is wrong for a deterministic engine.

## Mirror-match handling

Plan §4's `champion_as_enemy` adds `_sim_enemy` to the id. Generalised in
the shipped code to **two symmetric bridges with side suffixes** (`_a`
and `_b`) so a piece can sit on either side without collision. Original
ids stay in `MatchupConfig.piece_ids_*`; attribution never reads ids out
of `BattleResult` directly.

## Expected WR derivation

`expected_wr` is a power-budget benchmark: "what WR should this piece
score, given `power(T, L)` and the actual opponents it faced, assuming
team strength is additive?"

**Model** — deterministic power-threshold (step function):

```
team_a_power = Σ power(T, L) over team A pieces
team_b_power = Σ power(T, L) over team B pieces
if team_a_power > team_b_power:
    team_a_wr_expected = 1.0
elif team_a_power < team_b_power:
    team_a_wr_expected = 0.0
else:
    team_a_wr_expected = 0.5  # equal power → half-win
```

All pieces on the same team share the same `team_wr_expected` because
binary attribution treats the whole team as one win/loss event.

**Why additive** — T.18 sets `stat_multiplier = sqrt(power(T,L))` so that
`HP × DPS ≈ power`. Team combat budget is total damage absorbed × total
damage output, both summing across pieces. Multiplicative or
weakest-link models break the budget contract.

**Why this calc is non-trivial:**

- Per-opponent independent 1v1 model was the first instinct — wrong.
  Treats one team battle as N×M separate 1v1s, double-counts the
  team-level outcome, and produces a meaningless mean.
- The right formulation matches the actual `binary_win_rate`
  denominator: for each battle, each piece contributes `n_opponents ×
  team_wr_expected` to its expected-WR numerator and `n_opponents` to
  its denominator. Same shape as actual → `wr_delta = actual − expected`
  is unit-free and directly comparable.
- Tier-stratified sampling collapses to `expected_wr = 0.5` for
  everyone (same tier both sides) → `wr_delta` isolates kit quality
  cleanly.

**What `wr_delta` actually measures** — the sum of deviations from
raw stat performance:

- Ability / passive kit quality (T.20 content)
- Affinity clash (per-hit damage triangle by weather)
- Role coverage (tank + DPS > 2 DPS at the same total power)
- Composition synergies — **not yet shipped** (`TRAIT_REGISTRY` scaffold
  exists in `registries.py:77` but zero trait bonuses are registered;
  SPEC §D.8 marks synergies undesigned). Traits are opaque labels per
  V.8; the sim correctly drops them in `as_team_piece` since they
  change nothing measurable.

If synergies ship later, sim will need a `--synergies` flag and
`as_team_piece` must round-trip traits.

## Sudden-death override (`--max-ticks`)

The engine ships with `MAX_TICKS = 12_000` (~120s sim time), after which
sudden-death DOT escalates damage to force resolution. Good for the
auto-resolver in real gameplay; bad for balance sims because the piece
that loses the DOT race is whichever happens to have the lower max HP at
that moment, not whichever lost the actual fight.

`matchup.configure_sim_max_ticks(n)` mutates `loop_new.{MAX_TICKS,
SUDDEN_DEATH_TICK_START, HARD_CAP_TICKS}` in place. Sim runners apply
the cap via `ProcessPoolExecutor(initializer=...)` so each worker
imports `loop_new`, then gets the patch before any matchup runs.
Default in `runner.py` and `mega.py` is `1_000_000` ticks (~10_000s sim
time); pass `--max-ticks 0` to keep engine default.

True stalemates (e.g. two tanks doing 1 damage each, mitigation eats
everything) still resolve at `HARD_CAP_TICKS = max_ticks + 2_000` ticks
via the engine's existing timeout path. The `timed_out` flag in
`MatchupResult` records these — surface via `PieceStats.n_team_timeouts`
and the `timeout_rate` CSV column to spot stall-prone pieces.

## Follow-ups

- Re-run benchmarks once L2/L3 piece content lands.
- Add a `power-ladder` mode that fixes a reference piece against all
  opponents at every (T, L) — plan §3.2 row 3, deferred because there's
  no cross-tier data yet to validate against.
- Investigate per-tier-anchored BT normalisation when content evolves.
- `Sergeant-at-Arms` over-performance read — surface to content review.
- Optional: pytest `@balance` markers against curated even matchups
  (plan §10 P4). Not shipped — content still in flux.
