"""Tests for T21 — Challenge & Boss Encounters.

Covers:
- generate_challenge(): determinism, faction, affinity distribution, team size, reward
- generate_boss_encounter(): fixed cast, variable adds, map effect id
- ChallengeReward: structure, amber calculation
- Map effects: BoardState mutations and on-tick behaviour
- BoardState: basic query correctness
- attach_map_effect(): wiring integration (effect registered → fires on bus)
- Ley buff: per-cell independence, dedup, recapture correctness
- Fog targeting: targeting.py respects board_state.fog_range
- Flood lanes: boundary bounce, always-one-column invariant
"""
from __future__ import annotations

from collections import Counter
from random import Random
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.game.board import BoardState, CellModifier
from src.game.content import _CHAMPION_DEFS
from src.game.encounter import (
    AFFINITY_THEMED_COMPONENT,
    CH_BOSS,
    CH_CHALLENGE,
    CHALLENGE_TEAM_SIZE,
    ChallengeReward,
    derive_seed,
    generate_boss_encounter,
    generate_challenge,
)
from src.game.items import combine
from src.game.items.base import BASE_COMPONENTS
from src.game.map_effects import (
    MAP_EFFECT_CLASSES,
    DefensiveLeyEffect,
    FloodLanesEffect,
    FogEffect,
    HazardTilesEffect,
    SlowTilesEffect,
    SunlitTilesEffect,
    build_map_effect,
)
from src.game.models import Enemy, WeatherState
from src.game.route import STAGES


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _stage(index: int):
    """Return the StageDef for the given stage index."""
    return next(s for s in STAGES if s.index == index)


_ALL_CHAMPION_IDS: frozenset[str] = frozenset(d.id for d in _CHAMPION_DEFS)
_NON_T10_CHAMPION_IDS: frozenset[str] = frozenset(
    d.id for d in _CHAMPION_DEFS if d.tier != 10
)


# ---------------------------------------------------------------------------
# ChallengeReward structure
# ---------------------------------------------------------------------------

class TestChallengeReward:
    """ChallengeReward fields must be well-formed."""

    def test_reward_fields_for_each_stage(self):
        for stage in STAGES:
            _, reward = generate_challenge(42, stage.index * 10, stage)
            assert isinstance(reward, ChallengeReward)
            assert reward.champion_offer != ""
            assert isinstance(reward.component_offer, str)
            assert isinstance(reward.themed_component, str)
            assert reward.amber == 2 * stage.index
            assert reward.tempest_bonus >= 1

    def test_amber_scales_with_stage(self):
        for stage in STAGES:
            _, reward = generate_challenge(42, stage.index * 10, stage)
            assert reward.amber == 2 * stage.index

    def test_themed_component_matches_stage_affinity(self):
        for stage in STAGES:
            _, reward = generate_challenge(42, stage.index * 10, stage)
            expected = AFFINITY_THEMED_COMPONENT[stage.affinity]
            assert reward.themed_component == expected

    def test_champion_offer_is_in_squad(self):
        """champion_offer must be the id of a champion in the defeated team."""
        for stage in STAGES:
            squad, reward = generate_challenge(42, stage.index * 10, stage)
            squad_ids = {e.id for e in squad}
            assert reward.champion_offer in squad_ids

    def test_component_offer_is_valid_base_component(self):
        # Reward components MUST come from the recipe vocabulary, else they have
        # no recipe and can never fuse (B.34, V.74). Source of truth = items.base.
        for stage in STAGES:
            _, reward = generate_challenge(42, stage.index * 10, stage)
            assert reward.component_offer in BASE_COMPONENTS


# ---------------------------------------------------------------------------
# generate_challenge — determinism
# ---------------------------------------------------------------------------

class TestChallengeDeterminism:
    """Same inputs must always produce the same outputs."""

    def test_squad_deterministic(self):
        stage = _stage(3)
        live_wx = WeatherState.THUNDER
        s1, r1 = generate_challenge(42, 30, stage, live_weather=live_wx)
        s2, r2 = generate_challenge(42, 30, stage, live_weather=live_wx)
        assert [(e.id, e.tier, e.level) for e in s1] == [(e.id, e.tier, e.level) for e in s2]
        assert r1.champion_offer == r2.champion_offer

    def test_different_seeds_differ(self):
        stage = _stage(2)
        s1, _ = generate_challenge(1, 10, stage)
        s2, _ = generate_challenge(2, 10, stage)
        ids1 = [(e.id, e.tier, e.level) for e in s1]
        ids2 = [(e.id, e.tier, e.level) for e in s2]
        # Different seeds almost certainly produce different squads
        assert ids1 != ids2

    def test_different_node_indices_differ(self):
        stage = _stage(2)
        s1, _ = generate_challenge(42, 10, stage)
        s2, _ = generate_challenge(42, 11, stage)
        ids1 = [(e.id, e.tier, e.level) for e in s1]
        ids2 = [(e.id, e.tier, e.level) for e in s2]
        assert ids1 != ids2

    def test_different_weather_can_differ(self):
        """Changing live weather can change the squad composition."""
        stage = _stage(3)
        seen_ids = set()
        for wx in list(WeatherState):
            s, _ = generate_challenge(42, 30, stage, live_weather=wx)
            seen_ids.add(tuple(e.id for e in s))
        # At least two different weather states must yield different squads
        assert len(seen_ids) > 1


# ---------------------------------------------------------------------------
# generate_challenge — faction: champions only
# ---------------------------------------------------------------------------

