"""Power-rating derivation from MatchupResult sets (T.25).

Two complementary metrics:

    binary_win_rate  — per-piece wins / games, attributing every piece on the
                       winning team a 1 and on the losing team a 0 (draws =
                       0.5 each). Cheap, biased by opponent field.

    bradley_terry    — latent strength β_i ≥ 0 such that
                       P(i beats j) = β_i / (β_i + β_j). Iterative MLE update
                       converges in ~30 iterations. Normalised so the
                       weakest piece has β = 1.0; output is directly
                       comparable across roster + against power(T, L).

Attribution rule (binary, per amendment T.25):
    Every piece on the winning team scores 1 win vs every piece on the
    losing team. Draws split 0.5 each direction.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from src.game.models import CombatOutcome
from src.game.scaling import power

from tools.simulation.matchup import MatchupResult, get_piece


# ---------------------------------------------------------------------------
# Attribution
# ---------------------------------------------------------------------------


def _pairwise_records(
    results: list[MatchupResult],
) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], int]]:
    """Aggregate per-piece pairwise wins + game counts.

    Returns (wins, games) where keys are (piece_a, piece_b) with the
    semantic "piece_a scored against piece_b". Both directions always
    populated (games[a,b] == games[b,a]).
    """
    wins: dict[tuple[str, str], float] = {}
    games: dict[tuple[str, str], int] = {}
    for r in results:
        a_score = 1.0 if r.outcome == CombatOutcome.WIN else (
            0.5 if r.outcome == CombatOutcome.DRAW else 0.0
        )
        b_score = 1.0 - a_score
        for pa in r.config.piece_ids_a:
            for pb in r.config.piece_ids_b:
                wins[(pa, pb)] = wins.get((pa, pb), 0.0) + a_score
                wins[(pb, pa)] = wins.get((pb, pa), 0.0) + b_score
                games[(pa, pb)] = games.get((pa, pb), 0) + 1
                games[(pb, pa)] = games.get((pb, pa), 0) + 1
    return wins, games


# ---------------------------------------------------------------------------
# Public metrics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PieceStats:
    """Per-piece aggregate observed during a tournament run."""
    n_matches: int          # battles the piece participated in (any side)
    n_pair_games: int       # per-piece pair games (sum over opponents)
    n_pair_wins: float      # per-piece pair wins (binary attribution, draws = 0.5)
    n_team_wins: int        # team-level wins counted once per battle
    n_team_draws: int       # team-level draws counted once per battle
    n_team_timeouts: int    # battles the piece was in that timed out
    mean_duration: float    # mean battle duration (ticks)
    expected_wr: float      # mean team_power_self / (team_power_self + team_power_opp)
                            # over battles & per-opponent pair count; uses
                            # power(T,L) and assumes team strength is additive
                            # (matches T.18 HP*DPS ≈ P budget). See journal.


def aggregate_stats(results: list[MatchupResult]) -> dict[str, PieceStats]:
    """Per-piece tournament stats.

    `expected_wr` is calibrated against the actual opponent field, not the
    full roster — a T10 piece that only ever faced T9s gets a lower
    expected WR than one that faced T1s. Use to read whether a piece beats
    its tier-implied expectation given who it actually fought.
    """
    n_matches: dict[str, int] = {}
    n_team_wins: dict[str, int] = {}
    n_team_draws: dict[str, int] = {}
    n_team_timeouts: dict[str, int] = {}
    duration_sum: dict[str, int] = {}
    pair_wins: dict[str, float] = {}
    pair_games: dict[str, int] = {}
    expected_wr_sum: dict[str, float] = {}
    expected_wr_n: dict[str, int] = {}

    def _power_of(pid: str) -> float:
        try:
            p = get_piece(pid)
            return power(p.tier, p.level)
        except (KeyError, ValueError):
            return 1.0

    for r in results:
        a_score = 1.0 if r.outcome == CombatOutcome.WIN else (
            0.5 if r.outcome == CombatOutcome.DRAW else 0.0
        )
        b_score = 1.0 - a_score
        is_a_win = r.outcome == CombatOutcome.WIN
        is_draw = r.outcome == CombatOutcome.DRAW
        n_opp_a = len(r.config.piece_ids_a)
        n_opp_b = len(r.config.piece_ids_b)

        # Team-additive expected WR per T.18 power budget (HP*DPS ≈ P, sum
        # across roster slots). All pieces on the same team share the same
        # team_wr_expected because binary attribution makes the whole team
        # win or lose together.
        team_a_power = sum(_power_of(pid) for pid in r.config.piece_ids_a)
        team_b_power = sum(_power_of(pid) for pid in r.config.piece_ids_b)
        total_power = team_a_power + team_b_power
        team_a_exp_wr = (team_a_power / total_power) if total_power > 0 else 0.5
        team_b_exp_wr = 1.0 - team_a_exp_wr

        for pa in r.config.piece_ids_a:
            n_matches[pa] = n_matches.get(pa, 0) + 1
            if is_a_win:
                n_team_wins[pa] = n_team_wins.get(pa, 0) + 1
            if is_draw:
                n_team_draws[pa] = n_team_draws.get(pa, 0) + 1
            if r.timed_out:
                n_team_timeouts[pa] = n_team_timeouts.get(pa, 0) + 1
            duration_sum[pa] = duration_sum.get(pa, 0) + r.duration_ticks
            # Per-opponent pair accounting matches binary_win_rate's
            # denominator: each opponent contributes one "pair game" with
            # the team-level expected WR replicated across the row.
            pair_wins[pa] = pair_wins.get(pa, 0.0) + a_score * n_opp_b
            pair_games[pa] = pair_games.get(pa, 0) + n_opp_b
            expected_wr_sum[pa] = expected_wr_sum.get(pa, 0.0) + team_a_exp_wr * n_opp_b
            expected_wr_n[pa] = expected_wr_n.get(pa, 0) + n_opp_b

        for pb in r.config.piece_ids_b:
            n_matches[pb] = n_matches.get(pb, 0) + 1
            if not is_a_win and not is_draw:
                n_team_wins[pb] = n_team_wins.get(pb, 0) + 1
            if is_draw:
                n_team_draws[pb] = n_team_draws.get(pb, 0) + 1
            if r.timed_out:
                n_team_timeouts[pb] = n_team_timeouts.get(pb, 0) + 1
            duration_sum[pb] = duration_sum.get(pb, 0) + r.duration_ticks
            pair_wins[pb] = pair_wins.get(pb, 0.0) + b_score * n_opp_a
            pair_games[pb] = pair_games.get(pb, 0) + n_opp_a
            expected_wr_sum[pb] = expected_wr_sum.get(pb, 0.0) + team_b_exp_wr * n_opp_a
            expected_wr_n[pb] = expected_wr_n.get(pb, 0) + n_opp_a

    out: dict[str, PieceStats] = {}
    for pid in n_matches:
        m = n_matches[pid]
        n_exp = expected_wr_n.get(pid, 0)
        out[pid] = PieceStats(
            n_matches=m,
            n_pair_games=pair_games.get(pid, 0),
            n_pair_wins=pair_wins.get(pid, 0.0),
            n_team_wins=n_team_wins.get(pid, 0),
            n_team_draws=n_team_draws.get(pid, 0),
            n_team_timeouts=n_team_timeouts.get(pid, 0),
            mean_duration=duration_sum[pid] / m if m > 0 else 0.0,
            expected_wr=expected_wr_sum.get(pid, 0.0) / n_exp if n_exp > 0 else 0.0,
        )
    return out


def binary_win_rate(results: list[MatchupResult]) -> dict[str, float]:
    """Per-piece win rate aggregated over all battles the piece participated in."""
    wins_total: dict[str, float] = {}
    games_total: dict[str, int] = {}
    for r in results:
        a_score = 1.0 if r.outcome == CombatOutcome.WIN else (
            0.5 if r.outcome == CombatOutcome.DRAW else 0.0
        )
        b_score = 1.0 - a_score
        n_opp_b = len(r.config.piece_ids_b)
        n_opp_a = len(r.config.piece_ids_a)
        for pa in r.config.piece_ids_a:
            wins_total[pa] = wins_total.get(pa, 0.0) + a_score * n_opp_b
            games_total[pa] = games_total.get(pa, 0) + n_opp_b
        for pb in r.config.piece_ids_b:
            wins_total[pb] = wins_total.get(pb, 0.0) + b_score * n_opp_a
            games_total[pb] = games_total.get(pb, 0) + n_opp_a
    return {pid: wins_total[pid] / games_total[pid] for pid in wins_total if games_total[pid] > 0}


def bradley_terry(
    results: list[MatchupResult],
    *,
    iterations: int = 100,
    tol: float = 1e-6,
    normalise_to_weakest: bool = True,
) -> dict[str, float]:
    """Iterative MLE for Bradley-Terry latent strengths.

    Update rule (Hunter 2004 MM algorithm):

        β_i^new = W_i / Σ_{j != i} n_{ij} / (β_i + β_j)

    where W_i is total per-piece wins (binary attribution) and n_{ij} is
    total per-piece games between i and j across all battles. Converges
    in ~30 iterations for typical roster sizes.

    Output normalised so the piece with smallest β has β = 1.0; remaining
    pieces are scaled identically. Pieces with zero games are dropped.
    """
    wins, games = _pairwise_records(results)
    piece_ids = sorted({pid for pair in games for pid in pair})
    if not piece_ids:
        return {}

    # Aggregate per-piece W_i.
    wins_total: dict[str, float] = {pid: 0.0 for pid in piece_ids}
    for (a, b), w in wins.items():
        wins_total[a] += w

    # Pieces that have zero wins would collapse to 0 under MM; floor at a
    # small fraction of typical β so the ratio update stays finite.
    epsilon = 1e-3

    beta: dict[str, float] = {pid: 1.0 for pid in piece_ids}

    for _ in range(iterations):
        new_beta: dict[str, float] = {}
        for i in piece_ids:
            denom = 0.0
            for j in piece_ids:
                if i == j:
                    continue
                n_ij = games.get((i, j), 0)
                if n_ij == 0:
                    continue
                denom += n_ij / (beta[i] + beta[j])
            w_i = wins_total[i]
            if denom > 0 and w_i > 0:
                new_beta[i] = w_i / denom
            else:
                new_beta[i] = epsilon

        # Normalise to geometric mean = 1 each iteration; prevents drift
        # and keeps the scale stable between updates.
        log_sum = sum(math.log(v) for v in new_beta.values() if v > 0)
        n_nonzero = sum(1 for v in new_beta.values() if v > 0)
        if n_nonzero > 0:
            geom_mean = math.exp(log_sum / n_nonzero)
            if geom_mean > 0:
                for k in new_beta:
                    new_beta[k] = new_beta[k] / geom_mean

        max_delta = max(abs(new_beta[pid] - beta[pid]) for pid in piece_ids)
        beta = new_beta
        if max_delta < tol:
            break

    if normalise_to_weakest:
        nonzero = [v for v in beta.values() if v > 0]
        if nonzero:
            min_beta = min(nonzero)
            for pid in beta:
                beta[pid] = beta[pid] / min_beta

    return beta
