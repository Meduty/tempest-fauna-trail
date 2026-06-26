"""T.22 — Amber economy, Tempest team-cap progression, and champion shop.

Covers the t22 plan §6 test plan: cost curve, 3-copy leveling, interest banks,
deterministic win bonus, Tempest monotonicity + threshold cascade + cap,
all-or-nothing Amber rush, and deterministic shop rolls + reroll.
"""
from __future__ import annotations

import pytest

from src.game import economy, shop
from src.game.models import NodeState, Run, RunStatus
from src.game.route import build_route


def _run(*, seed: int = 42, amber: int = 0, node_index: int = 1) -> Run:
    route = build_route()
    for node in route:
        node.state = NodeState.CURRENT if node.index == node_index else NodeState.UPCOMING
    return Run(
        run_id="run_t22",
        schema_version=1,
        seed=seed,
        status=RunStatus.IN_PROGRESS,
        roster=[],
        bench=[],
        route=route,
        current_node_index=node_index,
        amber=amber,
    )


# ---------------------------------------------------------------------------
# Cost curve & sell value (§D.13, T.18 §5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tier", range(1, 10))
def test_champion_cost_is_linear(tier: int) -> None:
    assert economy.champion_cost(tier) == tier  # Cost(T) = T


@pytest.mark.parametrize(
    ("tier", "copies", "expected"),
    [(1, 1, 0), (2, 1, 1), (3, 1, 1), (4, 1, 2), (3, 3, 4), (5, 9, 22)],
)
def test_sell_value_floor_cost_over_two(tier: int, copies: int, expected: int) -> None:
    assert economy.sell_value(tier, copies) == expected


# ---------------------------------------------------------------------------
# Leveling — 3 copies → L2, 9 copies → L3
# ---------------------------------------------------------------------------


def test_level_from_copies_thresholds() -> None:
    assert [economy.level_from_copies(c) for c in (1, 2)] == [1, 1]
    assert [economy.level_from_copies(c) for c in (3, 4, 8)] == [2, 2, 2]
    assert [economy.level_from_copies(c) for c in (9, 12)] == [3, 3]


def test_buy_champion_levels_up_on_three_and_nine_copies() -> None:
    run = _run(amber=50)
    cid = "champ_dawnwisp"  # tier 1, cost 1

    assert economy.buy_champion(run, cid) is True
    assert run.champion_copies[cid] == 1
    assert run.roster[0].id == cid and run.roster[0].level == 1
    assert run.amber == 49

    # Two more copies → 3 total → level 2 (one materialized unit, ids unique).
    economy.buy_champion(run, cid)
    economy.buy_champion(run, cid)
    assert run.champion_copies[cid] == 3
    assert len(run.roster) == 1 and run.roster[0].level == 2

    # Up to 9 copies → level 3.
    for _ in range(6):
        economy.buy_champion(run, cid)
    assert run.champion_copies[cid] == 9
    assert run.roster[0].level == 3


def test_buy_champion_blocked_when_maxed_no_amber_waste() -> None:
    run = _run(amber=50)
    cid = "champ_dawnwisp"  # tier 1
    for _ in range(9):  # 9 copies → L3 (maxed)
        assert economy.buy_champion(run, cid) is True
    assert run.champion_copies[cid] == 9
    amber_at_max = run.amber
    # 10th buy must be refused — no Amber spent, copies unchanged.
    assert economy.buy_champion(run, cid) is False
    assert run.amber == amber_at_max
    assert run.champion_copies[cid] == 9


def test_buy_champion_rejects_unaffordable_and_primordial() -> None:
    run = _run(amber=0)
    assert economy.buy_champion(run, "champ_dawnwisp") is False  # cost 1 > 0 amber
    run.amber = 100
    assert economy.buy_champion(run, "champ_aurion") is False  # tier-10 boss-only
    assert economy.buy_champion(run, "champ_unknown") is False


