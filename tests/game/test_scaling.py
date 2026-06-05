"""Tests for src/game/scaling.py (T18)."""
import math

import pytest

from src.game.scaling import (
    FLAT_STATS,
    LEVEL_STEP,
    LEVEL_UP_MOD,
    PRIMARY_EXPONENT,
    PRIMARY_SCALABLE_STATS,
    SCALABLE_STATS,
    SECONDARY_EXPONENT,
    SECONDARY_SCALABLE_STATS,
    TIER_STEP,
    TIER_UP_MOD,
    TRIPLINGS,
    level_scale_stats,
    power,
    scale_stat,
    stat_multiplier,
)


# ---------------------------------------------------------------------------
# power()
# ---------------------------------------------------------------------------

class TestPower:
    def test_t1_l1_is_one(self):
        assert power(1, 1) == 1.0

    def test_l2_is_1_tripling(self):
        # L2 = 1 tripling → P = 2^1 = 2
        assert power(1, 2) == pytest.approx(2.0)

    def test_l3_is_3_triplings(self):
        # L3 = 3 triplings → P = 2^3 = 8
        assert power(1, 3) == pytest.approx(8.0)

    def test_t10_l3(self):
        # exponent = (10-1)/3 + 3 = 6 → P = 2^6 = 64
        assert power(10, 3) == pytest.approx(2**6, rel=1e-6)

    def test_tier_step_constant(self):
        """Each tier increments P by TIER_UP_MOD = cbrt(2)."""
        for t in range(1, 10):
            ratio = power(t + 1, 1) / power(t, 1)
            assert ratio == pytest.approx(TIER_UP_MOD, rel=1e-9)

    def test_triplings_drive_levels(self):
        """Power ratio between levels matches 2^(delta_triplings)."""
        # L1→L2: 1 tripling diff → ratio = 2^1
        assert power(1, 2) / power(1, 1) == pytest.approx(2**1, rel=1e-9)
        # L2→L3: 2 triplings diff → ratio = 2^2
        assert power(1, 3) / power(1, 2) == pytest.approx(2**2, rel=1e-9)

    def test_monotone_in_tier(self):
        for t in range(1, 10):
            assert power(t, 1) < power(t + 1, 1), f"Not monotone at T={t}"

    def test_monotone_in_level(self):
        for l in range(1, 3):
            assert power(1, l) < power(1, l + 1), f"Not monotone at L={l}"

    def test_out_of_range_tier_raises(self):
        with pytest.raises(ValueError):
            power(0, 1)
        with pytest.raises(ValueError):
            power(11, 1)

    def test_out_of_range_level_raises(self):
        with pytest.raises(ValueError):
            power(1, 0)
        with pytest.raises(ValueError):
            power(1, 4)


# ---------------------------------------------------------------------------
# stat_multiplier()
# ---------------------------------------------------------------------------

class TestStatMultiplier:
    def test_t1_l1_is_one(self):
        assert stat_multiplier(1, 1) == pytest.approx(1.0)

    def test_equals_sqrt_power(self):
        for t in range(1, 11):
            for l in range(1, 4):
                assert stat_multiplier(t, l) == pytest.approx(
                    math.sqrt(power(t, l)), rel=1e-9
                ), f"Mismatch at T={t} L={l}"

    def test_monotone_in_tier(self):
        for t in range(1, 10):
            assert stat_multiplier(t, 1) < stat_multiplier(t + 1, 1)

    def test_monotone_in_level(self):
        for l in range(1, 3):
            assert stat_multiplier(1, l) < stat_multiplier(1, l + 1)


# ---------------------------------------------------------------------------
# scale_stat()
# ---------------------------------------------------------------------------

class TestScaleStat:
    def test_t1_l1_returns_base(self):
        for base in (100, 50, 200, 1):
            assert scale_stat(base, 1, 1) == base

    def test_returns_int(self):
        result = scale_stat(100, 3, 2)
        assert isinstance(result, int)

    def test_rounding(self):
        # round(base * mult) — verify against direct computation
        base = 73
        for t in range(1, 11):
            for l in range(1, 4):
                expected = round(base * stat_multiplier(t, l))
                assert scale_stat(base, t, l) == expected

    def test_monotone_in_tier(self):
        base = 100
        for t in range(1, 10):
            assert scale_stat(base, t, 1) <= scale_stat(base, t + 1, 1)

    def test_monotone_in_level(self):
        base = 100
        for l in range(1, 3):
            assert scale_stat(base, 1, l) <= scale_stat(base, 1, l + 1)

    def test_t10_l3_approx_8x_base(self):
        # scale_stat(100, 10, 3) ≈ round(100 * sqrt(2**6)) = round(100 * 8) = 800
        result = scale_stat(100, 10, 3)
        assert 795 <= result <= 805


# ---------------------------------------------------------------------------
# SCALABLE_STATS
# ---------------------------------------------------------------------------

class TestScalableStats:
    def test_primary_contains_required_fields(self):
        required = {"max_hp", "strength", "intelligence", "armor", "resistance"}
        assert required == set(PRIMARY_SCALABLE_STATS)

    def test_scalable_stats_is_primary_alias(self):
        # SCALABLE_STATS retained as a deprecated alias of the primary tuple (V.34).
        assert SCALABLE_STATS == PRIMARY_SCALABLE_STATS

    def test_secondary_is_speeds_plus_threat(self):
        assert set(SECONDARY_SCALABLE_STATS) == {
            "attack_speed", "move_speed", "mana_regen", "threat"
        }

    def test_three_classes_disjoint(self):
        p, s, f = (set(PRIMARY_SCALABLE_STATS), set(SECONDARY_SCALABLE_STATS),
                   set(FLAT_STATS))
        assert p & s == set() and p & f == set() and s & f == set()

    def test_classes_cover_base_stats(self):
        # Every _BASE_STATS key is classified exactly once, except the premium
        # ratios crit_chance/penetration/penetration_pct (off the scaling model).
        from src.game.content import _BASE_STATS
        classified = (set(PRIMARY_SCALABLE_STATS) | set(SECONDARY_SCALABLE_STATS)
                      | set(FLAT_STATS))
        premium = {"crit_chance", "penetration", "penetration_pct"}
        assert set(_BASE_STATS) - premium == classified

    def test_secondary_exponent_gentle(self):
        # ≈ +2%/tier, ×1.428 over T1L1→T10L3.
        assert round(stat_multiplier(2, 1, SECONDARY_EXPONENT), 3) == 1.02
        assert round(stat_multiplier(10, 3, SECONDARY_EXPONENT), 2) == 1.43
        # PRIMARY default unchanged (sqrt(power)).
        assert stat_multiplier(5, 2) == stat_multiplier(5, 2, PRIMARY_EXPONENT)

    def test_level_scale_secondary_and_milli_monotone(self):
        s1 = {**{k: 100 for k in SECONDARY_SCALABLE_STATS}, "milli_AS": 100_000,
              "max_hp": 600}
        s3 = dict(s1)
        level_scale_stats(s3, tier=5, level=3)
        assert s3["attack_speed"] > s1["attack_speed"]
        assert s3["milli_AS"] > s1["milli_AS"]
        assert s3["max_hp"] > s1["max_hp"]
