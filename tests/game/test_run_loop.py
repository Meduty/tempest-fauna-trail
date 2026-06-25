"""T.15b — full per-node loop closure + save/load round-trip (V.2/V.36/V.69).

Drives the reward orchestrator across a whole run to a terminal state, and
confirms a run with a real `BattleResult` in its log round-trips through
`save_run`/`load_run` unchanged (so Continue-after-load resumes identically).
"""

from __future__ import annotations

from types import SimpleNamespace

from src.game.combat import resolve_combat
from src.game.content import CHAMPION_ROSTER, ENEMY_ROSTER
from src.game.economy import apply_node_result
from src.game.models import CombatOutcome, RunStatus, WeatherState
from src.game.run_init import champion_offer, new_run
from src.game.save import load_run, save_run


def _win():
    return SimpleNamespace(outcome=CombatOutcome.WIN, team_damage_dealt={}, node_id="")


def _loss():
    return SimpleNamespace(outcome=CombatOutcome.LOSS, team_damage_dealt={}, node_id="")


def test_full_run_of_wins_reaches_victory():
    run = new_run(5, champion_offer(5)[0])
    steps = 0
    while run.status == RunStatus.IN_PROGRESS and steps < 200:
        apply_node_result(run, _win())
        steps += 1
    assert run.status == RunStatus.VICTORY
    # One battle logged per node in the route.
    assert len(run.battle_log) == len(run.route)
    assert steps == len(run.route)


def test_losses_deplete_hearts_then_defeat():
    """Hearts model (T.38, V.71) — a loss is survivable; the run ends only when
    Hearts hit 0 (nodes 2-4 here are non-boss, non-final)."""
    run = new_run(5, champion_offer(5)[0])
    apply_node_result(run, _win())                      # clear node 1, hearts intact
    assert run.hearts == 3 and run.status == RunStatus.IN_PROGRESS
    for expected_hearts in (2, 1, 0):
        apply_node_result(run, _loss())
        assert run.hearts == expected_hearts
    assert run.status == RunStatus.DEFEAT
    assert len(run.battle_log) == 4


def test_save_load_roundtrip_with_real_battle(tmp_path):
    """A run carrying a real BattleResult round-trips unchanged (V.36) — Continue
    after load resumes the same state."""
    run = new_run(5, champion_offer(5)[0])
    team = list(CHAMPION_ROSTER.values())[:3]
    enemies = list(ENEMY_ROSTER.values())[:3]
    result = resolve_combat(team, enemies, WeatherState.CLEAR, node_id="n1-Lisbon")
    run.battle_log.append(result)
    run.amber = 17
    run.advance_to_next_node  # noqa: B018 — (no call; just keep node-1 current)

    path = tmp_path / f"{run.run_id}.json"
    save_run(run, path)
    loaded = load_run(path)

    assert loaded.run_id == run.run_id
    assert loaded.current_node_index == run.current_node_index
    assert loaded.status == run.status
    assert loaded.amber == run.amber
    assert len(loaded.battle_log) == 1
    assert loaded.battle_log[0].outcome == result.outcome
    assert loaded.battle_log[0].node_id == result.node_id