def test_sell_champion_refunds_and_removes() -> None:
    run = _run(amber=10)
    economy.buy_champion(run, "champ_dawnwisp")  # tier1, amber 9
    economy.buy_champion(run, "champ_dawnwisp")
    economy.buy_champion(run, "champ_dawnwisp")  # 3 copies, amber 7
    assert economy.sell_champion(run, "champ_dawnwisp") is True
    assert run.amber == 7 + economy.sell_value(1, 3)  # +1
    assert "champ_dawnwisp" not in run.champion_copies
    assert run.roster == []
    assert economy.sell_champion(run, "champ_dawnwisp") is False  # already gone


# ---------------------------------------------------------------------------
# Interest & income (§D.13 + interest amendment)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("amber", "expected"),
    [(0, 0), (9, 0), (10, 1), (35, 3), (50, 5), (60, 5), (123, 5)],
)
def test_interest_banks_with_cap(amber: int, expected: int) -> None:
    assert economy.interest(amber) == expected


def test_win_bonus_deterministic_and_in_range() -> None:
    for node_index in range(1, 20):
        bonus = economy.win_bonus(123, node_index)
        assert economy.WIN_BONUS_MIN <= bonus <= economy.WIN_BONUS_MAX
        assert bonus == economy.win_bonus(123, node_index)  # repeatable


def test_node_income_composes_base_interest_winbonus() -> None:
    assert economy.node_income(0, won=False, run_seed=1, node_index=1) == 3
    assert economy.node_income(10, won=False, run_seed=1, node_index=1) == 4  # +interest 1
    won = economy.node_income(10, won=True, run_seed=1, node_index=1)
    assert 3 + 1 + economy.WIN_BONUS_MIN <= won <= 3 + 1 + economy.WIN_BONUS_MAX


def test_apply_node_income_uses_amber_before_grant() -> None:
    run = _run(amber=10)
    granted = economy.apply_node_income(run, won=False, node_index=5)
    assert granted == 4  # base 3 + interest on the pre-income 10
    assert run.amber == 14


# ---------------------------------------------------------------------------
# Tempest — monotonic, threshold cascade, cap, pacing (§D.14)
# ---------------------------------------------------------------------------


def test_tempest_starts_rank_one() -> None:
    run = _run()
    assert run.tempest_rank == economy.START_RANK == 1


def test_tempest_early_ramp_rank_three_in_three_fights() -> None:
    run = _run()
    economy.grant_fight_tempest(run)  # +2 → rank 2 (thr 2)
    assert run.tempest_rank == 2
    economy.grant_fight_tempest(run)  # +2 (thr 4 → 1 fight short)
    economy.grant_fight_tempest(run)  # +2 → rank 3 after 3 fights total
    assert run.tempest_rank == 3


def test_tempest_monotonic_non_decreasing() -> None:
    run = _run()
    ranks = []
    for _ in range(60):
        economy.grant_fight_tempest(run)
        ranks.append(run.tempest_rank)
    assert ranks == sorted(ranks)


def test_tempest_free_play_tops_around_rank_seven_to_eight() -> None:
    # 38 combat nodes of free +2 alone.
    free_only = _run()
    for _ in range(38):
        economy.grant_fight_tempest(free_only)
    assert free_only.tempest_rank == 7  # 76 Tempest < 78 to reach rank 8

    # + 6 challenge bonuses (+1 each) tips it to rank 8.
    with_bonus = _run()
    for _ in range(38):
        economy.grant_fight_tempest(with_bonus)
    for _ in range(6):
        economy.grant_tempest(with_bonus, 1)
    assert with_bonus.tempest_rank == 8


def test_tempest_caps_at_rank_ten() -> None:
    run = _run()
    economy.grant_tempest(run, 10_000)
    assert run.tempest_rank == economy.MAX_RANK == 10
    economy.grant_tempest(run, 10_000)  # further grants never exceed the cap
    assert run.tempest_rank == 10


