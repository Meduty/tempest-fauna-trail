"""Tournament generators + executor."""
from __future__ import annotations

import pytest

from src.game.models import WeatherState

from tools.simulation.matchup import all_piece_ids
from tools.simulation.tournament import (
    enumerate_1v1,
    enumerate_team2,
    run_tournament,
    sample_teams,
)


def test_enumerate_1v1_pair_count():
    pieces = ["champ_ember_salamander", "champ_pebbleback_pangolin", "enemy_conscript"]
    configs = enumerate_1v1(WeatherState.CLEAR, piece_ids=pieces)
    assert len(configs) == 3  # C(3,2)
    for cfg in configs:
        assert len(cfg.piece_ids_a) == 1
        assert len(cfg.piece_ids_b) == 1
        assert cfg.piece_ids_a[0] != cfg.piece_ids_b[0]


def test_enumerate_1v1_full_roster_size():
    configs = enumerate_1v1(WeatherState.CLEAR)
    n = len(all_piece_ids())
    assert len(configs) == n * (n - 1) // 2


def test_enumerate_team2_disjoint():
    pieces = ["champ_ember_salamander", "champ_pebbleback_pangolin",
              "enemy_conscript", "enemy_picket"]
    configs = enumerate_team2(WeatherState.CLEAR, piece_ids=pieces)
    # C(4,2)=6 teams, C(6,2)=15 team pairings, minus 12 that share a piece
    # (any pair of 2-teams sharing a piece) -> 3 disjoint pairs
    assert len(configs) == 3
    for cfg in configs:
        assert set(cfg.piece_ids_a).isdisjoint(set(cfg.piece_ids_b))


def test_sample_teams_deterministic():
    a = sample_teams(WeatherState.CLEAR, team_size=2, n_battles=20, seed=7)
    b = sample_teams(WeatherState.CLEAR, team_size=2, n_battles=20, seed=7)
    assert a == b
    c = sample_teams(WeatherState.CLEAR, team_size=2, n_battles=20, seed=8)
    assert a != c


def test_sample_teams_teams_disjoint():
    configs = sample_teams(WeatherState.CLEAR, team_size=2, n_battles=50, seed=1)
    assert len(configs) == 50
    for cfg in configs:
        assert set(cfg.piece_ids_a).isdisjoint(set(cfg.piece_ids_b))
        assert len(cfg.piece_ids_a) == 2
        assert len(cfg.piece_ids_b) == 2


def test_sample_teams_tier_stratified_same_tier():
    """Stratified sampling: every piece in both teams must share one tier."""
    from tools.simulation.matchup import get_piece
    configs = sample_teams(
        WeatherState.CLEAR, team_size=2, n_battles=20, seed=1, tier_stratified=True
    )
    for cfg in configs:
        tiers = {get_piece(pid).tier for pid in cfg.piece_ids_a + cfg.piece_ids_b}
        assert len(tiers) == 1, f"stratified config crosses tiers: {tiers}"


def test_sample_teams_rejects_bad_inputs():
    with pytest.raises(ValueError):
        sample_teams(WeatherState.CLEAR, team_size=0, n_battles=5)
    with pytest.raises(ValueError):
        sample_teams(WeatherState.CLEAR, team_size=2, n_battles=-1)


def test_run_tournament_serial_matches_results():
    pieces = ["champ_ember_salamander", "champ_pebbleback_pangolin", "enemy_conscript"]
    configs = enumerate_1v1(WeatherState.CLEAR, piece_ids=pieces)
    results = run_tournament(configs, workers=1)
    assert len(results) == len(configs)
    for r in results:
        assert r.duration_ticks > 0
