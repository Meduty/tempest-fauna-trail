"""Tests for encounter generation (T19)."""
from __future__ import annotations

from random import Random

import pytest

from src.game.encounter import (
    BUDGET_TOLERANCE,
    CH_ENEMIES,
    CH_SHOP,
    CONTENT_VERSION,
    DEFAULT_DC,
    LEVEL_WEIGHTS,
    MAX_REROLLS,
    PREFERRED_TIERS,
    STAGE_BASE,
    STAGE_MAX_SQUAD,
    augment_seed,
    dc_name,
    derive_seed,
    filter_pool,
    generate_fight,
    generate_reward,
    next_dc,
    roll_squad,
    shop_seed,
    supply_seed,
)
from src.game.models import Enemy, WeatherState
from src.game.route import STAGES, stage_of
from src.game.scaling import power


class TestDeriveSeed:
    """Seed derivation must be deterministic and isolating."""

    def test_deterministic(self):
        assert derive_seed(42, 5, CH_ENEMIES) == derive_seed(42, 5, CH_ENEMIES)

    def test_different_nodes_differ(self):
        assert derive_seed(42, 5, CH_ENEMIES) != derive_seed(42, 6, CH_ENEMIES)

    def test_different_channels_differ(self):
        assert derive_seed(42, 5, 0) != derive_seed(42, 5, 1)

    def test_different_seeds_differ(self):
        assert derive_seed(1, 5, 0) != derive_seed(2, 5, 0)

    def test_fits_32_bits(self):
        result = derive_seed(2**31, 999, 6)
        assert 0 <= result < 2**32


class TestFilterPool:
    """Pool filtering respects tier/faction constraints."""

    def test_no_t10_enemies(self):
        for _stage in STAGES:
            pool = filter_pool()
            assert all(d.tier != 10 for d in pool), "T10 should be excluded"

    def test_faction_filter(self):
        pool = filter_pool(faction="human")
        assert all("human" in d.tags for d in pool)

    def test_tier_range_filter(self):
        pool = filter_pool(tier_range=(3, 5))
        assert all(3 <= d.tier <= 5 for d in pool)

    def test_full_pool_not_empty(self):
        for _stage in STAGES:
            pool = filter_pool()
            assert len(pool) > 0


class TestRollSquad:
    """Squad generation respects budget, composition, and determinism."""

    def test_deterministic(self):
        pool = filter_pool()
        rng1 = Random(derive_seed(42, 1, CH_ENEMIES))
        rng2 = Random(derive_seed(42, 1, CH_ENEMIES))
        s1 = roll_squad(rng1, 5.0, pool, stage_index=1)
        s2 = roll_squad(rng2, 5.0, pool, stage_index=1)
        assert [(e.id, e.tier, e.level) for e in s1] == [(e.id, e.tier, e.level) for e in s2]

    def test_respects_min_count(self):
        pool = filter_pool()
        rng = Random(1)
        squad = roll_squad(rng, 0.1, pool, min_count=2, stage_index=1)
        assert len(squad) >= 2

    def test_respects_max_count(self):
        pool = filter_pool()
        rng = Random(1)
        squad = roll_squad(rng, 999.0, pool, max_count=5, stage_index=6)
        assert len(squad) <= 5

    def test_max_dupes(self):
        pool = filter_pool()
        rng = Random(42)
        squad = roll_squad(rng, 10.0, pool, max_dupes=2, stage_index=1)
        from collections import Counter
        counts = Counter(e.id for e in squad)
        assert all(c <= 2 for c in counts.values()), f"Dupe violation: {counts}"

    def test_invalid_min_max_count_raises(self):
        with pytest.raises(ValueError, match="min_count <= max_count"):
            roll_squad(Random(1), 5.0, filter_pool(), min_count=3, max_count=2, stage_index=1)

    def test_impossible_duplicate_cap_raises(self):
        single_enemy_pool = filter_pool(tier_range=(1, 1))[:1]
        with pytest.raises(ValueError, match="cannot satisfy min_count"):
            roll_squad(Random(1), 0.1, single_enemy_pool, min_count=2, max_count=2, max_dupes=1, stage_index=1)

    def test_empty_pool_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            roll_squad(Random(1), 5.0, [], stage_index=1)

    def test_budget_adherence(self):
        """Total squad power should be roughly within budget."""
        for seed in range(10):
            pool = filter_pool()
            rng = Random(derive_seed(seed, 15, CH_ENEMIES))
            budget = 18.0
            squad = roll_squad(rng, budget, pool, stage_index=3)
            total_p = sum(power(e.tier, e.level) for e in squad)
            # Allow budget + tolerance + minimum squad padding
            assert total_p <= budget * 2.0, f"Squad P={total_p:.1f} far exceeds budget={budget}"


class TestGenerateFight:
    """Fight generation end-to-end tests."""

    def test_deterministic(self):
        s1 = generate_fight(42, 4, STAGES[0])
        s2 = generate_fight(42, 4, STAGES[0])
        assert [(e.id, e.tier, e.level) for e in s1] == [(e.id, e.tier, e.level) for e in s2]

    def test_different_nodes_produce_different_squads(self):
        s1 = generate_fight(42, 4, STAGES[0])
        s2 = generate_fight(42, 5, STAGES[0])
        # Very unlikely to be identical
        ids1 = [(e.id, e.tier, e.level) for e in s1]
        ids2 = [(e.id, e.tier, e.level) for e in s2]
        assert ids1 != ids2

    def test_respects_stage_max_squad(self):
        for stage in STAGES:
            squad = generate_fight(42, stage.index * 8, stage)
            assert len(squad) <= STAGE_MAX_SQUAD[stage.index]

    def test_no_t10_enemies_in_fight(self):
        for seed in range(20):
            for stage in STAGES:
                squad = generate_fight(seed, stage.index * 8, stage)
                assert all(e.tier != 10 for e in squad)

    def test_dc_increases_budget(self):
        """Higher DC should tend to produce more/stronger enemies."""
        squads_dc1 = [generate_fight(s, 30, STAGES[3]) for s in range(10)]
        squads_dc2 = [generate_fight(s, 30, STAGES[3], dc=2.0) for s in range(10)]
        avg_p_dc1 = sum(sum(power(e.tier, e.level) for e in sq) for sq in squads_dc1) / 10
        avg_p_dc2 = sum(sum(power(e.tier, e.level) for e in sq) for sq in squads_dc2) / 10
        assert avg_p_dc2 > avg_p_dc1