# ---------------------------------------------------------------------------
# Amber rush — all-or-nothing (§D.14)
# ---------------------------------------------------------------------------


def test_rank_up_cost_is_full_remaining() -> None:
    assert economy.rank_up_cost_amber(0, 1) == 2  # thr(1)=2
    assert economy.rank_up_cost_amber(1, 1) == 1  # remaining only
    assert economy.rank_up_cost_amber(0, 10) == 0  # max rank, no rank-up


def test_amber_rush_all_or_nothing() -> None:
    poor = _run(amber=1)
    assert economy.try_rank_up_with_amber(poor) is False  # cost 2 > 1, no partial
    assert poor.tempest_rank == 1 and poor.amber == 1

    rich = _run(amber=2)
    assert economy.try_rank_up_with_amber(rich) is True
    assert rich.tempest_rank == 2 and rich.amber == 0


def test_amber_rush_pays_only_the_gap() -> None:
    run = _run(amber=5)
    economy.grant_tempest(run, 1)  # 1 Tempest banked toward rank 2 (thr 2)
    assert economy.try_rank_up_with_amber(run) is True
    assert run.amber == 4  # paid the 1-point gap, not the full threshold
    assert run.tempest_rank == 2


def test_amber_rush_blocked_at_max_rank() -> None:
    run = _run(amber=999)
    economy.grant_tempest(run, 10_000)
    assert run.tempest_rank == 10
    assert economy.try_rank_up_with_amber(run) is False
    assert run.amber == 999


# ---------------------------------------------------------------------------
# Shop — deterministic rolls, stage gating, reroll (§D.15)
# ---------------------------------------------------------------------------


def _tiers(offers: list[str | None]) -> list[int]:
    from src.game.content import CHAMPION_DEF_BY_ID

    return [CHAMPION_DEF_BY_ID[cid].tier for cid in offers if cid is not None]


def test_roll_shop_is_deterministic() -> None:
    a = shop.roll_shop(777, 4, 3)
    b = shop.roll_shop(777, 4, 3)
    assert a == b
    assert len(a) == shop.SHOP_SLOTS


def test_roll_shop_rank_one_only_tiers_one_and_two() -> None:
    for visit in range(1, 30):
        assert set(_tiers(shop.roll_shop(7, visit, 1))) <= {1, 2}


def test_roll_shop_max_rank_can_reach_high_tiers() -> None:
    seen: set[int] = set()
    for visit in range(1, 200):
        seen.update(_tiers(shop.roll_shop(11, visit, 10)))
    assert max(seen) >= 8  # high-tier band is reachable at max rank
    assert 10 not in seen  # T10 Primordials never appear


def test_roll_shop_rank_gates_tier_ceiling() -> None:
    # The tier band lifts monotonically with rank — higher ranks unlock higher
    # tiers (pure rank-gating, no stage input).
    for rank in range(1, 11):
        ceiling = max(shop.RANK_TIER_WEIGHTS[rank])
        seen: set[int] = set()
        for visit in range(1, 60):
            seen.update(_tiers(shop.roll_shop(rank * 13, visit, rank)))
        assert max(seen) <= ceiling


def test_reroll_changes_offers_deterministically() -> None:
    base = shop.roll_shop(99, 5, 4, reroll_count=0)
    rerolled = shop.roll_shop(99, 5, 4, reroll_count=1)
    assert rerolled != base
    assert rerolled == shop.roll_shop(99, 5, 4, reroll_count=1)  # repeatable


def test_refresh_shop_populates_and_resets_rerolls() -> None:
    run = _run(node_index=1)
    run.shop_rerolls = 3
    shop.refresh_shop(run)
    assert len(run.shop_offers) == shop.SHOP_SLOTS
    assert run.shop_rerolls == 0
    assert set(_tiers(run.shop_offers)) <= {1, 2}  # rank 1 (default Tempest rank)


