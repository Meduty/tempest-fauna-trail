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

Defaults are conservative; raise --n-battles to scale up. Each stage runs
through one shared pool so workers are reused.

Usage examples:

    python -m tools.simulation.mega                       # default mega run
    python -m tools.simulation.mega --workers 16
    python -m tools.simulation.mega --n2 100000 --n3 50000
    python -m tools.simulation.mega --skip team3-sample
    python -m tools.simulation.mega --weather clear       # restrict to one weather
    python -m tools.simulation.mega --enable-2v2-full --weather clear

Engine is byte-deterministic; same flags reproduce the same CSV byte-for-byte.
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ProcessPoolExecutor
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
from tools.simulation.ratings import aggregate_stats, binary_win_rate, bradley_terry
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
    *,
    chunksize: int = 64,
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
        for cfg in tqdm(stage.configs, desc=label, total=n, unit="fight"):
            results.append(run_matchup(cfg))
        return results

    # imap_unordered streams results back as workers finish — perfect for tqdm.
    results = []
    iterator = pool.map(run_matchup, stage.configs, chunksize=chunksize)
    for r in tqdm(iterator, desc=label, total=n, unit="fight"):
        results.append(r)
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


def write_stage_outputs(stage: Stage, results: list[MatchupResult], out_dir: Path) -> None:
    results_path = out_dir / f"results_{stage.name}_{stage.weather.value}.csv"
    ratings_path = out_dir / f"ratings_{stage.name}_{stage.weather.value}.csv"
    write_results_csv(results_path, results)
    wr = binary_win_rate(results)
    bt = bradley_terry(results)
    stats = aggregate_stats(results)
    write_ratings_csv(ratings_path, win_rates=wr, bt_ratings=bt, stats=stats)
    print(f"[mega] wrote {results_path} + {ratings_path}")
    return wr, bt, stats  # type: ignore[return-value]


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
    p.add_argument("--chunksize", type=int, default=64,
                   help="ProcessPool chunksize. Default 64.")
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
            results = run_stage(stage, pool, chunksize=args.chunksize)
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
