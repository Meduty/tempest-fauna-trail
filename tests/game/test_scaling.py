"""Tests for src/game/scaling.py (T18)."""
import math

import pytest

from src.game.scaling import (
    LEVEL_STEP,
    SCALABLE_STATS,
    TIER_STEP,
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

    def test_l2_multiplies_by_level_step(self):
        assert power(1, 2) == pytest.approx(3.375)

    def test_l3_multiplies_by_level_step_sq(self):
        assert power(1, 3) == pytest.approx(11.390625)

    def test_t10_l3_approx_2715x(self):
        # Spread T1L1 → T10L3 = 3.375**6.5 = 1.5**19.5 ≈ 2715
        assert power(10, 3) == pytest.approx(1.5**19.5, rel=1e-6)

    def test_two_tiers_equal_one_level(self):
        """P(T+2, L) == P(T, L+1) for all valid T and L."""
        for t in range(1, 9):          # T+2 ≤ 10
            for l in range(1, 3):      # L+1 ≤ 3
                assert power(t + 2, l) == pytest.approx(power(t, l + 1)), (
                    f"Failed at T={t}, L={l}"
                )

    def test_monotone_in_tier(self):
        for t in range(1, 10):
            assert power(t, 1) < power(t + 1, 1), f"Not monotone at T={t}"

    def test_monotone_in_level(self):
        for l in range(1, 3):
            assert power(1, l) < power(1, l + 1), f"Not monotone at L={l}"

    def test_tier_step_constant(self):
        """Each tier increments P by TIER_STEP (= sqrt(LEVEL_STEP) = 1.5**1.5)."""
        for t in range(1, 10):
            ratio = power(t + 1, 1) / power(t, 1)
            assert ratio == pytest.approx(TIER_STEP, rel=1e-9)

    def test_level_step_constant(self):
        """Each level increments P by LEVEL_STEP (1.5**3 = 3.375)."""
        for l in range(1, 3):
            ratio = power(1, l + 1) / power(1, l)
            assert ratio == pytest.approx(LEVEL_STEP, rel=1e-9)

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

    def test_t10_l3_approx_52x_base(self):
        # scale_stat(100, 10, 3) ≈ round(100 * sqrt(1.5**19.5)) ≈ 5211
        result = scale_stat(100, 10, 3)
        assert 5200 <= result <= 5220


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
