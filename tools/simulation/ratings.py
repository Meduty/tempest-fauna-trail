"""Power-rating derivation from MatchupResult sets (T.25).

Metrics:

    binary_win_rate  — per-piece wins / games, attributing every piece on the
                       winning team a 1 and on the losing team a 0 (draws =
                       0.5 each). Cheap, biased by opponent field.

    expected_winrate — deterministic power-threshold model. The engine is
                       deterministic: higher total power wins 100%, lower
                       loses 100%, equal power scores 0.5 (secondary factors
                       average out across many matchups).

Attribution rule (binary, per amendment T.25):
    Every piece on the winning team scores 1 win vs every piece on the
    losing team. Draws split 0.5 each direction.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.game.models import CombatOutcome, WeatherState
from src.game.scaling import power
from src.game.weather_effects import ring_relation, RingRelation

from tools.simulation.matchup import MatchupResult, get_piece


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
    expected_wr: float      # deterministic power-threshold expected win rate:
                            # wins (1.0) vs lower-power opponents, half-wins
                            # (0.5) vs equal-power opponents, losses (0.0) vs
                            # higher-power opponents. Uses team-additive
                            # power(T,L).
    # Weather affinity clash metrics
    own_weather_wr: float       # win rate when fighting in own affinity weather
    counter_weather_wr: float   # win rate when fighting in weather that preys on you
    weather_sensitivity: float  # max(wr across weathers) - min(wr across weathers)


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
    # Per-weather tracking split across two maps:
    # weather_wins: {piece_id: {weather: wins}}
    # weather_games: {piece_id: {weather: games}}
    weather_wins: dict[str, dict[WeatherState, float]] = {}
    weather_games: dict[str, dict[WeatherState, int]] = {}

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

        # Deterministic power-threshold expected WR: higher total power
        # wins (1.0), lower loses (0.0), equal scores 0.5.
        team_a_power = sum(_power_of(pid) for pid in r.config.piece_ids_a)
        team_b_power = sum(_power_of(pid) for pid in r.config.piece_ids_b)
        if team_a_power > team_b_power:
            team_a_exp_wr = 1.0
        elif team_a_power < team_b_power:
            team_a_exp_wr = 0.0
        else:
            team_a_exp_wr = 0.5
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
            # Weather tracking
            if pa not in weather_wins:
                weather_wins[pa] = {}
                weather_games[pa] = {}
            w = r.config.weather
            weather_wins[pa][w] = weather_wins[pa].get(w, 0.0) + a_score * n_opp_b
            weather_games[pa][w] = weather_games[pa].get(w, 0) + n_opp_b

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
            # Weather tracking
            if pb not in weather_wins:
                weather_wins[pb] = {}
                weather_games[pb] = {}
            w = r.config.weather
            weather_wins[pb][w] = weather_wins[pb].get(w, 0.0) + b_score * n_opp_a
            weather_games[pb][w] = weather_games[pb].get(w, 0) + n_opp_a

    out: dict[str, PieceStats] = {}
    for pid in n_matches:
        m = n_matches[pid]
        n_exp = expected_wr_n.get(pid, 0)

        # Compute weather affinity metrics
        own_weather_wr = 0.0
        counter_weather_wr = 0.0
        weather_sensitivity = 0.0
        pw = weather_wins.get(pid, {})
        pg = weather_games.get(pid, {})
        try:
            piece = get_piece(pid)
            piece_affinity = piece.affinity
        except (KeyError, ValueError):
            piece_affinity = None

        if piece_affinity is not None and pg:
            # Per-weather win rates
            per_weather_wr: dict[WeatherState, float] = {}
            for w_state, g in pg.items():
                if g > 0:
                    per_weather_wr[w_state] = pw.get(w_state, 0.0) / g

            # Own weather = where piece affinity matches battle weather (SELF)
            if piece_affinity in per_weather_wr:
                own_weather_wr = per_weather_wr[piece_affinity]

            # Counter weather = weather that preys on this piece (PRIMARY_PREY)
            for w_state, wr_val in per_weather_wr.items():
                rel = ring_relation(piece_affinity, w_state)
                if rel == RingRelation.PRIMARY_PREY:
                    counter_weather_wr = wr_val
                    break

            if per_weather_wr:
                weather_sensitivity = max(per_weather_wr.values()) - min(per_weather_wr.values())

        out[pid] = PieceStats(
            n_matches=m,
            n_pair_games=pair_games.get(pid, 0),
            n_pair_wins=pair_wins.get(pid, 0.0),
            n_team_wins=n_team_wins.get(pid, 0),
            n_team_draws=n_team_draws.get(pid, 0),
            n_team_timeouts=n_team_timeouts.get(pid, 0),
            mean_duration=duration_sum[pid] / m if m > 0 else 0.0,
            expected_wr=expected_wr_sum.get(pid, 0.0) / n_exp if n_exp > 0 else 0.0,
            own_weather_wr=own_weather_wr,
            counter_weather_wr=counter_weather_wr,
            weather_sensitivity=weather_sensitivity,
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