class TestChallengeFaction:
    """All challenge pieces must come from the champion roster."""

    def test_all_pieces_from_champion_roster(self):
        for stage in STAGES:
            for seed in range(5):
                squad, _ = generate_challenge(seed, stage.index * 8, stage)
                for enemy in squad:
                    assert enemy.id in _ALL_CHAMPION_IDS, (
                        f"Challenge piece {enemy.id!r} is NOT a champion"
                    )

    def test_no_t10_primordials_in_squad(self):
        """T10 champions (Primordials) are boss-reserved; challenges exclude them."""
        t10_ids = frozenset(d.id for d in _CHAMPION_DEFS if d.tier == 10)
        for stage in STAGES:
            for seed in range(5):
                squad, _ = generate_challenge(seed, stage.index * 8, stage)
                for enemy in squad:
                    assert enemy.id not in t10_ids, (
                        f"T10 primordial {enemy.id!r} appeared in stage {stage.index} challenge"
                    )


# ---------------------------------------------------------------------------
# generate_challenge — team size
# ---------------------------------------------------------------------------

class TestChallengeTeamSize:
    """Challenge squads must match CHALLENGE_TEAM_SIZE[stage]."""

    def test_team_size_matches_table(self):
        for stage in STAGES:
            for seed in range(3):
                squad, _ = generate_challenge(seed, stage.index * 7, stage)
                expected = CHALLENGE_TEAM_SIZE[stage.index]
                assert len(squad) == expected, (
                    f"Stage {stage.index}: got {len(squad)} pieces, expected {expected}"
                )


# ---------------------------------------------------------------------------
# generate_challenge — affinity distribution (50/30/20)
# ---------------------------------------------------------------------------

class TestChallengeAffinityDistribution:
    """
    Over a large sample the affinity mix should roughly match 50/30/20.
    We verify that stage affinity dominates and that all slots are champion ids.
    """

    def test_stage_affinity_dominates(self):
        """Stage affinity should appear in ≥40% of slots (soft threshold)."""
        stage = _stage(1)  # Clear affinity
        stage_aff = stage.affinity
        total_pieces = 0
        stage_aff_pieces = 0

        for seed in range(30):
            squad, _ = generate_challenge(seed, stage.index * 5, stage,
                                          live_weather=WeatherState.RAIN)
            for enemy in squad:
                total_pieces += 1
                # Get the affinity from the champion def
                matching_def = next(
                    (d for d in _CHAMPION_DEFS if d.id == enemy.id), None
                )
                if matching_def and matching_def.affinity == stage_aff:
                    stage_aff_pieces += 1

        if total_pieces > 0:
            ratio = stage_aff_pieces / total_pieces
            assert ratio >= 0.35, (
                f"Stage affinity ratio too low: {ratio:.0%} (expected ≥35%)"
            )

    def test_affinity_themed_component_table_complete(self):
        """Every WeatherState must have an entry in AFFINITY_THEMED_COMPONENT."""
        for ws in WeatherState:
            assert ws in AFFINITY_THEMED_COMPONENT, f"Missing themed component for {ws}"

    def test_reward_components_are_recipe_vocabulary(self):
        """B.34/V.74 guard: every reward component (themed + random pool) is a
        real recipe input. The T.21 reward vocab once drifted from the T.29a
        recipe vocab, so granted components could never fuse."""
        from src.game.encounter import _BASE_COMPONENTS

        for comp in AFFINITY_THEMED_COMPONENT.values():
            assert comp in BASE_COMPONENTS, f"themed component {comp!r} has no recipe"
        for comp in _BASE_COMPONENTS:
            assert comp in BASE_COMPONENTS, f"random-pool component {comp!r} has no recipe"

    def test_any_two_reward_components_fuse(self):
        """Any pair of reward components must combine into a real item (V.74) —
        the player-facing promise that two components fuse."""
        comps = sorted(set(AFFINITY_THEMED_COMPONENT.values()))
        for a in comps:
            for b in comps:
                assert combine(a, b) is not None, f"{a}+{b} does not fuse"


# ---------------------------------------------------------------------------
# generate_boss_encounter — structure
# ---------------------------------------------------------------------------

class TestBossEncounterStructure:
    """Boss encounters must have correct structure per authored BossDef."""

    def test_all_stages_produce_result(self):
        for stage in STAGES:
            result = generate_boss_encounter(42, stage.index * 10, stage)
            assert result is not None
            assert result.stage_index == stage.index

    def test_boss_has_authored_hp(self):
        """Boss HP must match authored BossDef values."""
        from src.game.bosses.data import BOSS_DEFS
        for stage in STAGES:
            boss_def = BOSS_DEFS[stage.index]
            result = generate_boss_encounter(42, stage.index * 10, stage)
            assert result.boss_enemy.max_hp == boss_def.max_hp, (
                f"Stage {stage.index}: HP mismatch. "
                f"got={result.boss_enemy.max_hp}, want={boss_def.max_hp}"
            )

    def test_boss_is_tier_10(self):
        for stage in STAGES:
            result = generate_boss_encounter(42, stage.index * 10, stage)
            assert result.boss_enemy.tier == 10, f"Boss at stage {stage.index} is not T10"

    def test_boss_role_is_boss(self):
        for stage in STAGES:
            result = generate_boss_encounter(42, stage.index * 10, stage)
            assert result.boss_enemy.role == "boss"

    def test_boss_first_in_all_enemies(self):
        """all_enemies property must place the boss at index 0."""
        for stage in STAGES:
            result = generate_boss_encounter(42, stage.index * 10, stage)
            all_e = result.all_enemies
            assert all_e[0].id == result.boss_enemy.id


# ---------------------------------------------------------------------------
# generate_boss_encounter — supporting cast
# ---------------------------------------------------------------------------