def test_first_reroll_free_then_costs_one_amber() -> None:
    run = _run(node_index=1, amber=5)
    shop.refresh_shop(run)
    assert shop.reroll_shop(run) is True  # first reroll free
    assert run.amber == 5 and run.shop_rerolls == 1
    assert shop.reroll_shop(run) is True  # second costs 1
    assert run.amber == 4 and run.shop_rerolls == 2


# --- shop freeze (V.75) ----------------------------------------------------
def test_freeze_slot_survives_reroll() -> None:
    run = _run(node_index=1, amber=99)
    shop.refresh_shop(run)
    kept = run.shop_offers[2]
    assert shop.toggle_shop_freeze(run, 2) is True
    assert run.shop_frozen[2] is True
    shop.reroll_shop(run)
    assert run.shop_offers[2] == kept  # frozen slot untouched by reroll
    assert run.shop_frozen[2] is True


def test_freeze_persists_across_refresh_node_entry() -> None:
    run = _run(node_index=1, amber=99)
    shop.refresh_shop(run)
    kept = run.shop_offers[0]
    shop.toggle_shop_freeze(run, 0)
    run.current_node_index = 2          # simulate advancing to the next node's Prep
    shop.refresh_shop(run)              # per-entry auto-refresh
    assert run.shop_offers[0] == kept   # frozen card carried across Prep phases
    assert run.shop_frozen[0] is True


def test_buy_clears_freeze_on_slot() -> None:
    run = _run(node_index=1, amber=99)
    shop.refresh_shop(run)
    shop.toggle_shop_freeze(run, 1)
    assert shop.buy_from_shop(run, 1) is True
    assert run.shop_offers[1] is None
    assert run.shop_frozen[1] is False  # bought slot unfrozen


def test_cannot_freeze_empty_slot() -> None:
    run = _run(node_index=1, amber=99)
    shop.refresh_shop(run)
    assert shop.buy_from_shop(run, 0) is True  # slot 0 now None
    assert shop.toggle_shop_freeze(run, 0) is False
    assert run.shop_frozen[0] is False


def test_unfreeze_toggles_back() -> None:
    run = _run(node_index=1, amber=99)
    shop.refresh_shop(run)
    assert shop.toggle_shop_freeze(run, 3) is True
    assert shop.toggle_shop_freeze(run, 3) is False  # toggles off
    assert run.shop_frozen[3] is False


def test_reroll_blocked_when_unaffordable() -> None:
    run = _run(node_index=1, amber=0)
    shop.refresh_shop(run)
    assert shop.reroll_shop(run) is True  # first is free even at 0 amber
    assert shop.reroll_shop(run) is False  # second needs 1 amber
    assert run.shop_rerolls == 1


def test_generate_supply_offer_deterministic_and_rank_scaled() -> None:
    a = shop.generate_supply_offer(55, 6, 1)
    assert a == shop.generate_supply_offer(55, 6, 1)  # deterministic
    assert len(a) == shop.SUPPLY_SLOTS
    assert set(_tiers(a)) <= {1, 2}  # rank 1 tier-scaled


def test_take_supply_champion_is_free_recruit() -> None:
    run = _run(amber=0)
    offer = shop.generate_supply_offer(55, 6, 1)
    assert shop.take_supply_champion(run, offer[0]) is True
    assert run.amber == 0  # free, no Amber charged
    assert offer[0] in run.champion_copies
    assert any(c.id == offer[0] for c in run.roster)
    assert shop.take_supply_champion(run, "champ_aurion") is False  # T10 boss-only


def test_buy_from_shop_consumes_slot() -> None:
    run = _run(node_index=1, amber=20)
    shop.refresh_shop(run)
    bought_id = run.shop_offers[0]
    assert bought_id is not None
    assert shop.buy_from_shop(run, 0) is True
    assert run.shop_offers[0] is None
    assert bought_id in run.champion_copies
    assert shop.buy_from_shop(run, 0) is False  # empty slot
    assert shop.buy_from_shop(run, 99) is False  # out of range