class TestGenerateReward:
    """Reward nodes have half budget."""

    def test_reward_weaker_than_fight(self):
        """Reward squads should generally be weaker than fight squads."""
        fight_powers = []
        reward_powers = []
        for seed in range(20):
            fs = generate_fight(seed, 15, STAGES[1])
            rs = generate_reward(seed, 15, STAGES[1])
            fight_powers.append(sum(power(e.tier, e.level) for e in fs))
            reward_powers.append(sum(power(e.tier, e.level) for e in rs))
        assert sum(reward_powers) < sum(fight_powers)

    def test_deterministic(self):
        s1 = generate_reward(42, 12, STAGES[1])
        s2 = generate_reward(42, 12, STAGES[1])
        assert [(e.id, e.tier, e.level) for e in s1] == [(e.id, e.tier, e.level) for e in s2]


class TestSeedHelpers:
    """Seed channel helpers return consistent, isolated values."""

    def test_augment_seed_deterministic(self):
        assert augment_seed(42, 5) == augment_seed(42, 5)

    def test_augment_reroll_differs(self):
        assert augment_seed(42, 5, rerolled=False) != augment_seed(42, 5, rerolled=True)

    def test_supply_seed_deterministic(self):
        assert supply_seed(42, 5) == supply_seed(42, 5)

    def test_shop_seed_deterministic(self):
        assert shop_seed(42, 1) == shop_seed(42, 1)

    def test_shop_seed_varies_by_visit(self):
        assert shop_seed(42, 1) != shop_seed(42, 2)


class TestDifficultyCoefficient:
    """DC scaling utilities."""

    def test_default_dc(self):
        assert DEFAULT_DC == 1.0

    def test_next_dc(self):
        assert next_dc(1.0) == pytest.approx(1.1, abs=0.001)
        assert next_dc(1.1) == pytest.approx(1.21, abs=0.001)

    def test_dc_name(self):
        assert dc_name(1.0) == "DC +0"
        assert dc_name(1.1) == "DC +1"


class TestLevelDistribution:
    """Enemies get appropriate levels by stage."""

    def test_stage1_all_l1(self):
        """Stage 1 should produce only L1 enemies."""
        for seed in range(10):
            squad = generate_fight(seed, 3, STAGES[0])
            assert all(e.level == 1 for e in squad), f"Stage 1 produced non-L1: {[(e.name, e.level) for e in squad]}"

    def test_late_stages_have_higher_levels(self):
        """Stages 4-6 should occasionally produce L2+ enemies."""
        l2_plus_count = 0
        for seed in range(50):
            squad = generate_fight(seed, 44, STAGES[5])
            l2_plus_count += sum(1 for e in squad if e.level >= 2)
        assert l2_plus_count > 0, "Stage 6 never produced L2+ enemies"


class TestContentVersion:
    """Content version constant exists."""

    def test_content_version_defined(self):
        assert isinstance(CONTENT_VERSION, str)
        assert len(CONTENT_VERSION) > 0


# ---------------------------------------------------------------------------
# node_encounter — per-node dispatch (T.11)
# ---------------------------------------------------------------------------

class TestNodeEncounter:
    def _route(self):
        from src.game.route import build_route
        return build_route()

    def test_fight_node_matches_generate_fight(self) -> None:
        from src.game.encounter import node_encounter
        from src.game.models import NodeType
        from src.game.route import stage_of

        route = self._route()
        node = next(n for n in route if n.node_type is NodeType.FIGHT)
        enc = node_encounter(0, node, weather=node.weather)
        expected = generate_fight(0, node.index, stage_of(node.index))
        assert [e.id for e in enc.enemies] == [e.id for e in expected]
        assert enc.map_effect_id == ""

    def test_deterministic_same_seed(self) -> None:
        from src.game.encounter import node_encounter
        route = self._route()
        node = route[0]
        a = node_encounter(99, node, weather=node.weather)
        b = node_encounter(99, node, weather=node.weather)
        assert [e.id for e in a.enemies] == [e.id for e in b.enemies]

    def test_no_fight_nodes_empty(self) -> None:
        from src.game.encounter import node_encounter
        from src.game.models import NodeType

        route = self._route()
        for ntype in (NodeType.AUGMENT, NodeType.SUPPLY):
            matches = [n for n in route if n.node_type is ntype]
            for node in matches:
                enc = node_encounter(0, node)
                assert enc.enemies == []
                assert enc.map_effect_id == ""

    def test_boss_node_carries_map_effect(self) -> None:
        from src.game.encounter import generate_boss_encounter, node_encounter
        from src.game.models import NodeType
        from src.game.route import stage_of

        route = self._route()
        boss = next((n for n in route if n.node_type is NodeType.BOSS_FIGHT), None)
        assert boss is not None
        enc = node_encounter(0, boss)
        expected = generate_boss_encounter(0, boss.index, stage_of(boss.index))
        assert enc.map_effect_id == expected.map_effect_id
        assert len(enc.enemies) == len(expected.all_enemies)