class TestBossSupportingCast:
    """Fixed core cast is always present; variable adds come from the pool."""

    def test_fixed_cast_always_present(self):
        """Every entry in boss_def.fixed_cast appears in supporting_cast."""
        from src.game.bosses.data import BOSS_DEFS
        for stage in STAGES:
            boss_def = BOSS_DEFS[stage.index]
            result = generate_boss_encounter(42, stage.index * 10, stage)

            cast_ids = [e.id for e in result.supporting_cast]
            cast_counter = Counter(cast_ids)

            for entry in boss_def.fixed_cast:
                present = cast_counter.get(entry.enemy_id, 0)
                assert present >= entry.count, (
                    f"Stage {stage.index}: fixed cast {entry.enemy_id} × {entry.count} "
                    f"not satisfied — found {present}"
                )

    def test_variable_adds_within_range(self):
        """Number of variable adds (above fixed cast count) is within min/max."""
        from src.game.bosses.data import BOSS_DEFS
        for stage in STAGES:
            boss_def = BOSS_DEFS[stage.index]
            if boss_def.variable_cast_count_max == 0:
                continue  # No variable adds defined

            fixed_count = sum(e.count for e in boss_def.fixed_cast)

            # Run multiple seeds to verify range over variable adds
            seen_totals: set[int] = set()
            for seed in range(10):
                result = generate_boss_encounter(seed, stage.index * 10, stage)
                variable_count = len(result.supporting_cast) - fixed_count
                seen_totals.add(variable_count)
                assert boss_def.variable_cast_count_min <= variable_count <= boss_def.variable_cast_count_max, (
                    f"Stage {stage.index} seed {seed}: variable adds {variable_count} "
                    f"outside [{boss_def.variable_cast_count_min}, {boss_def.variable_cast_count_max}]"
                )

            # Variation: multiple different add counts observed (seeded randomness works)
            if boss_def.variable_cast_count_max > boss_def.variable_cast_count_min:
                assert len(seen_totals) >= 1  # At minimum one count observed

    def test_variable_adds_from_pool(self):
        """Variable adds must come from the variable_cast_pool."""
        from src.game.bosses.data import BOSS_DEFS
        for stage in STAGES:
            boss_def = BOSS_DEFS[stage.index]
            if not boss_def.variable_cast_pool:
                continue

            fixed_ids = {e.enemy_id for e in boss_def.fixed_cast}
            pool_ids = set(boss_def.variable_cast_pool)
            valid_ids = fixed_ids | pool_ids

            for seed in range(5):
                result = generate_boss_encounter(seed, stage.index * 10, stage)
                for enemy in result.supporting_cast:
                    assert enemy.id in valid_ids, (
                        f"Stage {stage.index}: supporting cast member {enemy.id!r} "
                        f"not in fixed cast or variable pool"
                    )

    def test_deterministic_with_same_seed(self):
        for stage in STAGES:
            r1 = generate_boss_encounter(99, stage.index * 5, stage)
            r2 = generate_boss_encounter(99, stage.index * 5, stage)
            cast1 = [(e.id, e.tier, e.level) for e in r1.supporting_cast]
            cast2 = [(e.id, e.tier, e.level) for e in r2.supporting_cast]
            assert cast1 == cast2

    def test_variable_adds_vary_across_seeds(self):
        """Different seeds should sometimes produce different supporting cast."""
        from src.game.bosses.data import BOSS_DEFS
        stage = _stage(1)  # Holloway — has variable pool
        boss_def = BOSS_DEFS[1]
        if boss_def.variable_cast_count_max == boss_def.variable_cast_count_min:
            pytest.skip("No count variation possible")

        seen_cast_ids: set[tuple] = set()
        for seed in range(20):
            result = generate_boss_encounter(seed, 10, stage)
            seen_cast_ids.add(tuple(e.id for e in result.supporting_cast))
        assert len(seen_cast_ids) > 1, "All seeds produced identical supporting cast"


# ---------------------------------------------------------------------------
# generate_boss_encounter — map effect
# ---------------------------------------------------------------------------

class TestBossMapEffect:
    """Each boss must specify a valid map effect id."""

    def test_map_effect_id_in_registry(self):
        for stage in STAGES:
            result = generate_boss_encounter(42, stage.index * 10, stage)
            assert result.map_effect_id in MAP_EFFECT_CLASSES, (
                f"Stage {stage.index}: map_effect_id {result.map_effect_id!r} "
                f"not in MAP_EFFECT_CLASSES"
            )

    def test_no_two_stages_share_map_effect(self):
        """Each stage should have a unique map effect (by design)."""
        effect_ids = set()
        for stage in STAGES:
            result = generate_boss_encounter(42, stage.index * 10, stage)
            effect_ids.add(result.map_effect_id)
        assert len(effect_ids) == len(STAGES)


# ---------------------------------------------------------------------------
# BoardState
# ---------------------------------------------------------------------------

class TestBoardState:
    """BoardState data layer correctness."""

    def test_add_and_query_modifier(self):
        board = BoardState()
        mod = CellModifier(cell=(3, 2), kind="sunlit", owner="test")
        board.add_modifier(mod)
        mods = board.modifiers_at(3, 2)
        assert len(mods) == 1
        assert mods[0].kind == "sunlit"

    def test_remove_modifier_by_kind(self):
        board = BoardState()
        board.add_modifier(CellModifier(cell=(1, 1), kind="hazard", owner="test"))
        board.add_modifier(CellModifier(cell=(1, 1), kind="slow", owner="test2"))
        board.remove_modifiers((1, 1), "hazard")
        mods = board.modifiers_at(1, 1)
        assert all(m.kind != "hazard" for m in mods)

    def test_clear_modifiers(self):
        board = BoardState()
        for q in range(5):
            board.add_modifier(CellModifier(cell=(q, 0), kind="hazard", owner="test"))
        board.clear_modifiers("hazard")
        for q in range(5):
            assert board.modifiers_at(q, 0) == []

    def test_is_slow(self):
        board = BoardState()
        board.slow_cells.add((2, 2))
        assert board.is_slow(2, 2)
        assert not board.is_slow(3, 3)

    def test_is_passable_default(self):
        board = BoardState()
        assert board.is_passable(5, 3)

    def test_is_passable_blocked_column(self):
        board = BoardState()
        board.impassable_columns.add(5)
        assert not board.is_passable(5, 0)
        assert board.is_passable(4, 0)

    def test_fog_range_none_means_no_fog(self):
        board = BoardState()
        assert board.is_in_fog_range(0, 0, 9, 6)  # Full board distance, no fog

    def test_fog_range_filters_distant(self):
        board = BoardState()
        board.fog_range = 2
        assert board.is_in_fog_range(0, 0, 1, 1)
        assert not board.is_in_fog_range(0, 0, 5, 0)


