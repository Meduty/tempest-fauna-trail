"""STR-vs-INT scaling-edge analysis (T.29 follow-up, D.25 evidence).

Hypothesis under test
---------------------
The universal auto-attack is `1.0*STR + 0.2*INT` (`combat/context.py`): STR
gets a **5x** auto multiplier vs INT. So a piece that scales its kit on STR
gets the auto damage **for free** alongside its ability damage, while an INT
caster's autos are near-dead weight. If ability INT-coeffs are sized the same
as STR-coeffs, STR pieces should systematically out-perform — and INT coeffs
*should be higher* to compensate.

What this measures
------------------
Runs **team** sims (tier-stratified random KvK — NOT 1v1, which rewards
self-sufficient duelists and confounds the signal), aggregates each piece's
win rate vs its power-expected win rate (`wr_delta` = observed - expected, a
**tier-controlled** over/under signal), then groups by roster axis:

  * `stat`      str / int / hybrid       (the scaling expression)
  * `playstyle` auto / ability / hybrid  (auto-attacker vs ability-user)
  * `stat x playstyle`                    (the crux: STR-ability vs INT-ability)

A positive mean `wr_delta` for a group = that group beats its power budget. The
prediction: `stat=str` and `playstyle=auto` over-perform; `stat=int` ability
users under-perform — the size of the gap is the INT-coeff correction needed.

Usage
-----
    python -m tools.simulation.stat_edge                 # default 3v3, 4000 battles, all weathers
    python -m tools.simulation.stat_edge --team-size 4 --n 6000 --weather clear
    python -m tools.simulation.stat_edge --csv results/stat_edge.csv

Enemies are excluded from the grouping (the STR/INT design lever is the
champion roster); they still populate the opposing teams.
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from tqdm import tqdm

from src.game.content import CHAMPION_DEF_BY_ID
from src.game.models import WeatherState

from tools.simulation.matchup import (
    _pool_initializer,
    base_of,
    configure_sim_max_ticks,
    parse_piece_id,
    run_matchup,
)
from tools.simulation.ratings import aggregate_stats
from tools.simulation.tournament import sample_teams

_WEATHERS = list(WeatherState)


def _run_with_progress(configs, label: str, workers: int):
    """Resolve configs with a tqdm progress bar (mirrors mega.run_stage)."""
    n = len(configs)
    if n == 0:
        return []
    if workers <= 1:
        configure_sim_max_ticks(0)
        return [run_matchup(c) for c in
                tqdm(configs, desc=label, total=n, unit="fight", smoothing=0.05)]
    results = []
    with ProcessPoolExecutor(max_workers=workers, initializer=_pool_initializer,
                             initargs=(0,)) as pool:
        futures = [pool.submit(run_matchup, c) for c in configs]
        for fut in tqdm(as_completed(futures), desc=label, total=n,
                        unit="fight", smoothing=0.05):
            results.append(fut.result())
    return results


def _axes(base_id: str) -> tuple[str, str, str, str] | None:
    """(stat, playstyle, intent, role) for a champion base id, or None if not a
    champion (enemies are excluded from grouping)."""
    d = CHAMPION_DEF_BY_ID.get(base_id)
    if d is None:
        return None
    return (d.stat, d.playstyle, d.intent, d.role if hasattr(d, "role") else "")


def _fmt_group(label: str, deltas: list[float], wrs: list[float]) -> str:
    if not deltas:
        return f"  {label:22} (no pieces)"
    return (
        f"  {label:22} n={len(deltas):3}  "
        f"win_rate={statistics.mean(wrs):+.3f}  "
        f"wr_delta={statistics.mean(deltas):+.4f}"
    )


def run(team_size: int, n_battles: int, weathers: list[WeatherState],
        workers: int, seed: int) -> dict[str, dict]:
    """Run the sweep; return per-(champion-base) aggregated win_rate + wr_delta."""
    all_results = []
    for w in weathers:
        configs = sample_teams(w, team_size, n_battles, seed=seed, tier_stratified=True)
        label = f"{team_size}v{team_size} @ {w.value}"
        all_results.extend(_run_with_progress(configs, label, workers))

    stats = aggregate_stats(all_results)

    # Pool per-piece stats by champion BASE id (across levels), champions only.
    by_base: dict[str, dict[str, float]] = defaultdict(
        lambda: {"wr_w": 0.0, "exp_w": 0.0, "games": 0.0}
    )
    for pid, ps in stats.items():
        base, _lvl = parse_piece_id(pid)
        if base not in CHAMPION_DEF_BY_ID:
            continue  # enemy — not part of the STR/INT design grouping
        wr = ps.n_pair_wins / ps.n_pair_games if ps.n_pair_games else 0.0
        acc = by_base[base]
        acc["wr_w"] += wr * ps.n_pair_games
        acc["exp_w"] += ps.expected_wr * ps.n_pair_games
        acc["games"] += ps.n_pair_games

    out: dict[str, dict] = {}
    for base, acc in by_base.items():
        g = acc["games"]
        if g <= 0:
            continue
        wr = acc["wr_w"] / g
        exp = acc["exp_w"] / g
        out[base] = {"win_rate": wr, "expected_wr": exp, "wr_delta": wr - exp,
                     "games": g}
    return out


def report(rows: dict[str, dict]) -> None:
    # Group by axis.
    by_stat: dict[str, list[str]] = defaultdict(list)
    by_play: dict[str, list[str]] = defaultdict(list)
    by_cross: dict[tuple[str, str], list[str]] = defaultdict(list)
    for base in rows:
        ax = _axes(base)
        if ax is None:
            continue
        stat, play, _intent, _role = ax
        by_stat[stat].append(base)
        by_play[play].append(base)
        by_cross[(stat, play)].append(base)

    def deltas(bases): return [rows[b]["wr_delta"] for b in bases]
    def wrs(bases): return [rows[b]["win_rate"] for b in bases]

    print("\n=== STR vs INT scaling edge (team sims, tier-stratified) ===")
    print("wr_delta = observed win_rate - power-expected win_rate (tier-controlled).")
    print("Positive = beats its power budget.\n")

    print("By stat axis (the scaling expression):")
    for stat in ("str", "int", "hybrid"):
        print(_fmt_group(stat, deltas(by_stat[stat]), wrs(by_stat[stat])))

    print("\nBy playstyle:")
    for play in ("auto", "ability", "hybrid"):
        print(_fmt_group(play, deltas(by_play[play]), wrs(by_play[play])))

    # Full stat × playstyle matrix — every mutation (auto-str, auto-int,
    # ap-str, ap-int, …) in a grid for direct comparison.
    stats_order = ("str", "int", "hybrid")
    plays_order = ("auto", "ability", "hybrid")

    def _cell(stat: str, play: str) -> str:
        bases = by_cross[(stat, play)]
        if not bases:
            return f"{'—':>18}"
        d = statistics.mean(deltas(bases))
        return f"{d:+.4f}|{statistics.mean(wrs(bases)):.2f}|n{len(bases):<2}".rjust(18)

    print("\nstat × playstyle matrix  [wr_delta | win_rate | n]:")
    print(f"  {'':9}" + "".join(f"{s:>18}" for s in stats_order))
    for play in plays_order:
        print(f"  {play:9}" + "".join(_cell(stat, play) for stat in stats_order))

    # The headline contrast.
    s_abil = deltas(by_cross[("str", "ability")])
    i_abil = deltas(by_cross[("int", "ability")])
    if s_abil and i_abil:
        gap = statistics.mean(s_abil) - statistics.mean(i_abil)
        print(f"\nSTR-ability vs INT-ability wr_delta gap: {gap:+.4f}")
        print("  >0 confirms STR ability-users out-perform (free auto tagalong) —")
        print("  INT ability-coeffs should be raised to close the gap (D.25).")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="stat_edge", description=__doc__)
    p.add_argument("--team-size", type=int, default=3)
    p.add_argument("--n", type=int, default=4000, help="battles per weather")
    p.add_argument("--weather", default="all",
                   help="'all' or a single weather state (e.g. clear)")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--csv", default=None, help="optional per-champion CSV out")
    args = p.parse_args(argv)

    weathers = _WEATHERS if args.weather == "all" else [WeatherState(args.weather)]
    rows = run(args.team_size, args.n, weathers, args.workers, args.seed)
    report(rows)

    if args.csv:
        path = Path(args.csv)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as f:
            wr = csv.writer(f)
            wr.writerow(["champion", "stat", "playstyle", "intent",
                         "win_rate", "expected_wr", "wr_delta", "games"])
            for base in sorted(rows):
                ax = _axes(base)
                if ax is None:
                    continue
                stat, play, intent, _role = ax
                r = rows[base]
                wr.writerow([base, stat, play, intent,
                             f"{r['win_rate']:.4f}", f"{r['expected_wr']:.4f}",
                             f"{r['wr_delta']:.4f}", int(r["games"])])
        print(f"\n[stat_edge] wrote {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
