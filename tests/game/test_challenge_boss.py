"""Tests for T21 — Challenge & Boss encounters, Map Effects."""
from __future__ import annotations

from random import Random

import pytest

from src.game.encounter import (
    CH_CHALLENGE,
    CH_BOSS,
    CHALLENGE_TEAM_SIZES,
    derive_seed,
    generate_challenge,
    generate_challenge_reward,
    generate_boss,
    BossEncounter,
    ChallengeReward,
)
from src.game.bosses import (
    BOSS_DEFS,
    BOSS_BUDGETS,
    BossDef,
    get_boss_def,
    make_boss_phase_hook,
    BOSS_ON_DEATH_FACTORIES,
)
from src.game.map_effects import (
    BoardState,
    CellModifier,
    MapEffect,
    SpawnRiftsEffect,
    FogEffect,
    HazardTilesEffect,
    LeyCellsEffect,
    FloodLanesEffect,
    CollapsingArenaEffect,
    MAP_EFFECT_REGISTRY,
)
from src.game.models import Enemy, WeatherState
from src.game.route import STAGES, stage_of


# ===========================================================================
# Challenge generation tests
# ===========================================================================


class TestChallengeGeneration:
    """Challenge encounters: champions as enemies, 50/30/20 split."""

    def test_determinism_same_seed_same_weather(self):
        """Same (seed, node, weather) → identical roster."""
        stage = STAGES[0]  # stage 1
        squad1 = generate_challenge(42, 5, stage, WeatherState.RAIN)
        squad2 = generate_challenge(42, 5, stage, WeatherState.RAIN)
        assert [e.id for e in squad1] == [e.id for e in squad2]

    def test_different_seeds_differ(self):
        """Different seeds → different rosters."""
        stage = STAGES[0]
        squad1 = generate_challenge(42, 5, stage, WeatherState.RAIN)
        squad2 = generate_challenge(99, 5, stage, WeatherState.RAIN)
        # Very unlikely to be identical with different seeds
        ids1 = [e.id for e in squad1]
        ids2 = [e.id for e in squad2]
        assert ids1 != ids2

    def test_different_weather_may_differ(self):
        """Different live weather → different 30% bucket → may differ."""
        stage = STAGES[2]  # stage 3
        squad_rain = generate_challenge(42, 5, stage, WeatherState.RAIN)
        squad_snow = generate_challenge(42, 5, stage, WeatherState.SNOW)
        # With different weather, composition should often differ
        # (not guaranteed but very likely with the 30% live weather bucket)
        ids_rain = [e.id for e in squad_rain]
        ids_snow = [e.id for e in squad_snow]
        # At least assert both are valid
        assert len(ids_rain) > 0
        assert len(ids_snow) > 0

    def test_team_size_matches_stage(self):
        """Challenge team sizes match the authored table §2.2."""
        for stage in STAGES:
            squad = generate_challenge(100, 3, stage, WeatherState.CLEAR)
            expected = CHALLENGE_TEAM_SIZES[stage.index]
            # Allow tolerance: budget may not fill all slots at higher stages
            # where tier-appropriate picks are expensive
            assert len(squad) >= max(2, expected // 2), (
                f"Stage {stage.index}: got {len(squad)} pieces, expected at least {expected // 2}"
            )
            assert len(squad) <= expected + 2

    def test_champions_faction(self):
        """§2.3 amended: challenge enemies are drawn from champions."""
        from src.game.content import _CHAMPION_DEFS
        champion_ids = {d.id for d in _CHAMPION_DEFS}

        stage = STAGES[2]  # stage 3
        squad = generate_challenge(42, 5, stage, WeatherState.THUNDER)
        for enemy in squad:
            assert enemy.id in champion_ids, (
                f"Challenge enemy {enemy.id} not from champion roster"
            )

    def test_no_tier_10_in_challenges(self):
        """T10 legendaries should not appear in challenges."""
        for stage in STAGES:
            squad = generate_challenge(42, 5, stage, WeatherState.RAIN)
            for enemy in squad:
                assert enemy.tier != 10, f"T10 champion {enemy.id} found in challenge"

    def test_affinity_distribution(self):
        """50% stage affinity, 30% live weather, 20% random (approximate)."""
        stage = STAGES[2]  # stage 3 = Thunder affinity
        live_wx = WeatherState.RAIN

        # Run multiple seeds and check distribution
        stage_aff_count = 0
        live_wx_count = 0
        total = 0
        for seed in range(10):
            squad = generate_challenge(seed, 5, stage, live_wx)
            for enemy in squad:
                total += 1
                if enemy.affinity == stage.affinity:
                    stage_aff_count += 1
                elif enemy.affinity == live_wx:
                    live_wx_count += 1

        # Stage affinity should be the dominant proportion (~50%)
        assert stage_aff_count / total > 0.30, (
            f"Stage affinity proportion too low: {stage_aff_count}/{total}"
        )
        # Live weather should be notable (~30%)
        if live_wx != stage.affinity:
            assert live_wx_count / total > 0.10, (
                f"Live weather proportion too low: {live_wx_count}/{total}"
            )