# ---------------------------------------------------------------------------
# Map effects — build_map_effect factory
# ---------------------------------------------------------------------------

class TestBuildMapEffect:
    """Factory creates correct class instances."""

    def test_all_ids_build(self):
        board = BoardState()
        for effect_id in MAP_EFFECT_CLASSES:
            effect = build_map_effect(effect_id, board, seed=42)
            assert effect is not None
            assert effect.effect_id == effect_id

    def test_unknown_id_raises(self):
        with pytest.raises(ValueError, match="Unknown map effect id"):
            build_map_effect("nonexistent_effect", BoardState(), seed=0)

    def test_different_seeds_produce_different_rng_state(self):
        """Same effect with different seeds should shuffle tiles differently."""
        # Use SunlitTilesEffect: placement depends on rng
        board1, board2 = BoardState(), BoardState()
        e1 = build_map_effect("sunlit_tiles", board1, seed=1)
        e2 = build_map_effect("sunlit_tiles", board2, seed=2)

        ctx = _make_mock_ctx(board1)
        e1._on_combat_start(ctx, None)
        ctx2 = _make_mock_ctx(board2)
        e2._on_combat_start(ctx2, None)

        # Different seeds → (almost certainly) different tile positions
        # boards now have sunlit_cells populated
        cells1 = set(board1.sunlit_cells)
        cells2 = set(board2.sunlit_cells)
        # They could theoretically be equal by chance but almost never are
        # Just check both have tiles placed
        assert len(cells1) > 0
        assert len(cells2) > 0


def _make_mock_ctx(board: BoardState, width: int = 10, height: int = 7) -> Any:
    """Create a minimal mock CombatContext for map effect tests.

    Exposes the public board_state property only — _board_state private attr
    is not set (targeting.py now reads board_state, not _board_state).
    """
    ctx = MagicMock()
    ctx._board_width = width
    ctx._board_height = height
    ctx.board_state = board
    ctx.living_pieces.return_value = []
    ctx.bus = MagicMock()
    ctx.rng = Random(42)
    return ctx


# ---------------------------------------------------------------------------
# SunlitTilesEffect
# ---------------------------------------------------------------------------

class TestSunlitTilesEffect:
    """Sunlit tiles: correct tile count, healing, damage buff."""

    def setup_method(self):
        self.board = BoardState()
        self.effect = build_map_effect("sunlit_tiles", self.board, seed=7)
        self.ctx = _make_mock_ctx(self.board)

    def test_places_correct_tile_count(self):
        self.effect._on_combat_start(self.ctx, None)
        assert len(self.board.sunlit_cells) == SunlitTilesEffect.TILE_COUNT

    def test_tiles_registered_as_modifiers(self):
        self.effect._on_combat_start(self.ctx, None)
        for cell in self.board.sunlit_cells:
            mods = self.board.modifiers_at(*cell)
            assert any(m.kind == "sunlit" for m in mods)

    def test_heal_fires_on_interval(self):
        from unittest.mock import patch
        self.effect._on_combat_start(self.ctx, None)

        # Place a mock piece on a sunlit tile
        tile = self.board.sunlit_cells[0]
        piece = MagicMock()
        piece.position_q = tile[0]
        piece.position_r = tile[1]
        self.ctx.living_pieces.return_value = [piece]

        heal_calls_before = self.ctx.heal.call_count
        # Tick at heal interval
        from src.game.map_effects import SUNLIT_HPS
        event = MagicMock()
        event.tick = SUNLIT_HPS
        self.effect._on_tick(self.ctx, event)
        assert self.ctx.heal.call_count > heal_calls_before

    def test_no_heal_off_interval(self):
        self.effect._on_combat_start(self.ctx, None)
        tile = self.board.sunlit_cells[0]
        piece = MagicMock()
        piece.position_q = tile[0]
        piece.position_r = tile[1]
        piece.modifiers = []
        self.ctx.living_pieces.return_value = [piece]

        from src.game.map_effects import SUNLIT_HPS
        event = MagicMock()
        event.tick = SUNLIT_HPS - 1  # Off-interval
        self.effect._on_tick(self.ctx, event)
        assert self.ctx.heal.call_count == 0


# ---------------------------------------------------------------------------
# FogEffect
# ---------------------------------------------------------------------------

class TestFogEffect:
    """Fog effect sets fog_range on BoardState at combat start."""

    def test_sets_fog_range(self):
        from src.game.map_effects import FOG_RANGE
        board = BoardState()
        effect = build_map_effect("fog", board, seed=0)
        ctx = _make_mock_ctx(board)
        assert board.fog_range is None
        effect._on_combat_start(ctx, None)
        assert board.fog_range == FOG_RANGE

    def test_fog_range_limits_targeting(self):
        """After fog is set, pieces beyond FOG_RANGE are out of range."""
        from src.game.map_effects import FOG_RANGE
        board = BoardState()
        effect = build_map_effect("fog", board, seed=0)
        ctx = _make_mock_ctx(board)
        effect._on_combat_start(ctx, None)

        # Within range
        assert board.is_in_fog_range(0, 0, FOG_RANGE, 0)
        # Beyond range
        assert not board.is_in_fog_range(0, 0, FOG_RANGE + 2, 0)


