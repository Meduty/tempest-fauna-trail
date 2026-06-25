"""T.15a — `economy.apply_node_result` reward-step orchestrator (V.69).

Drives the single game-side reward applier with stub `BattleResult`s (it only
reads `.outcome` + appends to `battle_log`), asserting income/tempest/progression
and determinism. No combat resolution needed.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.game.economy import (
    AMBER_BASE_INCOME,
    TEMPEST_PER_FIGHT,
    apply_node_result,
    interest,
    node_income,
)
from src.game.models import CombatOutcome, NodeState, RunStatus
from src.game.run_init import champion_offer, new_run

_SEED = 99


def _run():
    return new_run(_SEED, champion_offer(_SEED)[0])


def _result(outcome):
    return SimpleNamespace(outcome=outcome)


def test_win_grants_income_tempest_and_advances():
    run = _run()
    node_index = run.current_node_index
    expected_income = node_income(run.amber, True, run.seed, node_index)
    amber_before = run.amber

    summary = apply_node_result(run, _result(CombatOutcome.WIN))

    assert summary.won is True
    assert summary.amber_gained == expected_income
    assert run.amber == amber_before + expected_income
    assert summary.tempest_gained == TEMPEST_PER_FIGHT
    assert len(run.battle_log) == 1
    # Node cleared + advanced; run still in progress, not terminal.
    cleared = next(n for n in run.route if n.index == node_index)
    assert cleared.state == NodeState.CLEARED
    assert run.current_node_index > node_index
    assert run.status == RunStatus.IN_PROGRESS
    assert summary.terminal is False


def test_loss_sets_defeat_without_advancing():
    run = _run()
    node_index = run.current_node_index
    amber_before = run.amber
    expected_income = node_income(amber_before, False, run.seed, node_index)

    summary = apply_node_result(run, _result(CombatOutcome.LOSS))

    assert summary.won is False
    assert summary.tempest_gained == 0
    assert run.status == RunStatus.DEFEAT
    assert summary.terminal is True
    assert run.current_node_index == node_index  # did not advance
    # Income still applied (base + interest, no win bonus).
    assert summary.amber_gained == expected_income
    assert expected_income == AMBER_BASE_INCOME + interest(amber_before)


def test_draw_counts_as_defeat():
    run = _run()
    summary = apply_node_result(run, _result(CombatOutcome.DRAW))
    assert summary.won is False
    assert run.status == RunStatus.DEFEAT
    assert summary.terminal is True


def test_last_node_win_is_victory():
    run = _run()
    last = max(n.index for n in run.route)
    # Jump to the final node as the current node.
    for n in run.route:
        n.state = NodeState.UPCOMING
    final = next(n for n in run.route if n.index == last)
    final.state = NodeState.CURRENT
    run.current_node_index = last

    summary = apply_node_result(run, _result(CombatOutcome.WIN))

    assert run.status == RunStatus.VICTORY
    assert summary.terminal is True
    assert summary.status == RunStatus.VICTORY


def test_deterministic_income(  ):
    """Same seed + same outcome ⇒ identical Amber/tempest (V.2)."""
    a = _run()
    b = _run()
    sa = apply_node_result(a, _result(CombatOutcome.WIN))
    sb = apply_node_result(b, _result(CombatOutcome.WIN))
    assert (sa.amber_gained, sa.tempest_gained) == (sb.amber_gained, sb.tempest_gained)
    assert a.amber == b.amber and a.tempest == b.tempest