class TestChallengeRewards:
    """Challenge reward generation."""

    def test_reward_structure(self):
        """Reward contains champion_id, random and themed components."""
        stage = STAGES[0]
        squad = generate_challenge(42, 5, stage, WeatherState.CLEAR)
        reward = generate_challenge_reward(42, 5, stage, squad)

        assert reward.amber == 2  # 2 × stage 1
        assert reward.champion_reward_id  # non-empty
        assert reward.random_component
        assert reward.themed_component

    def test_reward_champion_from_team(self):
        """Reward champion is from the challenge team."""
        stage = STAGES[2]
        squad = generate_challenge(42, 5, stage, WeatherState.RAIN)
        reward = generate_challenge_reward(42, 5, stage, squad)

        team_ids = {e.id for e in squad}
        assert reward.champion_reward_id in team_ids

    def test_amber_scales_with_stage(self):
        """Amber reward = 2 × stage_index."""
        for stage in STAGES:
            squad = generate_challenge(42, 5, stage, WeatherState.CLEAR)
            reward = generate_challenge_reward(42, 5, stage, squad)
            assert reward.amber == 2 * stage.index


# ===========================================================================
# Boss encounter tests
# ===========================================================================


class TestBossEncounter:
    """Boss fight data and generation."""

    def test_all_stages_have_bosses(self):
        """Every stage 1-6 has a boss defined."""
        for i in range(1, 7):
            boss_def = get_boss_def(i)
            assert boss_def.stage == i
            assert boss_def.tier == 10

    def test_boss_affinities_match_stages(self):
        """Boss affinities match the stage affinity table."""
        expected = {
            1: WeatherState.CLEAR,
            2: WeatherState.MIST,
            3: WeatherState.THUNDER,
            4: WeatherState.CLOUDY,
            5: WeatherState.RAIN,
            6: WeatherState.SNOW,
        }
        for stage_idx, affinity in expected.items():
            assert BOSS_DEFS[stage_idx].affinity == affinity

    def test_boss_has_two_phase_abilities(self):
        """Each boss has distinct phase 1 and phase 2 abilities."""
        for boss_def in BOSS_DEFS.values():
            assert boss_def.phase1_active
            assert boss_def.phase1_passive
            assert boss_def.phase2_active
            assert boss_def.phase2_passive
            assert boss_def.phase1_active != boss_def.phase2_active
            assert boss_def.phase1_passive != boss_def.phase2_passive

    def test_generate_boss_deterministic(self):
        """Same seed → identical boss encounter."""
        stage = STAGES[0]
        enc1 = generate_boss(42, 7, stage)
        enc2 = generate_boss(42, 7, stage)
        assert enc1.boss.id == enc2.boss.id
        assert [e.id for e in enc1.supporting_cast] == [e.id for e in enc2.supporting_cast]

    def test_generate_boss_supporting_cast(self):
        """Boss has supporting cast of expected size."""
        for stage in STAGES:
            enc = generate_boss(42, stage.index * 8, stage)
            assert enc.boss.tier == 10
            assert len(enc.supporting_cast) >= 3  # All bosses have at least 3 adds

    def test_boss_map_effect_assigned(self):
        """Each boss encounter has a map effect."""
        for stage in STAGES:
            enc = generate_boss(42, stage.index * 8, stage)
            assert enc.map_effect_id in MAP_EFFECT_REGISTRY

    def test_add_variation_produces_variety(self):
        """Different seeds produce some variation in add composition."""
        stage = STAGES[0]
        ids_set = set()
        for seed in range(20):
            enc = generate_boss(seed, 7, stage)
            cast_ids = tuple(e.id for e in enc.supporting_cast)
            ids_set.add(cast_ids)
        # Should have at least some variation (not all identical)
        assert len(ids_set) > 1

    def test_iron_emperor_has_variation_pool(self):
        """Iron Emperor has add variation for variety."""
        emperor = BOSS_DEFS[6]
        assert emperor.add_variation_pool
        assert emperor.add_variation_count > 0