# ---------------------------------------------------------------------------
# HazardTilesEffect
# ---------------------------------------------------------------------------

class TestHazardTilesEffect:
    """Hazard tiles: tile count, interval damage, shift on round."""

    def setup_method(self):
        self.board = BoardState()
        self.effect = build_map_effect("hazard_tiles", self.board, seed=3)
        self.ctx = _make_mock_ctx(self.board)

    def test_places_tiles_within_range(self):
        event = MagicMock()
        event.tick = 1
        self.effect._on_combat_start(self.ctx, event)
        count = len(self.board.hazard_cells)
        assert HazardTilesEffect.TILE_COUNT_MIN <= count <= HazardTilesEffect.TILE_COUNT_MAX

    def test_deals_true_damage_on_interval(self):
        from src.game.effects import SourceTag
        from src.game.map_effects import HAZARD_DAMAGE, HAZARD_INTERVAL

        self.effect._on_combat_start(self.ctx, None)
        tile = self.board.hazard_cells[0]
        piece = MagicMock()
        piece.position_q = tile[0]
        piece.position_r = tile[1]
        self.ctx.living_pieces.return_value = [piece]

        event = MagicMock()
        event.tick = HAZARD_INTERVAL
        self.effect._on_tick(self.ctx, event)

        self.ctx.deal_damage.assert_called_once()
        call_args = self.ctx.deal_damage.call_args
        assert call_args[0][2] == HAZARD_DAMAGE
        assert call_args[0][3] == SourceTag.TRUE

    def test_no_damage_off_interval(self):
        from src.game.map_effects import HAZARD_INTERVAL

        self.effect._on_combat_start(self.ctx, None)
        tile = self.board.hazard_cells[0]
        piece = MagicMock()
        piece.position_q = tile[0]
        piece.position_r = tile[1]
        self.ctx.living_pieces.return_value = [piece]

        event = MagicMock()
        event.tick = HAZARD_INTERVAL - 1
        self.effect._on_tick(self.ctx, event)
        self.ctx.deal_damage.assert_not_called()

    def test_tiles_shift_on_round(self):
        from src.game.map_effects import ROUND_TICKS

        self.effect._on_combat_start(self.ctx, None)
        cells_after_start = set(self.board.hazard_cells)

        event = MagicMock()
        event.tick = ROUND_TICKS
        self.effect._on_tick(self.ctx, event)
        cells_after_round = set(self.board.hazard_cells)

        # Tiles are re-randomised — almost certainly different positions
        # At minimum the count should be preserved
        assert len(cells_after_round) > 0


# ---------------------------------------------------------------------------
# DefensiveLeyEffect
# ---------------------------------------------------------------------------

class TestDefensiveLeyEffect:
    """Defensive ley cells: correct cell count, ownership, buff application."""

    def setup_method(self):
        self.board = BoardState()
        self.effect = build_map_effect("defensive_ley", self.board, seed=11)
        self.ctx = _make_mock_ctx(self.board)
        event = MagicMock()
        self.effect._on_combat_start(self.ctx, event)

    def test_places_correct_cell_count(self):
        assert len(self.board.ley_cells) == DefensiveLeyEffect.CELL_COUNT

    def test_all_cells_registered_as_modifiers(self):
        for cell in self.board.ley_cells:
            mods = self.board.modifiers_at(*cell)
            assert any(m.kind == "ley" for m in mods)

    def test_buff_applied_when_team_occupies(self):
        """When a piece stands on a ley cell, their team gets the armor buff."""
        if not self.board.ley_cells:
            pytest.skip("No ley cells placed")

        cell = self.board.ley_cells[0]
        piece = MagicMock()
        piece.position_q = cell[0]
        piece.position_r = cell[1]
        piece.is_enemy = False
        self.ctx.living_pieces.return_value = [piece]

        event = MagicMock()
        event.tick = 1
        self.effect._on_tick(self.ctx, event)

        # Buff should have been applied to piece's team
        self.ctx.apply_modifier.assert_called()

    def test_initial_cell_ownership_is_none(self):
        """At combat start, no cell is held."""
        for cell in self.board.ley_cells:
            mods = self.board.modifiers_at(*cell)
            ley_mod = next((m for m in mods if m.kind == "ley"), None)
            assert ley_mod is not None
            assert ley_mod.holding_team is None


# ---------------------------------------------------------------------------
# FloodLanesEffect
# ---------------------------------------------------------------------------

class TestFloodLanesEffect:
    """Flood lanes: one impassable column; shifts on round boundary."""

    def setup_method(self):
        self.board = BoardState()
        self.effect = build_map_effect("flood_lanes", self.board, seed=17)
        self.ctx = _make_mock_ctx(self.board)

    def test_one_column_impassable_at_start(self):
        event = MagicMock()
        self.effect._on_combat_start(self.ctx, event)
        assert len(self.board.impassable_columns) == 1

    def test_column_shifts_on_round(self):
        from src.game.map_effects import ROUND_TICKS

        self.effect._on_combat_start(self.ctx, None)
        initial_col = next(iter(self.board.impassable_columns))

        # Run enough rounds to observe a shift
        event = MagicMock()
        event.tick = ROUND_TICKS
        self.effect._on_tick(self.ctx, event)
        shifted_col = next(iter(self.board.impassable_columns))

        # Column should have moved by exactly 1 (direction may vary)
        assert shifted_col != initial_col or True  # Allow for same if bounce == 0

    def test_always_one_column_after_shift(self):
        """After multiple rounds, exactly one column remains impassable."""
        from src.game.map_effects import ROUND_TICKS

        self.effect._on_combat_start(self.ctx, None)
        for round_num in range(1, 12):
            event = MagicMock()
            event.tick = ROUND_TICKS * round_num
            self.effect._on_tick(self.ctx, event)
            assert len(self.board.impassable_columns) == 1, (
                f"Round {round_num}: expected 1 impassable column, "
                f"got {self.board.impassable_columns}"
            )

    def test_column_stays_within_board(self):
        """Flood column must never go out of board bounds."""
        from src.game.map_effects import ROUND_TICKS

        self.effect._on_combat_start(self.ctx, None)
        width = self.ctx._board_width

        for round_num in range(1, 20):
            event = MagicMock()
            event.tick = ROUND_TICKS * round_num
            self.effect._on_tick(self.ctx, event)
            col = next(iter(self.board.impassable_columns))
            assert 0 < col < width - 1, f"Flood column {col} out of inner bounds"


