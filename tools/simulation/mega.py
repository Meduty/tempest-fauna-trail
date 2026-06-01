"""Mega sweep — run every proposed T.25 simulation flavour in one go.

Stages queued in order, each executed via ProcessPoolExecutor with a tqdm
progress bar. Outputs land under --out (default results/mega/):

    results_<stage>_<weather>.csv    raw battle log
    ratings_<stage>_<weather>.csv    win-rate + Bradley-Terry betas
    run.log                          stdout snapshot (when redirected)

Stages:
    1v1            full C(120,2) pairs per weather (default ALL weathers)
    team2-sample   N random 2v2 matchups per weather
    team3-sample   N random 3v3 matchups per weather
    team2-full     opt-in (~25M battles per weather; requires --enable-2v2-full)

Defaults are conservative; raise --n2 / --n3 to scale up. Each stage runs
through one shared pool so workers are reused.

Engine is byte-deterministic; same flags reproduce the same CSV byte-for-byte.

----------------------------------------------------------------------------
Arguments — what each flag controls
----------------------------------------------------------------------------

--out PATH
    Output directory. One pair of CSVs per (stage, weather) is written:
    `results_<stage>_<weather>.csv` (raw battles) + `ratings_<stage>_<weather>.csv`
    (per-piece win rate, expected_wr, wr_delta, beta, deviation, timeouts).
    Default: `results/mega`.

--workers N
    Process pool size. Engine is pure Python and CPU-bound; near-linear
    speed-up up to ~16 cores, diminishing past ~32 (pickle IPC tax).
    **Set to physical core count**, NOT logical (SMT contention hurts Python
    on this workload). Pass 1 to run serial (useful for debugging tracebacks).

--weather W
    Restrict to one weather (`clear`, `cloudy`, `mist`, `rain`, `snow`,
    `thunder`). Default: all 6 — each stage runs once per weather, so total
    battle count is `n_stages × 6`. Use when iterating quickly on one
    weather's affinity-clash effects or when running the heavy
    `--enable-2v2-full` mode.

--n2 N
    Battles per weather for `team2-sample`. Default 50_000. Higher = tighter
    Bradley-Terry convergence (each piece sees more opponents). Below ~5_000
    per weather, BT β has visible noise per piece.

--n3 N
    Same as --n2 but for `team3-sample` (3v3 random teams). Default 30_000.
    3v3 needs more samples than 2v2 to cover the wider opponent field —
    don't reduce blindly.

--seed N
    `random.Random` seed for `sample_teams`. Engine is byte-deterministic
    anyway, so changing the seed only changes WHICH matchups get sampled,
    not the outcomes of those matchups. Use different seeds to cross-check
    a finding isn't an artefact of one specific sample.

--tier-stratified
    In `team-sample` stages, both teams are drawn from one tier band per
    battle. Same total battle count, but every matchup is now intra-tier.
    Consequence: `expected_wr` collapses to 0.5 for every piece (equal
    team power on both sides), so `wr_delta = actual − 0.5` isolates kit
    quality from raw stat differential. BT β still ranks within-tier but
    cannot be compared across tiers (no cross-tier games to link the
    groups).

--skip STAGE
    Drop a stage from the queue. Repeatable. Choices: `1v1`,
    `team2-sample`, `team3-sample`, `team2-full`. Useful when iterating on
    a specific stage's content or when a stage has already been run and
    cached.

--enable-2v2-full
    Adds the `team2-full` stage — full Cartesian product of disjoint 2v2
    pairings. ~25M battles per weather. ~36 hours on 8 cores per weather.
    Only sane with `--weather` restricting to one weather; gated behind
    this opt-in flag to prevent accidental overnight jobs. Use when you
    want absolute confidence on a single weather, not statistical samples.

--max-ticks N
    Override the combat engine's `MAX_TICKS` constant inside each worker.
    Default: 1_000_000 — effectively disables the sudden-death DOT so
    battles resolve organically on stats alone, not on whichever piece
    happened to lose the timeout race. Pass 0 to keep the engine default
    (12_000 ticks ≈ 120s sim time, with sudden death engaged).

----------------------------------------------------------------------------
Usage examples — paired with what each measures
----------------------------------------------------------------------------

Default mega run — full balance pass across the full weather grid:

    python -m tools.simulation.mega --workers 8 --out results/mega

    Measures: per-piece power deviation across all 6 weathers, full 1v1
    matrix plus sampled team play at 2v2 and 3v3. ~523k battles total.
    ~12-30 min on 8 cores. The canonical run to do after any roster or
    kit change. `ratings_1v1_clear.csv` is the cleanest single signal;
    `ratings_team*_*.csv` shows team-context deviations.

Quick smoke — verify the simulation harness works end-to-end:

    python -m tools.simulation.mega --weather clear --n2 1000 --n3 500 \\
        --skip 1v1

    Measures: nothing balance-relevant. Runs in ~30s. Use after editing
    sim code (`tools/simulation/*`) to confirm CSVs and progress bars
    still emit correctly. Outputs ARE noisy at this scale — do not draw
    balance conclusions from this run.

Single weather only — iterate fast on one affinity:

    python -m tools.simulation.mega --weather rain --workers 8

    Measures: full sim grid restricted to Rain. ~85k battles in default
    config (≈ 1/6 of the full run). Use when investigating one weather's
    affinity clash interactions without paying the 6× weather multiplier.

Bigger samples — tighten Bradley-Terry convergence:

    python -m tools.simulation.mega --workers 8 \\
        --n2 200000 --n3 100000 --out results/big

    Measures: same balance signals as the default run but with ~4× the
    samples per stage. Use when default-run `wr_delta` for a piece sits
    near a decision threshold (e.g. ±5%) and you need to disambiguate
    real over/under-performance from sampling noise. β values stabilise
    to 3 significant figures at this sample size.

Tier-stratified — isolate kit quality from raw tier differential:

    python -m tools.simulation.mega --tier-stratified --workers 8

    Measures: per-piece WR within its tier band. `expected_wr` is 0.5
    for everyone (equal-power teams both sides), so `wr_delta` directly
    reads as "how much better than average for my tier". Use when
    comparing kits across tiers is muddying the picture — e.g. T7 piece
    looks weak in unstratified but is actually fine relative to other
    T7s.

Full 2v2 Cartesian — exhaustive single-weather audit:

    python -m tools.simulation.mega --weather clear --enable-2v2-full \\
        --workers 8

    Measures: every disjoint 2v2 pairing under one weather. ~25M battles.
    ~36 hours on 8 cores. Use when a sample-based result is contested
    and you want the ground truth distribution with zero sampling
    artefacts. NEVER combine with all-weather — runtime is days.

Stage isolation — re-run after editing one stage's content:

    python -m tools.simulation.mega --skip team3-sample --workers 8
    python -m tools.simulation.mega --skip team3-sample --skip team2-sample

    Measures: only the unskipped stages. Use when a 1v1 finding needs
    re-confirmation and team stages are unaffected by the change, or
    vice-versa. Saves the bulk of the runtime when only one stage's data
    is stale.

Seed sweep — cross-check that a finding is not a sampling artefact:

    python -m tools.simulation.mega --seed 7 --workers 8
    python -m tools.simulation.mega --seed 13 --workers 8

    Measures: the same balance grid with two different sampled opponent
    sets. If a piece shows `wr_delta = +18%` under seed 7 and `+5%` under
    seed 13, the +18% read was largely seed noise. Genuine over/under-
    performance is seed-stable.

Workstation scaling — match physical core count:

    python -m tools.simulation.mega --workers 16   # 16-core box
    python -m tools.simulation.mega --workers 32   # 32-core workstation

    Measures: same data, ~2× / ~4× faster than the 8-core baseline. Don't
    set workers > physical cores — Python on this workload loses to SMT
    contention.

Engine default MAX_TICKS (sudden death engaged):

    python -m tools.simulation.mega --max-ticks 0 --workers 8

    Measures: balance under the SHIPPED engine constraint. Useful as a
    reality check — the auto-resolver players actually see uses the
    12_000-tick cap, so this run shows whether sudden-death-prone pieces
    suffer in real play. Expect `timeout_rate` columns to be >0 on
    stalemate-prone matchups, biasing them down.

Custom MAX_TICKS — explicit ceiling between the two extremes:

    python -m tools.simulation.mega --max-ticks 500000 --workers 8

    Measures: balance under a middle-ground time budget. Default 1_000_000
    effectively never times out; 12_000 hits sudden death often. 500_000
    catches genuine deadlocks without biasing fast-resolving matchups.

Live log capture — watch progress AND keep an audit trail:

    python -m tools.simulation.mega --workers 8 2>&1 | tee results/mega/run.log

    Measures: same as default run. The `tee` captures the per-stage
    tier-bucketed summary printout for post-hoc review. Useful when
    running unattended.

Big overnight balance pass — maximum coverage:

    python -m tools.simulation.mega --workers 16 \\
        --n2 500000 --n3 200000 --out results/overnight

    Measures: ~4.5M battles total. ~3-6 hours on 16 cores. Use before a
    release / milestone snapshot. β values stable to 4 significant
    figures; per-piece WR noise floor below ±0.5%.

----------------------------------------------------------------------------
Reading the output
----------------------------------------------------------------------------

Sort `ratings_*.csv` by `wr_delta` to find pieces beating or missing their
power-budget expectation:

    wr_delta > 0    overperforming vs raw power(T,L) budget — likely strong
                    kit, favourable affinity matchups, or good role coverage.
    wr_delta < 0    underperforming — weak kit, unfavourable matchups,
                    stat distribution doesn't fit role.

Guard rails when interpreting:

    n_matches < 20      noise floor; ignore the row.
    timeout_rate > 0.1  piece stalls — wr_delta is unreliable (forced
                        outcomes biased by who happens to win sudden death).
    beta_deviation_pct  same signal as wr_delta but in β space. Use when
                        comparing across tiers (β is power-normalised).
    expected_wr ≈ 0.5   sample is tier-stratified or otherwise balanced —
                        wr_delta reads as pure kit quality.

When a piece flags as outlier, cross-check with a `--seed` sweep before
filing a content change — a single-run +20% can drop to +5% under a
different seed.
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from tqdm import tqdm

from src.game.models import WeatherState

from tools.simulation.matchup import (
    MatchupConfig,
    MatchupResult,
    _pool_initializer,
    configure_sim_max_ticks,
    run_matchup,
)
from tools.simulation.ratings import PieceStats, aggregate_stats, binary_win_rate, bradley_terry
from tools.simulation.report import print_summary, write_ratings_csv, write_results_csv
from tools.simulation.tournament import enumerate_1v1, enumerate_team2, sample_teams


ALL_WEATHERS = [
    WeatherState.CLEAR,
    WeatherState.CLOUDY,
    WeatherState.MIST,
    WeatherState.RAIN,
    WeatherState.SNOW,
    WeatherState.THUNDER,
]


# ---------------------------------------------------------------------------
# Stage description
# ---------------------------------------------------------------------------


@dataclass
class Stage:
    name: str
    weather: WeatherState
    configs: list[MatchupConfig]


# ---------------------------------------------------------------------------
# Pool execution with progress
# ---------------------------------------------------------------------------


def run_stage(
    stage: Stage,
    pool: ProcessPoolExecutor | None,
) -> list[MatchupResult]:
    """Resolve every config in a stage with a tqdm bar.

    If pool is None, runs serial (no progress overhead on small stages).
    """
    n = len(stage.configs)
    if n == 0:
        return []

    label = f"{stage.name} @ {stage.weather.value}"
    if pool is None:
        results: list[MatchupResult] = []
        for cfg in tqdm(stage.configs, desc=label, total=n, unit="fight", smoothing=0.05):
            results.append(run_matchup(cfg))
        return results

    # Submit all configs and stream results back as workers finish.
    results = []
    futures = {pool.submit(run_matchup, cfg): cfg for cfg in stage.configs}
    for fut in tqdm(as_completed(futures), desc=label, total=n, unit="fight", smoothing=0.05):
        results.append(fut.result())
    return results


# ---------------------------------------------------------------------------
# Stage builders
# ---------------------------------------------------------------------------


def build_stages(
    args: argparse.Namespace,
    weathers: list[WeatherState],
) -> list[Stage]:
    """Materialise every requested stage. Skipped stages are dropped here."""
    stages: list[Stage] = []
    skip = set(args.skip or [])

    if "1v1" not in skip:
        for w in weathers:
            stages.append(Stage("1v1", w, enumerate_1v1(w)))

    if "team2-sample" not in skip:
        for w in weathers:
            configs = sample_teams(
                w, team_size=2, n_battles=args.n2,
                seed=args.seed, tier_stratified=args.tier_stratified,
            )
            stages.append(Stage("team2-sample", w, configs))

    if "team3-sample" not in skip:
        for w in weathers:
            configs = sample_teams(
                w, team_size=3, n_battles=args.n3,
                seed=args.seed, tier_stratified=args.tier_stratified,
            )
            stages.append(Stage("team3-sample", w, configs))

    if args.enable_2v2_full and "team2-full" not in skip:
        for w in weathers:
            stages.append(Stage("team2-full", w, enumerate_team2(w)))

    return stages


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def write_stage_outputs(
    stage: Stage, results: list[MatchupResult], out_dir: Path
) -> tuple[dict[str, float], dict[str, float], dict[str, PieceStats]]:
    results_path = out_dir / f"results_{stage.name}_{stage.weather.value}.csv"
    ratings_path = out_dir / f"ratings_{stage.name}_{stage.weather.value}.csv"
    write_results_csv(results_path, results)
    wr = binary_win_rate(results)
    bt = bradley_terry(results)
    stats = aggregate_stats(results)
    write_ratings_csv(ratings_path, win_rates=wr, bt_ratings=bt, stats=stats)
    print(f"[mega] wrote {results_path} + {ratings_path}")
    return wr, bt, stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_weather(raw: str) -> WeatherState:
    try:
        return WeatherState(raw.lower())
    except ValueError:
        valid = ", ".join(w.value for w in WeatherState)
        raise argparse.ArgumentTypeError(f"unknown weather {raw!r}; expected one of: {valid}")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tools.simulation.mega",
                                description="Mega T.25 sweep with progress bars.")
    p.add_argument("--out", type=Path, default=Path("results/mega"),
                   help="Output directory. Default results/mega")
    p.add_argument("--workers", type=int, default=8,
                   help="Process pool size. Default 8. Pass 1 for serial.")
    p.add_argument("--weather", type=_parse_weather, default=None,
                   help="Restrict to one weather. Default: all 6.")
    p.add_argument("--n2", type=int, default=50_000,
                   help="Battle count per weather for team2-sample. Default 50000.")
    p.add_argument("--n3", type=int, default=30_000,
                   help="Battle count per weather for team3-sample. Default 30000.")
    p.add_argument("--seed", type=int, default=42, help="Sampling RNG seed.")
    p.add_argument("--tier-stratified", action="store_true",
                   help="Draw teams within one tier band per battle.")
    p.add_argument("--skip", action="append", choices=["1v1", "team2-sample",
                                                        "team3-sample", "team2-full"],
                   help="Stage(s) to skip. Repeatable.")
    p.add_argument("--enable-2v2-full", action="store_true",
                   help="Include full 2v2 Cartesian stage (~25M battles per weather).")
    p.add_argument("--max-ticks", type=int, default=1_000_000,
                   help="Combat engine MAX_TICKS override for sim runs. "
                        "Default 1_000_000 (disables sudden death). Pass 0 "
                        "to keep engine default.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    weathers = [args.weather] if args.weather else ALL_WEATHERS
    print(f"[mega] weathers = {[w.value for w in weathers]}; "
          f"workers = {args.workers}; out = {args.out}")

    print("[mega] enumerating stages...")
    stages = build_stages(args, weathers)
    if not stages:
        print("[mega] nothing to do (all stages skipped)")
        return 0

    total = sum(len(s.configs) for s in stages)
    print(f"[mega] queue: {len(stages)} stages, {total:,} total battles")
    for s in stages:
        print(f"  - {s.name:14} @ {s.weather.value:8} : {len(s.configs):>10,} battles")

    # Apply tick cap inline for the serial path; workers get it via initializer.
    configure_sim_max_ticks(args.max_ticks)
    if args.max_ticks > 0:
        print(f"[mega] combat MAX_TICKS overridden to {args.max_ticks:,} "
              f"(sudden death disabled within cap)")

    t0 = time.monotonic()
    pool: ProcessPoolExecutor | None = None
    if args.workers > 1:
        pool = ProcessPoolExecutor(
            max_workers=args.workers,
            initializer=_pool_initializer,
            initargs=(args.max_ticks,),
        )
    try:
        for stage in stages:
            t_stage = time.monotonic()
            results = run_stage(stage, pool)
            elapsed = time.monotonic() - t_stage
            rate = len(results) / elapsed if elapsed > 0 else 0.0
            print(f"[mega] {stage.name} @ {stage.weather.value}: "
                  f"{len(results):,} battles in {elapsed:.1f}s ({rate:.0f}/s)")
            wr, bt, stats = write_stage_outputs(stage, results, args.out)

            # Per-stage console summary (tier-bucketed)
            print_summary(win_rates=wr, bt_ratings=bt, stats=stats)
    finally:
        if pool is not None:
            pool.shutdown(wait=True)

    print(f"[mega] all stages done in {time.monotonic() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