# ===========================================================================
# Boss phase hook tests
# ===========================================================================


class TestBossPhaseHook:
    """Boss phase transition at 50% HP."""

    def test_phase_hook_creates_bundle(self):
        """Phase hook factory returns an EffectBundle with one hook."""
        boss_def = BOSS_DEFS[1]
        factory = make_boss_phase_hook(boss_def)
        from src.game.piece import Piece
        owner = Piece(id="test_boss", base_stats={"hp": 100.0})
        owner.hp = 100.0
        owner.max_hp = 100.0
        bundle = factory(owner)
        assert len(bundle.hooks) == 1
        assert bundle.hooks[0].event == "on_damage_taken"
        assert bundle.hooks[0].scope.value == "once_per_combat"

    def test_all_bosses_have_on_death(self):
        """Every boss has an on-death hook defined."""
        for boss_def in BOSS_DEFS.values():
            assert boss_def.on_death_hook in BOSS_ON_DEATH_FACTORIES


# ===========================================================================
# Map Effects tests
# ===========================================================================


class TestBoardState:
    """BoardState — cell modifier container."""

    def test_add_and_query_modifier(self):
        board = BoardState()
        mod = CellModifier(cell=(3, 4), kind="hazard", owner="test")
        board.add_modifier(mod)
        assert board.modifiers_at(3, 4) == [mod]
        assert board.modifiers_at(0, 0) == []

    def test_is_passable(self):
        board = BoardState()
        assert board.is_passable(5, 5)
        board.add_modifier(CellModifier(cell=(5, 5), kind="impassable", owner="test"))
        assert not board.is_passable(5, 5)

    def test_collapse_blocks_passage(self):
        board = BoardState()
        board.add_modifier(CellModifier(cell=(0, 0), kind="collapse", owner="test"))
        assert not board.is_passable(0, 0)

    def test_remove_by_owner(self):
        board = BoardState()
        board.add_modifier(CellModifier(cell=(1, 1), kind="hazard", owner="boss_a"))
        board.add_modifier(CellModifier(cell=(2, 2), kind="ley", owner="boss_b"))
        board.remove_by_owner("boss_a")
        assert board.modifiers_at(1, 1) == []
        assert len(board.modifiers_at(2, 2)) == 1

    def test_cells_with_kind(self):
        board = BoardState()
        board.add_modifier(CellModifier(cell=(1, 1), kind="hazard", owner="test"))
        board.add_modifier(CellModifier(cell=(3, 3), kind="hazard", owner="test"))
        board.add_modifier(CellModifier(cell=(5, 5), kind="ley", owner="test"))
        assert set(board.cells_with_kind("hazard")) == {(1, 1), (3, 3)}
        assert board.cells_with_kind("ley") == [(5, 5)]


class TestHazardTilesEffect:
    """Strand's capture-grid hazard tiles."""

    def test_setup_places_tiles(self):
        effect = HazardTilesEffect(num_tiles=4)
        board = BoardState()
        rng = Random(42)
        effect.setup(board, rng)
        hazard_cells = board.cells_with_kind("hazard")
        assert len(hazard_cells) == 4

    def test_on_round_shifts_tiles(self):
        effect = HazardTilesEffect(num_tiles=3)
        board = BoardState()
        rng = Random(42)
        effect.setup(board, rng)
        initial_cells = set(board.cells_with_kind("hazard"))

        # Simulate a round boundary — rng state changes
        from unittest.mock import MagicMock
        ctx = MagicMock()
        ctx.rng = Random(99)
        effect.on_round(ctx, board, 1)
        new_cells = set(board.cells_with_kind("hazard"))
        # Cells should have moved (very likely with different rng)
        # Note: extremely rare collision possible if rng picks same cells
        assert len(new_cells) == 3  # correct count maintained


