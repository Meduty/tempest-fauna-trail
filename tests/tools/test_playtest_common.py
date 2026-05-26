"""Unit tests for tools/playtest/_common.py helpers."""
from __future__ import annotations

import argparse

import pytest

from src.game.bosses.data import get_boss_def
from src.game.encounter import generate_boss_encounter
from src.game.models import CombatOutcome, WeatherState
from src.game.route import STAGES

from tools.playtest._common import (
    default_team,
    format_table,
    Column,
    node_position_in_stage,
    parse_champion_ids,
    parse_enemy_ids,
    parse_weather,
    resolve_boss_combat,
    stage_def,
)


class TestParseWeather:
    def test_known_state(self) -> None:
        assert parse_weather("rain") == WeatherState.RAIN

    def test_case_insensitive(self) -> None:
        assert parse_weather("ThUnDeR") == WeatherState.THUNDER

    def test_unknown_raises(self) -> None:
        with pytest.raises(argparse.ArgumentTypeError):
            parse_weather("solar_eclipse")


class TestParseChampionIds:
    def test_empty(self) -> None:
        assert parse_champion_ids("") == []

    def test_single(self) -> None:
        team = parse_champion_ids("champ_dawnwisp")
        assert len(team) == 1
        assert team[0].id == "champ_dawnwisp"

    def test_multi(self) -> None:
        team = parse_champion_ids("champ_dawnwisp,champ_veldt_pronghorn")
        assert [c.id for c in team] == ["champ_dawnwisp", "champ_veldt_pronghorn"]

    def test_unknown_raises(self) -> None:
        with pytest.raises(argparse.ArgumentTypeError):
            parse_champion_ids("champ_made_up_animal")


class TestParseEnemyIds:
    def test_single(self) -> None:
        squad = parse_enemy_ids("enemy_conscript")
        assert squad[0].id == "enemy_conscript"

    def test_unknown_raises(self) -> None:
        with pytest.raises(argparse.ArgumentTypeError):
            parse_enemy_ids("enemy_not_real")


class TestDefaultTeam:
    def test_deterministic(self) -> None:
        a = default_team(stage_index=1, size=3)
        b = default_team(stage_index=1, size=3)
        assert [c.id for c in a] == [c.id for c in b]

    def test_size_respected(self) -> None:
        team = default_team(stage_index=2, size=4)
        assert len(team) == 4

    def test_picks_appropriate_tier(self) -> None:
        team = default_team(stage_index=3, size=3)
        assert all(c.tier == 3 for c in team)


class TestStageHelpers:
    def test_stage_def_range(self) -> None:
        with pytest.raises(argparse.ArgumentTypeError):
            stage_def(7)

    def test_node_position_inside_stage(self) -> None:
        assert node_position_in_stage(1, 1) == 0
        # Stage 1 has 10 nodes
        assert node_position_in_stage(1, 10) == 9
        # First node of stage 2 == absolute index 11
        assert node_position_in_stage(2, 11) == 0

    def test_node_position_out_of_stage(self) -> None:
        with pytest.raises(argparse.ArgumentTypeError):
            node_position_in_stage(1, 11)


class TestFormatTable:
    def test_alignment_and_header(self) -> None:
        cols = [Column("a", 4), Column("b", 4, "right")]
        lines = format_table(cols, [["1", "2"], ["xx", "yyyy"]])
        assert lines[0].startswith("a   ")
        # lines[0]=header, [1]=divider, [2]=first row, [3]=second row.
        # Right-aligned column ends with the value of the second row.
        assert lines[3].endswith("yyyy")

    def test_truncates_overlong(self) -> None:
        cols = [Column("a", 3)]
        lines = format_table(cols, [["abcdef"]])
        # Truncated to width 3 with ellipsis on the last char
        assert lines[-1].rstrip() == "ab…"


class TestResolveBossCombat:
    def test_runs_and_returns_battle_result(self) -> None:
        encounter = generate_boss_encounter(run_seed=7, node_index=10, stage=STAGES[0])
        # Use a strong team so the call actually exercises the path
        from src.game.content import get_champion

        team = [
            get_champion("champ_aurion"),
            get_champion("champ_nerei"),
            get_champion("champ_aerion"),
        ]
        result = resolve_boss_combat(
            team, encounter, WeatherState.CLEAR, run_seed=7, node_id="s1-n10-test",
        )
        assert result.node_id == "s1-n10-test"
        assert result.outcome in {CombatOutcome.WIN, CombatOutcome.LOSS, CombatOutcome.DRAW}
        assert result.duration_ticks > 0
        # Recorder populated events
        assert len(result.events) > 0

    def test_deterministic(self) -> None:
        encounter = generate_boss_encounter(run_seed=11, node_index=10, stage=STAGES[0])
        from src.game.content import get_champion

        team = [get_champion("champ_aurion"), get_champion("champ_nerei")]
        a = resolve_boss_combat(team, encounter, WeatherState.CLEAR, run_seed=11)
        b = resolve_boss_combat(team, encounter, WeatherState.CLEAR, run_seed=11)
        assert a.outcome == b.outcome
        assert a.duration_ticks == b.duration_ticks
        assert len(a.events) == len(b.events)


def test_resolve_boss_combat_uses_authored_spawn() -> None:
    """Sanity: boss appears in the encounter we're about to resolve."""
    encounter = generate_boss_encounter(run_seed=1, node_index=10, stage=STAGES[0])
    boss_def = get_boss_def(stage_index=1)
    assert encounter.boss_enemy.id == boss_def.id
