"""Tests for the weather-system impact sim (tools/simulation/weather_impact.py).

Logic-level checks only — the heavy combat sweeps are not run here. We verify the
isolation construction (equal budget, clear-affinity inertness), the side-swap
fold math, and that the deterministic sampling is reproducible.
"""
from __future__ import annotations

import random

import pytest

from src.game.models import CombatOutcome, WeatherState
from src.game.weather_effects import RingRelation, combat_modifier, damage_modifier

from tools.simulation import weather_impact as wi


# ---------------------------------------------------------------------------
# Roster index — one champion per (affinity, tier), all 6 affinities present
# ---------------------------------------------------------------------------


def test_index_covers_every_affinity_and_tier():
    affinities = {a for (a, _t) in wi.CHAMP_BY_AFF_TIER}
    assert affinities == set(WeatherState)  # 5 ring weathers + clear
    for aff in WeatherState:
        tiers = {t for (a, t) in wi.CHAMP_BY_AFF_TIER if a == aff}
        assert tiers == set(wi.ALL_TIERS)


def test_champ_id_unique_per_aff_tier():
    seen = set()
    for (aff, tier), cid in wi.CHAMP_BY_AFF_TIER.items():
        assert wi.champ_id(aff, tier) == cid
        seen.add(cid)
    assert len(seen) == len(wi.CHAMP_BY_AFF_TIER)


# ---------------------------------------------------------------------------
# Clear is the inert isolator in BOTH systems — the whole design rests on this
# ---------------------------------------------------------------------------


def test_clear_is_inert_in_weather_favor():
    # Clear affinity under any weather, and any affinity under clear weather,
    # gets the identity stat modifier (System A off).
    from src.game.weather_effects import IDENTITY
    for w in WeatherState:
        assert combat_modifier(WeatherState.CLEAR, w) is IDENTITY
    for aff in WeatherState:
        assert combat_modifier(aff, WeatherState.CLEAR) is IDENTITY


def test_clear_is_inert_in_affinity_clash():
    # Any matchup touching clear has a 1.0 damage multiplier (System B off).
    for aff in WeatherState:
        assert damage_modifier(WeatherState.CLEAR, aff) == 1.0
        assert damage_modifier(aff, WeatherState.CLEAR) == 1.0


# ---------------------------------------------------------------------------
# Equal-budget construction: both teams draw the same tier multiset
# ---------------------------------------------------------------------------


def test_sample_tiers_distinct_and_in_pool():
    rng = random.Random("seed")
    tiers = wi.sample_tiers(rng, 8)
    assert len(tiers) == 8
    assert len(set(tiers)) == 8
    assert all(t in wi.TIER_POOL for t in tiers)


def test_sampling_is_deterministic():
    a = wi.sample_tiers(random.Random("k"), 6)
    b = wi.sample_tiers(random.Random("k"), 6)
    assert a == b


# ---------------------------------------------------------------------------
# Side-swap fold — cancels the engine's input-order side advantage
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, hp_a, hp_b, outcome):
        self.hp_remaining_a = hp_a
        self.hp_remaining_b = hp_b
        self.outcome = outcome


def test_fold_normal_orientation():
    b = wi._fold(+1, _FakeResult(80, 20, CombatOutcome.WIN))
    assert b.outcome == CombatOutcome.WIN
    assert b.margin == pytest.approx(0.6)


def test_fold_swapped_orientation_reorients_to_player():
    # Player was on side B here: side-A won with hp 80 vs 20, so from the
    # player's view it is a LOSS with margin -0.6.
    b = wi._fold(-1, _FakeResult(80, 20, CombatOutcome.WIN))
    assert b.outcome == CombatOutcome.LOSS
    assert b.margin == pytest.approx(-0.6)


def test_fold_zero_hp_is_zero_margin():
    b = wi._fold(+1, _FakeResult(0, 0, CombatOutcome.DRAW))
    assert b.margin == 0.0


def test_mk_configs_both_sides_adds_swap():
    team = ("x@1",)
    enemy = ("y@1",)
    one = wi._mk_configs(team, enemy, WeatherState.RAIN, both_sides=False)
    assert len(one) == 1 and one[0][0] == +1
    two = wi._mk_configs(team, enemy, WeatherState.RAIN, both_sides=True)
    assert len(two) == 2
    assert two[0][0] == +1 and two[0][1].piece_ids_a == team
    # swap: roles flipped, sign -1
    assert two[1][0] == -1 and two[1][1].piece_ids_a == enemy and two[1][1].piece_ids_b == team


# ---------------------------------------------------------------------------
# CellResult metrics
# ---------------------------------------------------------------------------


def test_cellresult_metrics():
    c = wi.CellResult(wins=3, losses=1, draws=0, margins=[0.5, 0.5, 0.5, -0.5])
    assert c.n == 4
    assert c.win_rate == pytest.approx(0.75)
    assert c.decisive_rate == pytest.approx(1.0)
    assert c.mean_margin == pytest.approx(0.25)


def test_cellresult_empty_is_nan():
    c = wi.CellResult(0, 0, 0, [])
    assert c.win_rate != c.win_rate  # NaN
    assert c.mean_margin != c.mean_margin


# ---------------------------------------------------------------------------
# Ring-relation summary skips NaN (V.16 — absent ≠ 0)
# ---------------------------------------------------------------------------


def test_relation_summary_runs_over_real_cells():
    # mono-X vs mono-Y cells, margin = mean_margin; just ensure no crash and the
    # four ordered relations are emitted.
    cells = {}
    for ax in wi.RING_WEATHERS:
        for ay in wi.RING_WEATHERS:
            cells[(ax, ay)] = wi.CellResult(1, 0, 0, [0.1])
    lines = wi._relation_summary(cells, lambda c: c.mean_margin, wi._mgn)
    assert len(lines) == 4
    assert any(RingRelation.PRIMARY_PREDATOR.value in ln for ln in lines)