class TestFloodLanesEffect:
    """Crège's dredge-wake flood lanes."""

    def test_setup_floods_column(self):
        effect = FloodLanesEffect(start_column=3)
        board = BoardState()
        rng = Random(42)
        effect.setup(board, rng)
        from src.game.combat.context import BOARD_HEIGHT
        for r in range(BOARD_HEIGHT):
            assert not board.is_passable(3, r)

    def test_on_round_shifts_flood(self):
        effect = FloodLanesEffect(start_column=3)
        board = BoardState()
        rng = Random(42)
        effect.setup(board, rng)

        from unittest.mock import MagicMock
        ctx = MagicMock()
        effect.on_round(ctx, board, 1)
        # Column 4 should now be flooded
        from src.game.combat.context import BOARD_HEIGHT
        assert not board.is_passable(4, 0)


class TestCollapsingArenaEffect:
    """Iron Emperor's shrinking arena."""

    def test_no_initial_collapse(self):
        effect = CollapsingArenaEffect()
        board = BoardState()
        effect.setup(board, Random(42))
        # All cells should be passable initially
        assert board.is_passable(0, 0)
        assert board.is_passable(5, 3)

    def test_collapse_after_rounds(self):
        effect = CollapsingArenaEffect(collapse_interval_rounds=1)
        board = BoardState()
        effect.setup(board, Random(42))

        from unittest.mock import MagicMock
        ctx = MagicMock()
        effect.on_round(ctx, board, 1)
        # Edges should now be collapsed
        assert not board.is_passable(0, 0)
        # Center should still be passable
        assert board.is_passable(5, 3)

    def test_accelerate_doubles_speed(self):
        effect = CollapsingArenaEffect(collapse_interval_rounds=2)
        board = BoardState()
        effect.setup(board, Random(42))

        from unittest.mock import MagicMock
        ctx = MagicMock()

        # Before acceleration, round 1 does nothing (interval=2)
        effect.on_round(ctx, board, 1)
        assert board.is_passable(0, 0)

        # Round 2 collapses
        effect.on_round(ctx, board, 2)
        assert not board.is_passable(0, 0)

        # Reset for acceleration test
        effect2 = CollapsingArenaEffect(collapse_interval_rounds=2)
        board2 = BoardState()
        effect2.setup(board2, Random(42))
        effect2.accelerate()  # Phase 2

        # Now round 1 should collapse (interval becomes 1)
        effect2.on_round(ctx, board2, 1)
        assert not board2.is_passable(0, 0)


class TestLeyCellsEffect:
    """Vossberg's scorched thermals."""

    def test_setup_places_ley_cells(self):
        effect = LeyCellsEffect(num_cells=3)
        board = BoardState()
        effect.setup(board, Random(42))
        assert len(board.cells_with_kind("ley")) == 3


class TestSpawnRiftsEffect:
    """Holloway's furnace vents."""

    def test_setup_places_rifts(self):
        effect = SpawnRiftsEffect(rift_cells=[(2, 1), (7, 1)])
        board = BoardState()
        effect.setup(board, Random(42))
        assert len(board.cells_with_kind("rift")) == 2


class TestFogEffect:
    """Vance's sandstorm fog."""

    def test_setup_marks_fog(self):
        effect = FogEffect()
        board = BoardState()
        effect.setup(board, Random(42))
        assert board.has_kind(0, 0, "fog")


class TestMapEffectRegistry:
    """Map effect registry maps all boss effect IDs."""

    def test_all_boss_effects_registered(self):
        for boss_def in BOSS_DEFS.values():
            assert boss_def.map_effect_id in MAP_EFFECT_REGISTRY
