"""`economy.apply_node_result` reward-step orchestrator (T.15a V.69 + T.38 V.70/V.71).

Drives the single game-side reward applier with stub `BattleResult`s (it only
reads `.outcome` + appends to `battle_log`), asserting income/tempest/progression,
node-type rewards, the Hearts survivable-loss model, and determinism. No combat
resolution needed.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.game.economy import (
    AMBER_BASE_INCOME,
    TEMPEST_PER_FIGHT,
    apply_node_result,
    interest,
    node_income,
    recruit_challenge_offer,
)
from src.game.encounter import generate_challenge, generate_reward_loot
from src.game.models import CombatOutcome, NodeState, NodeType, RunStatus
from src.game.route import stage_of
from src.game.run_init import champion_offer, new_run

_SEED = 99


def _run():
    return new_run(_SEED, champion_offer(_SEED)[0])


def _result(outcome):
    return SimpleNamespace(outcome=outcome)


def _set_current(run, idx):
    """Force ``idx`` to be the current node (single CURRENT, rest UPCOMING)."""
    for n in run.route:
        n.state = NodeState.UPCOMING
    node = next(n for n in run.route if n.index == idx)
    node.state = NodeState.CURRENT
    run.current_node_index = idx
    return node


def _node_of_type(run, node_type):
    """First node index of ``node_type`` in the route (route order)."""
    return next(n.index for n in run.route if n.node_type == node_type)


# --------------------------------------------------------------------------- win

def test_win_grants_income_tempest_and_advances():
    run = _run()
    node_index = _node_of_type(run, NodeType.FIGHT)
    _set_current(run, node_index)
    expected_income = node_income(run.amber, True, run.seed, node_index)
    amber_before = run.amber

    summary = apply_node_result(run, _result(CombatOutcome.WIN))

    assert summary.won is True
    assert summary.amber_gained == expected_income
    assert run.amber == amber_before + expected_income
    assert summary.tempest_gained == TEMPEST_PER_FIGHT
    assert len(run.battle_log) == 1
    cleared = next(n for n in run.route if n.index == node_index)
    assert cleared.state == NodeState.CLEARED
    assert run.current_node_index > node_index
    assert run.status == RunStatus.IN_PROGRESS
    assert summary.terminal is False


def test_last_node_win_is_victory():
    run = _run()
    last = max(n.index for n in run.route)
    _set_current(run, last)

    summary = apply_node_result(run, _result(CombatOutcome.WIN))

    assert run.status == RunStatus.VICTORY
    assert summary.terminal is True
    assert summary.status == RunStatus.VICTORY


# ----------------------------------------------------------------- node rewards

def test_reward_node_win_deposits_loot_to_inventory():
    run = _run()
    idx = _node_of_type(run, NodeType.REWARD)
    _set_current(run, idx)
    expected = generate_reward_loot(run.seed, idx).item_ids

    summary = apply_node_result(run, _result(CombatOutcome.WIN))

    assert list(summary.item_ids) == list(expected)
    for item_id in expected:
        assert run.inventory.get(item_id, 0) >= 1


def test_challenge_node_win_grants_amber_components_tempest_and_pending_offer():
    run = _run()
    idx = _node_of_type(run, NodeType.CHALLENGE)
    node = _set_current(run, idx)
    stage = stage_of(idx)
    _squad, reward = generate_challenge(run.seed, idx, stage, node.weather)

    summary = apply_node_result(run, _result(CombatOutcome.WIN))

    # amber bonus + both components + the +1 tempest bonus
    assert summary.bonus_amber == reward.amber == 2 * stage.index
    assert summary.tempest_gained == TEMPEST_PER_FIGHT + reward.tempest_bonus
    assert run.inventory.get(reward.component_offer, 0) >= 1
    assert run.inventory.get(reward.themed_component, 0) >= 1
    # champion_offer is surfaced PENDING, not auto-applied
    assert summary.champion_offer == (reward.champion_offer or None)
    assert summary.champion_offer not in run.champion_copies


# --------------------------------------------------------------- Hearts (loss)

def test_new_run_has_three_hearts():
    assert _run().hearts == 3


def test_nonboss_loss_survives_and_costs_a_heart():
    run = _run()
    idx = _node_of_type(run, NodeType.FIGHT)
    _set_current(run, idx)
    amber_before = run.amber
    expected_income = node_income(amber_before, False, run.seed, idx)

    summary = apply_node_result(run, _result(CombatOutcome.LOSS))

    assert summary.won is False
    assert run.hearts == 2
    assert summary.hearts_remaining == 2
    assert run.status == RunStatus.IN_PROGRESS
    assert summary.terminal is False
    assert run.current_node_index > idx  # advanced (survived)
    # income = base + interest, no win bonus; unique payouts zeroed
    assert summary.amber_gained == expected_income == AMBER_BASE_INCOME + interest(amber_before)
    assert summary.tempest_gained == 0
    assert summary.item_ids == ()
    assert summary.bonus_amber == 0


def test_loss_on_reward_node_grants_no_loot():
    run = _run()
    idx = _node_of_type(run, NodeType.REWARD)
    _set_current(run, idx)
    inv_before = dict(run.inventory)

    summary = apply_node_result(run, _result(CombatOutcome.LOSS))

    assert summary.item_ids == ()
    assert run.inventory == inv_before  # structural zeroing — win-only payouts


def test_loss_to_zero_hearts_defeats():
    run = _run()
    run.hearts = 1
    _set_current(run, _node_of_type(run, NodeType.FIGHT))
    idx = run.current_node_index

    summary = apply_node_result(run, _result(CombatOutcome.LOSS))

    assert run.hearts == 0
    assert run.status == RunStatus.DEFEAT
    assert summary.terminal is True
    assert run.current_node_index == idx  # did not advance


def test_three_losses_from_full_defeat_on_third():
    run = _run()
    _set_current(run, _node_of_type(run, NodeType.FIGHT))
    apply_node_result(run, _result(CombatOutcome.LOSS))
    assert run.status == RunStatus.IN_PROGRESS and run.hearts == 2
    apply_node_result(run, _result(CombatOutcome.LOSS))
    assert run.status == RunStatus.IN_PROGRESS and run.hearts == 1
    summary = apply_node_result(run, _result(CombatOutcome.LOSS))
    assert run.hearts == 0 and run.status == RunStatus.DEFEAT and summary.terminal


def test_draw_costs_a_heart_and_survives():
    run = _run()
    _set_current(run, _node_of_type(run, NodeType.FIGHT))
    summary = apply_node_result(run, _result(CombatOutcome.DRAW))
    assert summary.won is False
    assert run.hearts == 2
    assert run.status == RunStatus.IN_PROGRESS


def test_boss_loss_is_instant_defeat_with_hearts_remaining():
    run = _run()
    _set_current(run, _node_of_type(run, NodeType.BOSS_FIGHT))
    assert run.hearts == 3  # full hearts

    summary = apply_node_result(run, _result(CombatOutcome.LOSS))

    assert run.status == RunStatus.DEFEAT  # hard gate, regardless of Hearts
    assert summary.terminal is True
    assert run.hearts == 2  # still decremented for display


def test_final_node_loss_defeats_not_victory():
    run = _run()
    last = max(n.index for n in run.route)
    final = _set_current(run, last)
    final.node_type = NodeType.FIGHT  # isolate the is-last guard from the boss guard
    assert run.hearts == 3

    summary = apply_node_result(run, _result(CombatOutcome.LOSS))

    assert run.status == RunStatus.DEFEAT  # never relabel a lost final fight as VICTORY
    assert summary.status == RunStatus.DEFEAT
    assert summary.terminal is True


# -------------------------------------------------------------------- recruit

def test_recruit_challenge_offer_adds_unowned_to_bench():
    run = _run()
    offer = next(
        cid for cid in champion_offer(_SEED) if cid not in run.champion_copies
    )
    bench_before = len(run.bench)

    assert recruit_challenge_offer(run, offer) is True
    assert run.champion_copies.get(offer) == 1
    assert len(run.bench) == bench_before + 1
    assert any(c.id == offer for c in run.bench)
    # already owned ⇒ no-op
    assert recruit_challenge_offer(run, offer) is False
    assert len(run.bench) == bench_before + 1


def test_recruit_unknown_id_is_noop():
    run = _run()
    assert recruit_challenge_offer(run, "not_a_real_champion") is False


# ----------------------------------------------------------------- save / det

def test_hearts_round_trip_and_back_compat():
    from src.game.models import Run

    run = _run()
    run.hearts = 2
    assert Run.from_dict(run.to_dict()).hearts == 2
    # pre-T.38 payload (no "hearts" key) → default 3
    payload = run.to_dict()
    del payload["hearts"]
    assert Run.from_dict(payload).hearts == 3


def test_deterministic_income_and_reward():
    """Same seed + same outcome ⇒ identical Amber/tempest/reward (V.2/V.70)."""
    a = _run()
    b = _run()
    sa = apply_node_result(a, _result(CombatOutcome.WIN))
    sb = apply_node_result(b, _result(CombatOutcome.WIN))
    assert (sa.amber_gained, sa.tempest_gained) == (sb.amber_gained, sb.tempest_gained)
    assert sa.item_ids == sb.item_ids and sa.champion_offer == sb.champion_offer
    assert a.amber == b.amber and a.tempest == b.tempest and a.inventory == b.inventory
