"""CLI entry point for power simulation (T.25).

Examples:
    # Full 1v1 sweep at clear weather, single process
    python -m tools.simulation.runner --mode 1v1 --weather clear --out results/

    # 1v1 across all 6 weathers, 8 workers
    python -m tools.simulation.runner --mode 1v1 --all-weathers --workers 8 \
        --out results/

    # Sample 2000 random 2v2 matchups, tier-stratified
    python -m tools.simulation.runner --mode team-sample --team-size 2 \
        --n-battles 2000 --tier-stratified --weather clear --out results/

    # Full N=2 Cartesian (heavy — confirm with --i-know-what-im-doing)
    python -m tools.simulation.runner --mode team2-full --weather clear \
        --i-know-what-im-doing --out results/

Sampling defaults are intentionally conservative; pass --n-battles to
scale up. Engine is byte-deterministic — same seed reproduces the run.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from src.game.models import WeatherState

from tools.simulation.matchup import all_piece_ids
from tools.simulation.ratings import aggregate_stats, binary_win_rate
from tools.simulation.report import print_summary, write_ratings_csv, write_results_csv
from tools.simulation.tournament import (
    enumerate_1v1,
    enumerate_team2,
    run_tournament,
    sample_teams,
)


_WEATHERS = [WeatherState.CLEAR, WeatherState.CLOUDY, WeatherState.MIST,
             WeatherState.RAIN, WeatherState.SNOW, WeatherState.THUNDER]


def _parse_weather(raw: str) -> WeatherState:
    try:
        return WeatherState(raw.lower())
    except ValueError:
        valid = ", ".join(w.value for w in WeatherState)
        raise argparse.ArgumentTypeError(f"Unknown weather {raw!r}; expected one of: {valid}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tools.simulation.runner")
    parser.add_argument(
        "--mode",
        required=True,
        choices=["1v1", "team2-full", "team-sample"],
        help="Tournament generator: 1v1 = C(N,2) pairs; team2-full = full 2v2 "
             "Cartesian (heavy); team-sample = random N-piece teams.",
    )
    parser.add_argument("--weather", type=_parse_weather, default=WeatherState.CLEAR)
    parser.add_argument("--all-weathers", action="store_true",
                        help="Run every weather; outputs one CSV per weather.")
    parser.add_argument("--team-size", type=int, default=2,
                        help="Pieces per team for team-sample mode. Default 2.")
    parser.add_argument("--n-battles", type=int, default=1000,
                        help="Battle count for team-sample mode. Default 1000.")
    parser.add_argument("--tier-stratified", action="store_true",
                        help="In team-sample mode, draw both teams from one tier band.")
    parser.add_argument("--seed", type=int, default=42, help="Sampling RNG seed.")
    parser.add_argument("--workers", type=int, default=1,
                        help="Process pool size. Default 1 (serial).")
    parser.add_argument("--out", type=Path, default=Path("results"),
                        help="Output directory for CSVs. Default ./results")
    parser.add_argument(
        "--i-know-what-im-doing",
        action="store_true",
        help="Required to launch team2-full mode (~25M battles per weather).",
    )
    parser.add_argument(
        "--max-ticks", type=int, default=1_000_000,
        help="Override combat engine MAX_TICKS for the sim. Default 1_000_000 "
             "(disables sudden death so battles resolve organically). Pass 0 "
             "to keep the engine default (12000).",
    )
    return parser


def _build_configs(args: argparse.Namespace, weather: WeatherState) -> list:
    if args.mode == "1v1":
        return enumerate_1v1(weather)
    if args.mode == "team2-full":
        if not args.i_know_what_im_doing:
            raise SystemExit(
                "team2-full enumerates ~25M battles per weather. "
                "Pass --i-know-what-im-doing to confirm."
            )
        return enumerate_team2(weather)
    if args.mode == "team-sample":
        return sample_teams(
            weather, args.team_size, args.n_battles,
            seed=args.seed, tier_stratified=args.tier_stratified,
        )
    raise SystemExit(f"unknown mode: {args.mode}")


def _run_weather(args: argparse.Namespace, weather: WeatherState) -> None:
    print(f"[runner] {args.mode} @ {weather.value}: generating configs...")
    configs = _build_configs(args, weather)
    print(f"[runner] {args.mode} @ {weather.value}: {len(configs)} battles "
          f"(workers={args.workers})")

    t0 = time.monotonic()
    results = run_tournament(configs, workers=args.workers, max_ticks=args.max_ticks)
    elapsed = time.monotonic() - t0
    rate = len(results) / elapsed if elapsed > 0 else 0.0
    print(f"[runner] {args.mode} @ {weather.value}: done in {elapsed:.1f}s "
          f"({rate:.0f} battles/s)")

    out_dir = args.out
    results_path = out_dir / f"results_{args.mode}_{weather.value}.csv"
    ratings_path = out_dir / f"ratings_{args.mode}_{weather.value}.csv"

    write_results_csv(results_path, results)

    wr = binary_win_rate(results)
    stats = aggregate_stats(results)
    write_ratings_csv(ratings_path, win_rates=wr, stats=stats)

    print(f"[runner] wrote {results_path}")
    print(f"[runner] wrote {ratings_path}")
    print_summary(win_rates=wr, stats=stats)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    weathers = _WEATHERS if args.all_weathers else [args.weather]
    print(f"[runner] roster size = {len(all_piece_ids())}; "
          f"weathers = {[w.value for w in weathers]}")
    for w in weathers:
        _run_weather(args, w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