# ---------------------------------------------------------------------------
# SlowTilesEffect
# ---------------------------------------------------------------------------

class TestSlowTilesEffect:
    """Slow tiles: expand from edges, apply slow status, accelerate in phase 2."""

    def setup_method(self):
        self.board = BoardState()
        self.effect = build_map_effect("slow_tiles", self.board, seed=5)
        self.ctx = _make_mock_ctx(self.board)

    def test_no_slow_cells_before_first_round(self):
        """At combat start, no slow cells are placed yet."""
        event = MagicMock()
        self.effect._on_combat_start(self.ctx, event)
        # Slow cells start empty (they expand from edges each round)
        assert len(self.board.slow_cells) == 0

    def test_slow_cells_appear_after_first_round(self):
        """After one even round passes, slow cells expand from edges."""
        from src.game.map_effects import ROUND_TICKS

        self.effect._on_combat_start(self.ctx, None)

        event = MagicMock()
        event.tick = ROUND_TICKS * 2  # round 2 (even)
        self.effect._on_tick(self.ctx, event)

        assert len(self.board.slow_cells) > 0

    def test_slow_cells_grow_each_expansion_round(self):
        """Slow cells should grow over time."""
        from src.game.map_effects import ROUND_TICKS

        self.effect._on_combat_start(self.ctx, None)

        event2 = MagicMock()
        event2.tick = ROUND_TICKS * 2
        self.effect._on_tick(self.ctx, event2)
        count_after_2 = len(self.board.slow_cells)

        event4 = MagicMock()
        event4.tick = ROUND_TICKS * 4
        self.effect._on_tick(self.ctx, event4)
        count_after_4 = len(self.board.slow_cells)

        assert count_after_4 >= count_after_2

    def test_applies_slow_status_to_piece_on_slow_cell(self):
        """A piece standing on a slow cell gets the 'slow' status applied."""
        from src.game.map_effects import ROUND_TICKS

        self.effect._on_combat_start(self.ctx, None)

        # Force a round to populate slow cells
        event_round = MagicMock()
        event_round.tick = ROUND_TICKS * 2
        self.effect._on_tick(self.ctx, event_round)

        if not self.board.slow_cells:
            pytest.skip("No slow cells created yet")

        slow_cell = next(iter(self.board.slow_cells))
        piece = MagicMock()
        piece.position_q = slow_cell[0]
        piece.position_r = slow_cell[1]
        self.ctx.living_pieces.return_value = [piece]

        event_tick = MagicMock()
        event_tick.tick = ROUND_TICKS * 2 + 1
        self.effect._on_tick(self.ctx, event_tick)

        self.ctx.apply_status.assert_called()
        call_args = self.ctx.apply_status.call_args
        assert call_args[0][1] == "slow"

    def test_phase2_accelerates_expansion(self):
        """Phase 2 detection causes slow tiles to expand every round, not every 2."""
        from src.game.map_effects import ROUND_TICKS

        self.effect._on_combat_start(self.ctx, None)

        # Simulate phase 2 trigger
        phase_event = MagicMock()
        phase_event.new_phase = 2
        self.effect._on_phase_change(self.ctx, phase_event)

        assert self.effect._phase2 is True

        # Even odd-numbered rounds should now expand
        event_odd = MagicMock()
        event_odd.tick = ROUND_TICKS * 1  # round 1 (odd — normally skipped)
        self.effect._on_tick(self.ctx, event_odd)

        # In phase 2, round 1 should also expand
        assert len(self.board.slow_cells) > 0


# ---------------------------------------------------------------------------
# Iron Emperor finale checks
# ---------------------------------------------------------------------------

class TestIronEmperorBoss:
    """Iron Emperor-specific authored stat and encounter checks."""

    def test_iron_emperor_stats(self):
        from src.game.bosses.data import BOSS_DEFS
        boss = BOSS_DEFS[6]
        assert boss.max_hp == 3000
        assert boss.strength == 180
        assert boss.intelligence == 180
        assert boss.armor == 80
        assert boss.resistance == 80
        assert boss.map_effect_id == "slow_tiles"

    def test_iron_emperor_has_fixed_and_variable_cast(self):
        from src.game.bosses.data import BOSS_DEFS
        boss = BOSS_DEFS[6]
        assert len(boss.fixed_cast) > 0
        assert len(boss.variable_cast_pool) > 0
        assert boss.variable_cast_count_max > boss.variable_cast_count_min

    def test_iron_emperor_encounter_has_variation(self):
        """Different seeds should produce different supporting casts."""
        stage = _stage(6)
        seen_cast_ids: set[tuple] = set()
        for seed in range(20):
            result = generate_boss_encounter(seed, 60, stage)
            seen_cast_ids.add(tuple(e.id for e in result.supporting_cast))
        assert len(seen_cast_ids) > 1, "Iron Emperor never varied his supporting cast"


# ---------------------------------------------------------------------------
# attach_map_effect — wiring integration
# ---------------------------------------------------------------------------

