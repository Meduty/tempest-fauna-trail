"""Bradley-Terry + binary win-rate attribution."""
from __future__ import annotations

from dataclasses import dataclass

from src.game.models import CombatOutcome, WeatherState

from tools.simulation.matchup import MatchupConfig, MatchupResult
from tools.simulation.ratings import aggregate_stats, binary_win_rate, bradley_terry


def _make_result(
    team_a: tuple[str, ...],
    team_b: tuple[str, ...],
    outcome: CombatOutcome,
) -> MatchupResult:
    return MatchupResult(
        config=MatchupConfig(team_a, team_b, WeatherState.CLEAR),
        outcome=outcome,
        duration_ticks=100,
        hp_remaining_a=10 if outcome == CombatOutcome.WIN else 0,
        hp_remaining_b=10 if outcome == CombatOutcome.LOSS else 0,
        timed_out=False,
    )


def test_binary_win_rate_1v1_attribution():
    """A beats B 3 of 4 times -> A is 0.75, B is 0.25."""
    results = [
        _make_result(("A",), ("B",), CombatOutcome.WIN),
        _make_result(("A",), ("B",), CombatOutcome.WIN),
        _make_result(("A",), ("B",), CombatOutcome.WIN),
        _make_result(("A",), ("B",), CombatOutcome.LOSS),
    ]
    wr = binary_win_rate(results)
    assert wr["A"] == 0.75
    assert wr["B"] == 0.25


def test_binary_win_rate_team_attribution():
    """Team {A,B} beats {C,D}: A and B each get 2 wins (one vs C, one vs D)."""
    results = [_make_result(("A", "B"), ("C", "D"), CombatOutcome.WIN)]
    wr = binary_win_rate(results)
    assert wr["A"] == 1.0
    assert wr["B"] == 1.0
    assert wr["C"] == 0.0
    assert wr["D"] == 0.0


def test_binary_win_rate_draw_is_half():
    results = [_make_result(("A",), ("B",), CombatOutcome.DRAW)]
    wr = binary_win_rate(results)
    assert wr["A"] == 0.5
    assert wr["B"] == 0.5


def test_bradley_terry_converges_with_clear_ordering():
    """Round-robin where A > B > C produces β_A > β_B > β_C."""
    results = []
    # A always beats B
    for _ in range(5):
        results.append(_make_result(("A",), ("B",), CombatOutcome.WIN))
    # B always beats C
    for _ in range(5):
        results.append(_make_result(("B",), ("C",), CombatOutcome.WIN))
    # A always beats C
    for _ in range(5):
        results.append(_make_result(("A",), ("C",), CombatOutcome.WIN))

    bt = bradley_terry(results, iterations=200)
    assert bt["A"] > bt["B"] > bt["C"]
    # Weakest normalised to 1.0
    assert min(bt.values()) >= 1.0 - 1e-6


def test_bradley_terry_handles_team_battles():
    """Team battles feed per-piece pairwise records."""
    results = [
        _make_result(("A", "B"), ("C", "D"), CombatOutcome.WIN),
        _make_result(("A", "B"), ("C", "D"), CombatOutcome.WIN),
        _make_result(("A", "B"), ("C", "D"), CombatOutcome.WIN),
    ]
    bt = bradley_terry(results, iterations=100)
    # All winners should rank strictly higher than all losers
    assert min(bt["A"], bt["B"]) > max(bt["C"], bt["D"])


def test_bradley_terry_empty_input():
    assert bradley_terry([]) == {}


# ---------------------------------------------------------------------------
# aggregate_stats
# ---------------------------------------------------------------------------


def test_aggregate_stats_match_counts():
    """n_matches counts each battle a piece played, not per-opponent pairs."""
    results = [
        _make_result(("champ_ember_salamander",), ("enemy_conscript",), CombatOutcome.WIN),
        _make_result(("champ_ember_salamander",), ("enemy_picket",), CombatOutcome.WIN),
        _make_result(("champ_ember_salamander",), ("enemy_picket",), CombatOutcome.LOSS),
    ]
    stats = aggregate_stats(results)
    assert stats["champ_ember_salamander"].n_matches == 3
    assert stats["champ_ember_salamander"].n_team_wins == 2
    assert stats["enemy_picket"].n_matches == 2
    assert stats["enemy_picket"].n_team_wins == 1


def test_aggregate_stats_expected_wr_uses_team_additive_power():
    """Real pieces from different tiers: expected_wr should differ from 0.5.

    champ_ember_salamander is T3 (power = 2^(2/3) ≈ 1.587),
    enemy_conscript is T1 (power = 1.0). Expected WR for champ should
    be ≈ 1.587 / (1.587 + 1.0) ≈ 0.613 in a 1v1.
    """
    results = [
        _make_result(("champ_ember_salamander",), ("enemy_conscript",), CombatOutcome.WIN),
    ]
    stats = aggregate_stats(results)
    champ_exp = stats["champ_ember_salamander"].expected_wr
    conscript_exp = stats["enemy_conscript"].expected_wr
    # T3 vs T1: champ should beat 0.6
    assert champ_exp > 0.55
    assert conscript_exp < 0.45
    # Probabilities sum to 1 across the matchup
    assert abs(champ_exp + conscript_exp - 1.0) < 1e-6


def test_aggregate_stats_team_battle_shares_expected_wr():
    """All pieces in a team share the same team-level expected WR."""
    results = [
        _make_result(
            ("champ_ember_salamander", "champ_pebbleback_pangolin"),
            ("enemy_conscript", "enemy_picket"),
            CombatOutcome.WIN,
        ),
    ]
    stats = aggregate_stats(results)
    # Both team-A pieces should have identical expected_wr
    assert (
        abs(stats["champ_ember_salamander"].expected_wr
            - stats["champ_pebbleback_pangolin"].expected_wr) < 1e-6
    )
    # And team-B pieces identical too
    assert (
        abs(stats["enemy_conscript"].expected_wr
            - stats["enemy_picket"].expected_wr) < 1e-6
    )


def test_aggregate_stats_timeout_tracking():
    r = MatchupResult(
        config=MatchupConfig(("A",), ("B",), WeatherState.CLEAR),
        outcome=CombatOutcome.DRAW,
        duration_ticks=12000,
        hp_remaining_a=50,
        hp_remaining_b=50,
        timed_out=True,
    )
    stats = aggregate_stats([r])
    assert stats["A"].n_team_timeouts == 1
    assert stats["A"].n_team_draws == 1
    assert stats["A"].mean_duration == 12000


def test_aggregate_stats_pair_games_matches_binary_win_rate():
    """pair_games / pair_wins must reconstruct binary_win_rate exactly."""
    results = [
        _make_result(("A", "B"), ("C", "D"), CombatOutcome.WIN),
        _make_result(("A", "B"), ("C", "D"), CombatOutcome.LOSS),
        _make_result(("A",), ("D",), CombatOutcome.WIN),
    ]
    stats = aggregate_stats(results)
    wr = binary_win_rate(results)
    for pid, s in stats.items():
        expected_wr = s.n_pair_wins / s.n_pair_games if s.n_pair_games > 0 else 0.0
        assert abs(wr[pid] - expected_wr) < 1e-9
