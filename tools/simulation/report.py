"""CSV + console output for T.25 simulation runs."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from src.game.scaling import power

from tools.simulation.matchup import MatchupResult, get_piece
from tools.simulation.ratings import PieceStats


# ---------------------------------------------------------------------------
# CSV writers
# ---------------------------------------------------------------------------


def write_results_csv(path: Path, results: list[MatchupResult]) -> None:
    """One row per matchup. Use for raw analysis / matrix reconstruction."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "team_a", "team_b", "weather", "outcome",
            "duration_ticks", "hp_remaining_a", "hp_remaining_b", "timed_out",
        ])
        for r in results:
            writer.writerow([
                "|".join(r.config.piece_ids_a),
                "|".join(r.config.piece_ids_b),
                r.config.weather.value,
                r.outcome.value,
                r.duration_ticks,
                r.hp_remaining_a,
                r.hp_remaining_b,
                int(r.timed_out),
            ])


def write_ratings_csv(
    path: Path,
    *,
    win_rates: dict[str, float],
    stats: dict[str, PieceStats] | None = None,
) -> None:
    """One row per piece. Columns:

        piece_id, name, affinity, role, tier, level, kind,
        n_matches, n_pair_games, n_pair_wins, n_team_wins, n_team_draws,
        n_team_timeouts, mean_duration_ticks,
        win_rate, expected_wr, wr_delta,
        expected_power, timeout_rate

    expected_wr uses the deterministic power-threshold model: higher team
    power wins (1.0), lower loses (0.0), equal scores 0.5.
    wr_delta = win_rate - expected_wr is the unit-free "over/under" signal.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    piece_ids = sorted(set(win_rates) | set(stats or {}))
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "piece_id", "name", "affinity", "role", "tier", "level", "kind",
            "n_matches", "n_pair_games", "n_pair_wins",
            "n_team_wins", "n_team_draws", "n_team_timeouts",
            "mean_duration_ticks",
            "win_rate", "expected_wr", "wr_delta",
            "expected_power", "timeout_rate",
            "own_weather_wr", "counter_weather_wr", "weather_sensitivity",
        ])
        for pid in piece_ids:
            try:
                piece = get_piece(pid)
                name = piece.name
                affinity = piece.affinity.value
                role = piece.role
                tier = piece.tier
                level = piece.level
                expected_power = power(tier, level)
                kind = "champion" if pid.startswith("champ_") else "enemy"
            except KeyError:
                name = ""
                affinity = ""
                role = ""
                tier = 0
                level = 0
                expected_power = 0.0
                kind = ""
            wr = win_rates.get(pid, 0.0)
            s = (stats or {}).get(pid)
            n_matches = s.n_matches if s else 0
            n_pair_games = s.n_pair_games if s else 0
            n_pair_wins = s.n_pair_wins if s else 0.0
            n_team_wins = s.n_team_wins if s else 0
            n_team_draws = s.n_team_draws if s else 0
            n_team_timeouts = s.n_team_timeouts if s else 0
            mean_duration = s.mean_duration if s else 0.0
            expected_wr = s.expected_wr if s else 0.0
            wr_delta = wr - expected_wr
            timeout_rate = (n_team_timeouts / n_matches) if n_matches > 0 else 0.0
            own_weather_wr = s.own_weather_wr if s else 0.0
            counter_weather_wr = s.counter_weather_wr if s else 0.0
            weather_sensitivity = s.weather_sensitivity if s else 0.0

            writer.writerow([
                pid, name, affinity, role, tier, level, kind,
                n_matches, n_pair_games, f"{n_pair_wins:.2f}",
                n_team_wins, n_team_draws, n_team_timeouts,
                f"{mean_duration:.1f}",
                f"{wr:.4f}", f"{expected_wr:.4f}", f"{wr_delta:+.4f}",
                f"{expected_power:.4f}",
                f"{timeout_rate:.4f}",
                f"{own_weather_wr:.4f}", f"{counter_weather_wr:.4f}",
                f"{weather_sensitivity:.4f}",
            ])


# ---------------------------------------------------------------------------
# Console summary
# ---------------------------------------------------------------------------


def print_summary(
    *,
    win_rates: dict[str, float],
    stats: dict[str, PieceStats] | None = None,
    top_n: int = 5,
    wr_delta_alert: float = 0.15,
) -> None:
    """Tier-bucketed top/bottom by wr_delta (actual − expected WR).

    `wr_delta` is the cleanest signal: positive = beats power-implied
    expectation, negative = under-performs. Uses the deterministic power-
    threshold model where higher power wins 100%, equal scores 50%.
    """
    if not win_rates:
        print("[summary] no ratings to report")
        return

    @dataclass
    class _Row:
        pid: str
        tier: int
        n: int
        wr: float
        exp_wr: float
        delta: float

    piece_ids = set(win_rates) | set(stats or {})
    rows_by_tier: dict[int, list[_Row]] = {}
    for pid in piece_ids:
        try:
            piece = get_piece(pid)
            tier = piece.tier
        except KeyError:
            tier = 0
        s = (stats or {}).get(pid)
        wr = win_rates.get(pid, 0.0)
        exp_wr = s.expected_wr if s else 0.0
        delta = wr - exp_wr
        n = s.n_matches if s else 0
        rows_by_tier.setdefault(tier, []).append(
            _Row(pid, tier, n, wr, exp_wr, delta)
        )

    n_total = sum(r.n for tier_rows in rows_by_tier.values() for r in tier_rows)
    print()
    print(f"=== T.25 summary — {sum(len(v) for v in rows_by_tier.values())} pieces, "
          f"{n_total:,} per-piece matches ===")
    header = (f"  {'piece_id':<32} {'T':>2} {'n':>5} "
              f"{'WR':>6} {'exp':>6} {'delta':>7}")

    flagged = 0
    for tier in sorted(rows_by_tier):
        rows = rows_by_tier[tier]
        rows.sort(key=lambda r: -r.delta)
        print(f"\n-- Tier {tier} ({len(rows)} pieces) --")
        print(header)
        top = rows[:top_n]
        bottom = rows[-top_n:] if len(rows) > top_n else []
        for r in top:
            tag = "  +" if r.delta > wr_delta_alert else ""
            print(f"  {r.pid:<32} {r.tier:>2} {r.n:>5} "
                  f"{r.wr:>6.3f} {r.exp_wr:>6.3f} {r.delta:>+7.3f}{tag}")
        if bottom and bottom != top:
            print(f"  {'...':<32}")
            for r in bottom:
                tag = "  -" if r.delta < -wr_delta_alert else ""
                print(f"  {r.pid:<32} {r.tier:>2} {r.n:>5} "
                      f"{r.wr:>6.3f} {r.exp_wr:>6.3f} {r.delta:>+7.3f}{tag}")
        flagged += sum(1 for r in rows if abs(r.delta) > wr_delta_alert)

    print(f"\n[summary] {flagged} piece(s) outside ±{wr_delta_alert:+.0%} wr_delta band")