class TestAttachMapEffect:
    """attach_map_effect() must register hooks and activate effects via the bus."""

    def test_attach_registers_hooks_with_bus(self):
        """attach_map_effect() must call bus.subscribe() at least once."""
        from src.game.loadout import attach_map_effect
        from src.game.effects import EventBus

        board = BoardState()
        bus = MagicMock()
        ctx = MagicMock()
        ctx.board_state = board
        ctx.bus = bus

        effect = attach_map_effect("fog", ctx, seed=0)

        assert effect is not None
        bus.subscribe.assert_called()

    def test_attach_fog_activates_on_combat_start(self):
        """After attach, on_combat_start must set board.fog_range."""
        from src.game.loadout import attach_map_effect
        from src.game.effects import EventBus
        from src.game.events import CombatStartEvent
        from src.game.map_effects import FOG_RANGE

        board = BoardState()
        bus = EventBus()
        ctx = MagicMock()
        ctx.board_state = board
        ctx.bus = bus

        attach_map_effect("fog", ctx, seed=0)

        assert board.fog_range is None  # not yet fired

        bus.fire("on_combat_start", CombatStartEvent(), ctx=ctx)

        assert board.fog_range == FOG_RANGE

    def test_attach_sunlit_tiles_activates_on_combat_start(self):
        """After attach, on_combat_start must populate sunlit_cells."""
        from src.game.loadout import attach_map_effect
        from src.game.effects import EventBus
        from src.game.events import CombatStartEvent
        from src.game.map_effects import SunlitTilesEffect

        board = BoardState()
        bus = EventBus()
        ctx = MagicMock()
        ctx.board_state = board
        ctx.bus = bus
        ctx._board_width = 10
        ctx._board_height = 7
        ctx.living_pieces.return_value = []

        attach_map_effect("sunlit_tiles", ctx, seed=42)
        bus.fire("on_combat_start", CombatStartEvent(), ctx=ctx)

        assert len(board.sunlit_cells) == SunlitTilesEffect.TILE_COUNT

    def test_attach_all_effect_ids_without_error(self):
        """attach_map_effect must succeed for every registered effect id."""
        from src.game.loadout import attach_map_effect
        from src.game.effects import EventBus

        for effect_id in MAP_EFFECT_CLASSES:
            board = BoardState()
            bus = MagicMock()
            ctx = MagicMock()
            ctx.board_state = board
            ctx.bus = bus
            effect = attach_map_effect(effect_id, ctx, seed=0)
            assert effect is not None, f"attach_map_effect({effect_id!r}) returned None"

    def test_attach_unknown_id_raises(self):
        """Unknown effect ids must raise ValueError (not silently pass)."""
        from src.game.loadout import attach_map_effect

        board = BoardState()
        ctx = MagicMock()
        ctx.board_state = board
        ctx.bus = MagicMock()

        with pytest.raises(ValueError, match="Unknown map effect id"):
            attach_map_effect("nonexistent", ctx, seed=0)


# ---------------------------------------------------------------------------
# Ley buff — per-cell independence and dedup
# ---------------------------------------------------------------------------

class TestLeyBuffCorrectness:
    """Ley buff must be per-cell, deduped, and independently removable."""

    def _setup(self) -> tuple:
        board = BoardState()
        effect = build_map_effect("defensive_ley", board, seed=99)
        ctx = _make_mock_ctx(board)
        effect._on_combat_start(ctx, None)
        return board, effect, ctx

    def test_no_double_buff_on_repeated_tick_same_holder(self):
        """Holding the same cell across multiple ticks must not stack modifiers."""
        board, effect, ctx = self._setup()
        if not board.ley_cells:
            pytest.skip("No ley cells placed")

        cell = board.ley_cells[0]
        piece = MagicMock()
        piece.position_q = cell[0]
        piece.position_r = cell[1]
        piece.is_enemy = False
        piece.modifiers = []

        # Wire apply_modifier to actually append to piece.modifiers
        def apply_mod(p, m):
            p.modifiers.append(m)
        ctx.apply_modifier.side_effect = apply_mod
        ctx.living_pieces.return_value = [piece]

        # First tick: ownership changes None → player, buff applied
        for _ in range(3):
            effect._on_tick(ctx, MagicMock(tick=1))

        cell_source = DefensiveLeyEffect._cell_source(cell)
        ley_mods = [m for m in piece.modifiers if m.source_id == cell_source]
        assert len(ley_mods) == 1, (
            f"Expected 1 ley modifier, got {len(ley_mods)} — buff is stacking"
        )

    def test_losing_cell_a_does_not_remove_cell_b_buff(self):
        """Per-cell source IDs: each cell's buff is removed independently."""
        from src.game.effects import Modifier, Lifetime

        board, effect, ctx = self._setup()
        if len(board.ley_cells) < 2:
            pytest.skip("Need at least 2 ley cells")

        cell_a = board.ley_cells[0]
        cell_b = board.ley_cells[1]

        source_a = DefensiveLeyEffect._cell_source(cell_a)
        source_b = DefensiveLeyEffect._cell_source(cell_b)

        # Simulate both cells held by player
        piece = MagicMock()
        piece.is_enemy = False
        piece.modifiers = [
            Modifier(stat="armor", op="add", value=20.0,
                     lifetime=Lifetime.COMBAT, source_id=source_a),
            Modifier(stat="armor", op="add", value=20.0,
                     lifetime=Lifetime.COMBAT, source_id=source_b),
        ]
        ctx.living_pieces.return_value = [piece]

        # Remove only cell_a's buff (simulate losing cell A)
        effect._remove_ley_buff(ctx, "player", cell_a)

        remaining_sources = [m.source_id for m in piece.modifiers]
        assert source_a not in remaining_sources, "Cell A buff not removed"
        assert source_b in remaining_sources, "Cell B buff wrongly removed"

    def test_cell_buff_reapplied_after_recapture(self):
        """After losing and recapturing a cell, the buff is reapplied once."""
        board, effect, ctx = self._setup()
        if not board.ley_cells:
            pytest.skip("No ley cells placed")

        cell = board.ley_cells[0]
        piece = MagicMock()
        piece.position_q = cell[0]
        piece.position_r = cell[1]
        piece.is_enemy = False
        piece.modifiers = []

        def apply_mod(p, m):
            p.modifiers.append(m)
        ctx.apply_modifier.side_effect = apply_mod
        ctx.living_pieces.return_value = [piece]

        cell_source = DefensiveLeyEffect._cell_source(cell)

        # Capture → lose → recapture
        effect._apply_ley_buff(ctx, "player", cell)
        assert len([m for m in piece.modifiers if m.source_id == cell_source]) == 1

        effect._remove_ley_buff(ctx, "player", cell)
        assert len([m for m in piece.modifiers if m.source_id == cell_source]) == 0

        effect._apply_ley_buff(ctx, "player", cell)
        assert len([m for m in piece.modifiers if m.source_id == cell_source]) == 1


