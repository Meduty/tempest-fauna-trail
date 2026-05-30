"""Matchup bridge + run_matchup behavior."""
from __future__ import annotations

import pytest

from src.game.content import CHAMPION_ROSTER, ENEMY_ROSTER, get_champion, get_enemy
from src.game.models import CombatOutcome, WeatherState

from tools.simulation.matchup import (
    SIDE_A_SUFFIX,
    SIDE_B_SUFFIX,
    MatchupConfig,
    as_enemy_piece,
    as_team_piece,
    all_piece_ids,
    configure_sim_max_ticks,
    get_piece,
    run_matchup,
)


def test_as_enemy_piece_copies_combat_fields():
    champ = get_champion("champ_ember_salamander")
    enemy = as_enemy_piece(champ)
    assert enemy.id == champ.id + SIDE_B_SUFFIX
    assert enemy.max_hp == champ.max_hp
    assert enemy.strength == champ.strength
    assert enemy.intelligence == champ.intelligence
    assert enemy.affinity == champ.affinity
    assert enemy.role == champ.role
    assert enemy.tier == champ.tier
    assert enemy.active_ability == champ.active_ability
    assert enemy.passive_ability == champ.passive_ability


def test_as_team_piece_drops_traits():
    enemy = get_enemy("enemy_conscript")
    team_piece = as_team_piece(enemy)
    assert team_piece.id == enemy.id + SIDE_A_SUFFIX
    # Enemy has no traits; team-side cast must produce empty traits list
    assert team_piece.traits == []
    assert team_piece.max_hp == enemy.max_hp


def test_all_piece_ids_covers_full_roster():
    ids = all_piece_ids()
    assert len(ids) == len(CHAMPION_ROSTER) + len(ENEMY_ROSTER)
    assert set(ids) == set(CHAMPION_ROSTER) | set(ENEMY_ROSTER)


def test_get_piece_unknown_raises():
    with pytest.raises(KeyError):
        get_piece("not_a_real_piece")


def test_run_matchup_deterministic():
    cfg = MatchupConfig(
        piece_ids_a=("champ_ember_salamander",),
        piece_ids_b=("enemy_conscript",),
        weather=WeatherState.CLEAR,
    )
    r1 = run_matchup(cfg)
    r2 = run_matchup(cfg)
    assert r1.outcome == r2.outcome
    assert r1.duration_ticks == r2.duration_ticks
    assert r1.hp_remaining_a == r2.hp_remaining_a
    assert r1.hp_remaining_b == r2.hp_remaining_b


def test_run_matchup_mirror_does_not_collide():
    """Same piece on both sides must not crash via id collision."""
    cfg = MatchupConfig(
        piece_ids_a=("champ_ember_salamander",),
        piece_ids_b=("champ_ember_salamander",),
        weather=WeatherState.CLEAR,
    )
    r = run_matchup(cfg)
    assert r.outcome in (CombatOutcome.WIN, CombatOutcome.LOSS, CombatOutcome.DRAW)


def test_run_matchup_team():
    """Multi-piece teams resolve to a coherent BattleResult."""
    cfg = MatchupConfig(
        piece_ids_a=("champ_ember_salamander", "champ_pebbleback_pangolin"),
        piece_ids_b=("enemy_conscript", "enemy_picket"),
        weather=WeatherState.CLEAR,
    )
    r = run_matchup(cfg)
    assert r.duration_ticks > 0
    assert r.outcome in (CombatOutcome.WIN, CombatOutcome.LOSS, CombatOutcome.DRAW)


def test_configure_sim_max_ticks_mutates_loop_constants():
    """configure_sim_max_ticks must update all three related loop constants."""
    from src.game.combat import loop_new
    original_max = loop_new.MAX_TICKS
    original_sd = loop_new.SUDDEN_DEATH_TICK_START
    original_hc = loop_new.HARD_CAP_TICKS
    try:
        configure_sim_max_ticks(500_000)
        assert loop_new.MAX_TICKS == 500_000
        assert loop_new.SUDDEN_DEATH_TICK_START == 500_000
        assert loop_new.HARD_CAP_TICKS == 502_000
    finally:
        loop_new.MAX_TICKS = original_max
        loop_new.SUDDEN_DEATH_TICK_START = original_sd
        loop_new.HARD_CAP_TICKS = original_hc


def test_configure_sim_max_ticks_zero_is_noop():
    """Passing 0 must leave engine constants untouched."""
    from src.game.combat import loop_new
    original_max = loop_new.MAX_TICKS
    configure_sim_max_ticks(0)
    assert loop_new.MAX_TICKS == original_max
