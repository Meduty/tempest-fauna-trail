"""Deterministic power-threshold + binary win-rate attribution."""
from __future__ import annotations

from src.game.models import CombatOutcome, WeatherState

from tools.simulation.matchup import MatchupConfig, MatchupResult
from tools.simulation.ratings import aggregate_stats, binary_win_rate, weather_metrics


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


def _result_w(
    team_a: tuple[str, ...],
    team_b: tuple[str, ...],
    outcome: CombatOutcome,
    weather: WeatherState,
) -> MatchupResult:
    return MatchupResult(
        config=MatchupConfig(team_a, team_b, weather),
        outcome=outcome,
        duration_ticks=100,
        hp_remaining_a=10 if outcome == CombatOutcome.WIN else 0,
        hp_remaining_b=10 if outcome == CombatOutcome.LOSS else 0,
        timed_out=False,
    )


# --- weather metrics (V.16) ---------------------------------------------------
# champ_aerion: affinity THUNDER, PRIMARY_PREY weather = MIST.

def test_weather_metrics_own_counter_sensitivity():
    """own = own-affinity weather wr; counter = prey weather wr; sens = range."""
    per_weather_wr = {
        "champ_aerion": {
            WeatherState.THUNDER: 0.7,  # own (affinity)
            WeatherState.MIST: 0.3,     # counter (preys on thunder)
            WeatherState.CLEAR: 0.5,
        }
    }
    wm = weather_metrics(per_weather_wr)
    own, counter, sens = wm["champ_aerion"]
    assert own == 0.7
    assert counter == 0.3
    assert abs(sens - 0.4) < 1e-9  # max 0.7 - min 0.3


def test_weather_metrics_single_weather_zero_sensitivity():
    """One weather -> sensitivity is exactly 0 (was the bug: always 0 per-file).

    counter is NaN, not 0.0: the counter weather is absent (no data), which must
    be distinguished from a genuine 0% win rate so aggregators can skip it.
    """
    import math
    wm = weather_metrics({"champ_aerion": {WeatherState.THUNDER: 0.7}})
    own, counter, sens = wm["champ_aerion"]
    assert own == 0.7              # thunder is its own weather
    assert math.isnan(counter)     # mist absent -> no data, not 0%
    assert sens == 0.0


def test_weather_metrics_unknown_piece_is_nan():
    import math
    wm = weather_metrics({"nonexistent_piece": {WeatherState.CLEAR: 0.9}})
    own, counter, sens = wm["nonexistent_piece"]
    assert math.isnan(own) and math.isnan(counter) and math.isnan(sens)


def test_aggregate_stats_weather_sensitivity_across_weathers():
    """Regression: aggregate_stats over multi-weather results yields a real,
    non-zero sensitivity — the per-weather-file caller bug aside, the math
    must work when fed multiple weathers."""
    results = [
        _result_w(("champ_aerion",), ("enemy_conscript",), CombatOutcome.WIN,
                  WeatherState.THUNDER),
        _result_w(("champ_aerion",), ("enemy_conscript",), CombatOutcome.LOSS,
                  WeatherState.MIST),
    ]
    s = aggregate_stats(results)["champ_aerion"]
    assert s.own_weather_wr == 1.0       # won in thunder (own)
    assert s.counter_weather_wr == 0.0   # lost in mist (prey)
    assert s.weather_sensitivity == 1.0  # 1.0 - 0.0


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


def test_aggregate_stats_expected_wr_uses_deterministic_power_threshold():
    """Real pieces from different tiers: expected_wr should be 1.0 for higher power.

    champ_ember_salamander is T3 (power = 2^(2/3) ≈ 1.587),
    enemy_conscript is T1 (power = 1.0). The deterministic model gives
    the higher-power piece expected_wr = 1.0 and the lower-power piece 0.0.
    """
    results = [
        _make_result(("champ_ember_salamander",), ("enemy_conscript",), CombatOutcome.WIN),
    ]
    stats = aggregate_stats(results)
    champ_exp = stats["champ_ember_salamander"].expected_wr
    conscript_exp = stats["enemy_conscript"].expected_wr
    # T3 vs T1: champ has strictly higher power -> expected 1.0
    assert champ_exp == 1.0
    assert conscript_exp == 0.0


def test_aggregate_stats_expected_wr_equal_power_is_half():
    """Equal team power -> expected_wr = 0.5 for both sides."""
    results = [
        _make_result(("enemy_conscript",), ("enemy_conscript",), CombatOutcome.WIN),
    ]
    stats = aggregate_stats(results)
    # Same piece on both sides: identical power -> 0.5
    assert stats["enemy_conscript"].expected_wr == 0.5


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