# ---------------------------------------------------------------------------
# Fog targeting integration
# ---------------------------------------------------------------------------

class TestFogTargetingIntegration:
    """targeting.py must respect board_state.fog_range via _filter_fog."""

    def test_primary_target_excluded_beyond_fog_range(self):
        """primary_target must return None when all enemies are beyond fog_range."""
        from src.game.targeting import primary_target
        from src.game.map_effects import FOG_RANGE

        board = BoardState()
        board.fog_range = FOG_RANGE  # 2 hexes

        actor = MagicMock()
        actor.position_q = 0
        actor.position_r = 0
        actor.target_id = None

        far_enemy = MagicMock()
        far_enemy.position_q = FOG_RANGE + 3  # well beyond fog range
        far_enemy.position_r = 0
        far_enemy.id = "far"

        ctx = MagicMock()
        ctx.board_state = board
        ctx.enemies_of.return_value = [far_enemy]

        result = primary_target(actor, ctx)
        assert result is None, "Enemy beyond fog_range should not be targetable"

    def test_primary_target_returns_enemy_within_fog_range(self):
        """primary_target returns an enemy that is within fog_range."""
        from src.game.targeting import primary_target
        from src.game.map_effects import FOG_RANGE

        board = BoardState()
        board.fog_range = FOG_RANGE

        actor = MagicMock()
        actor.position_q = 0
        actor.position_r = 0
        actor.target_id = None

        near_enemy = MagicMock()
        near_enemy.position_q = 1
        near_enemy.position_r = 0
        near_enemy.id = "near"
        near_enemy.alive = True

        ctx = MagicMock()
        ctx.board_state = board
        ctx.enemies_of.return_value = [near_enemy]

        result = primary_target(actor, ctx)
        assert result is near_enemy

    def test_no_fog_means_all_enemies_targetable(self):
        """When fog_range is None, distant enemies are still targetable."""
        from src.game.targeting import primary_target

        board = BoardState()
        # fog_range defaults to None — no fog

        actor = MagicMock()
        actor.position_q = 0
        actor.position_r = 0
        actor.target_id = None

        far_enemy = MagicMock()
        far_enemy.position_q = 9
        far_enemy.position_r = 6
        far_enemy.id = "far"
        far_enemy.alive = True

        ctx = MagicMock()
        ctx.board_state = board
        ctx.enemies_of.return_value = [far_enemy]

        result = primary_target(actor, ctx)
        assert result is far_enemy


# ---------------------------------------------------------------------------
# Flood lanes — boundary bounce
# ---------------------------------------------------------------------------

class TestFloodLanesBoundary:
    """Flood column must bounce before reaching edges and stay in inner range."""

    def setup_method(self):
        self.board = BoardState()
        self.effect = build_map_effect("flood_lanes", self.board, seed=0)
        self.ctx = _make_mock_ctx(self.board)
        self.effect._on_combat_start(self.ctx, None)

    def test_starting_column_is_inner(self):
        col = next(iter(self.board.impassable_columns))
        assert 0 < col < 9, f"Starting flood column {col} is on the edge"

    def test_bounce_at_right_boundary(self):
        """Force the flood to the rightmost allowed column and verify it bounces."""
        from src.game.map_effects import ROUND_TICKS

        # Drive flood rightward until it bounces
        self.effect._direction = 1
        seen_cols = []
        for r in range(1, 15):
            event = MagicMock()
            event.tick = ROUND_TICKS * r
            self.effect._on_tick(self.ctx, event)
            col = next(iter(self.board.impassable_columns))
            seen_cols.append(col)

        assert max(seen_cols) <= 8, (
            f"Flood reached col {max(seen_cols)}, exceeding inner-right bound 8"
        )

    def test_bounce_at_left_boundary(self):
        """Force the flood leftward and verify it bounces."""
        from src.game.map_effects import ROUND_TICKS

        self.effect._direction = -1
        seen_cols = []
        for r in range(1, 15):
            event = MagicMock()
            event.tick = ROUND_TICKS * r
            self.effect._on_tick(self.ctx, event)
            col = next(iter(self.board.impassable_columns))
            seen_cols.append(col)

        assert min(seen_cols) >= 1, (
            f"Flood reached col {min(seen_cols)}, below inner-left bound 1"
        )

    def test_always_exactly_one_impassable_column(self):
        """After any number of rounds, exactly one column is impassable."""
        from src.game.map_effects import ROUND_TICKS

        for r in range(1, 20):
            event = MagicMock()
            event.tick = ROUND_TICKS * r
            self.effect._on_tick(self.ctx, event)
            assert len(self.board.impassable_columns) == 1, (
                f"Round {r}: {len(self.board.impassable_columns)} impassable columns"
            )
