"""Tests for src/game/scaling.py (T18)."""
import math

import pytest

from src.game.scaling import (
    LEVEL_STEP,
    LEVEL_UP_MOD,
    SCALABLE_STATS,
    TIER_STEP,
    TIER_UP_MOD,
    TRIPLINGS,
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
    def test_scalable_contains_required_fields(self):
        required = {"max_hp", "strength", "intelligence", "armor", "resistance"}
        assert required.issubset(set(SCALABLE_STATS))

    def test_flat_stats_not_in_scalable(self):
        flat = {"attack_speed", "mana_regen", "move_speed", "attack_range",
                "threat", "ability_cost"}
        for stat in flat:
            assert stat not in SCALABLE_STATS, (
                f"Flat stat '{stat}' must not be in SCALABLE_STATS"
            )
