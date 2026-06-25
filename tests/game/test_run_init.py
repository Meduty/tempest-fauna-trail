"""Run-start flow (T.10) — offer determinism + new_run invariants (V.2, V.63).

Pure game logic; no Flet. Asserts the seed-deterministic 1-of-3 champion offer
and that ``new_run`` builds a valid in-progress ``Run`` per SPEC §G run-start
conditions (10 Amber, rank 1, node-1 CURRENT, chosen champion at level 1, first
shop populated).
"""

from __future__ import annotations

import pytest

from src.game import run_init
from src.game.content import CHAMPION_DEF_BY_ID
from src.game.models import NodeState, RunStatus


# ---------------------------------------------------------------------------
# Champion offer — determinism + shape (V.2)
# ---------------------------------------------------------------------------


def test_offer_is_three_distinct_tier_1_2_champions():
    offer = run_init.champion_offer(12345)
    assert len(offer) == run_init.OFFER_SIZE == 3
    assert len(set(offer)) == 3
    for cid in offer:
        assert CHAMPION_DEF_BY_ID[cid].tier in run_init.OFFER_TIERS


def test_offer_is_seed_deterministic():
    # Same seed → byte-identical offer; different seed → (generally) differs.
    assert run_init.champion_offer(7) == run_init.champion_offer(7)
    seeds = {tuple(run_init.champion_offer(s)) for s in range(40)}
    assert len(seeds) > 1  # the offer actually varies across seeds


def test_offer_pool_has_enough_champions():
    assert len(run_init._offer_pool()) >= run_init.OFFER_SIZE


# ---------------------------------------------------------------------------
# new_run — invariants (SPEC §G, V.63)
# ---------------------------------------------------------------------------


def test_new_run_starting_conditions():
    seed = 999
    chosen = run_init.champion_offer(seed)[0]
    run = run_init.new_run(seed, chosen)

    assert run.status == RunStatus.IN_PROGRESS
    assert run.seed == seed
    assert run.amber == run_init.STARTING_AMBER == 10
    assert run.tempest_rank == run_init.STARTING_RANK == 1
    assert run.current_node_index == 1

    # Node 1 is the sole CURRENT node; all others UPCOMING.
    current = [n for n in run.route if n.state == NodeState.CURRENT]
    assert len(current) == 1 and current[0].index == 1
    assert run.current_node() is current[0]


def test_new_run_grants_chosen_champion_at_level_1():
    seed = 31337
    chosen = run_init.champion_offer(seed)[1]
    run = run_init.new_run(seed, chosen)

    assert [c.id for c in run.roster] == [chosen]
    assert run.roster[0].level == 1
    assert run.champion_copies[chosen] == 1
    assert run.bench == []


def test_new_run_populates_first_shop():
    run = run_init.new_run(2024, run_init.champion_offer(2024)[2])
    assert len(run.shop_offers) == 5
    assert any(slot is not None for slot in run.shop_offers)
    assert run.shop_rerolls == 0


def test_new_run_is_deterministic():
    seed = 88
    chosen = run_init.champion_offer(seed)[0]
    a = run_init.new_run(seed, chosen)
    b = run_init.new_run(seed, chosen)
    assert a.to_dict() == b.to_dict()


def test_new_run_rejects_unoffered_champion():
    seed = 5
    offer = set(run_init.champion_offer(seed))
    not_offered = next(cid for cid in CHAMPION_DEF_BY_ID if cid not in offer)
    with pytest.raises(ValueError, match="not in the starting offer"):
        run_init.new_run(seed, not_offered)
