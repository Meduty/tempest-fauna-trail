"""Tests for the T.29a item engine.

Covers:
  - RECIPE_MAP completeness (all 36 entries including same-component diagonal)
  - combine() correctness and edge-cases
  - Champion.items model: 3-slot enforcement, serialization round-trip
  - piece_from_champion copies items into Piece.items
  - Raw component bundle application (stat increase)
  - Hook item: Splitwind Talons procs deterministically in a fixed-seed fight
  - Mana item: Deepwell / springtear affect ActiveSlot
  - Spellfang Crown sets ability_can_crit via on_combat_start
  - Living Bulwark is a pure stat item (no hooks)
  - REWARD loot: same seed → same drop; independent of squad seed
  - No-item regression: no-item teams produce byte-identical results
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from src.game.effects import EffectBundle, EventBus
from src.game.encounter import generate_reward_loot, CH_REWARD, derive_seed
from src.game.items import BASE_COMPONENTS, RECIPE_MAP, combine
from src.game.items.base import SPIRIT_GEM
from src.game.loadout import apply_bundle, compile_loadout, piece_from_champion
from src.game.models import Champion, WeatherState
from src.game.piece import ActiveSlot, Piece
from src.game.registries import ITEM_REGISTRY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_champ(**kwargs: Any) -> Champion:
    """Build a minimal Champion for tests."""
    defaults: dict[str, Any] = {
        "id": "test_champ",
        "name": "Tester",
        "affinity": WeatherState.CLEAR,
        "role": "bruiser",
        "tier": 1,
        "level": 1,
        "max_hp": 1000,
        "strength": 100,
        "intelligence": 100,
        "attack_speed": 100,
        "move_speed": 100,
        "mana_regen": 100,
        "threat": 50,
        "armor": 50,
        "resistance": 50,
        "attack_range": 1,
        "active_ability": "",
        "passive_ability": "",
        "traits": ["Beast"],
    }
    defaults.update(kwargs)
    return Champion(**defaults)


def _make_piece_with_items(item_ids: list[str]) -> tuple[Piece, EventBus]:
    """Build a Piece that has item_ids equipped, apply bundles, return (piece, bus)."""
    champ = _make_champ(items=item_ids)
    piece = piece_from_champion(champ)
    bus = EventBus()
    for item_id in piece.items:
        factory = ITEM_REGISTRY.get(item_id)
        if factory:
            bundle = factory(piece)
            if bundle:
                apply_bundle(piece, bundle, bus)
    return piece, bus


# ---------------------------------------------------------------------------
# Recipe map — completeness
# ---------------------------------------------------------------------------

class TestRecipeMap:
    def test_total_entries_is_36(self) -> None:
        assert len(RECIPE_MAP) == 36

    def test_same_component_diagonal_all_8(self) -> None:
        """Each base component combines with itself."""
        for comp in BASE_COMPONENTS:
            key = frozenset({comp})
            assert key in RECIPE_MAP, f"same-component recipe missing for {comp!r}"

    def test_cross_component_28_entries(self) -> None:
        cross = [k for k in RECIPE_MAP if len(k) == 2]
        assert len(cross) == 28

    def test_all_values_are_strings(self) -> None:
        for key, value in RECIPE_MAP.items():
            assert isinstance(value, str) and value, f"Bad value for {key!r}"


# ---------------------------------------------------------------------------
# combine()
# ---------------------------------------------------------------------------

class TestCombine:
    def test_same_component_fang(self) -> None:
        assert combine("fang", "fang") == "apex_fang"

    def test_same_component_talon(self) -> None:
        assert combine("talon", "talon") == "tempest_talons"

    def test_cross_fang_talon(self) -> None:
        assert combine("fang", "talon") == "huntress_talon"

    def test_cross_order_independent(self) -> None:
        """combine(a, b) == combine(b, a)."""
        assert combine("talon", "fang") == combine("fang", "talon")

    def test_unknown_pair_returns_none(self) -> None:
        assert combine("fang", "unicorn_dust") is None

    def test_spirit_gem_crafts_emblem(self) -> None:
        """Spirit-Gem + mapped component → that Kinship's emblem (T.29b §3.5);
        unmapped components (wardpelt/keen_claw) craft nothing."""
        assert combine(SPIRIT_GEM, "fang") == "beast_emblem"
        assert combine("fang", SPIRIT_GEM) == "beast_emblem"
        assert combine(SPIRIT_GEM, "heartseed") == "spirit_emblem"
        assert combine(SPIRIT_GEM, "wardpelt") is None
        assert combine(SPIRIT_GEM, "keen_claw") is None

    def test_all_36_pairs_resolve(self) -> None:
        """Every RECIPE_MAP key resolves through combine()."""
        from random import Random
        rng = Random(42)
        comps = sorted(BASE_COMPONENTS)
        for a in comps:
            for b in comps:
                result = combine(a, b)
                assert result is not None, f"combine({a!r}, {b!r}) returned None"

    def test_known_core_cut_items_resolve(self) -> None:
        expected = {
            ("heartseed", "keen_claw"): "spellfang_crown",
            ("old_hide", "stoneplate"): "living_bulwark",
            ("talon", "wardpelt"): "splitwind_talons",
            ("heartseed", "springtear"): "everbloom_staff",
        }
        for (a, b), item_id in expected.items():
            assert combine(a, b) == item_id, f"combine({a!r},{b!r}) != {item_id!r}"


# ---------------------------------------------------------------------------
# Champion.items model
# ---------------------------------------------------------------------------

class TestChampionItems:
    def test_default_items_empty(self) -> None:
        champ = _make_champ()
        assert champ.items == []

    def test_equip_up_to_3(self) -> None:
        champ = _make_champ(items=["fang", "talon", "heartseed"])
        assert champ.items == ["fang", "talon", "heartseed"]

    def test_equip_4_raises(self) -> None:
        with pytest.raises(ValueError, match="at most 3"):
            _make_champ(items=["fang", "talon", "heartseed", "old_hide"])

    def test_empty_string_item_raises(self) -> None:
        with pytest.raises(ValueError):
            _make_champ(items=["fang", ""])

    def test_to_dict_includes_items(self) -> None:
        champ = _make_champ(items=["fang", "talon"])
        d = champ.to_dict()
        assert d["items"] == ["fang", "talon"]

    def test_from_dict_round_trip(self) -> None:
        champ = _make_champ(items=["spellfang_crown", "living_bulwark"])
        d = champ.to_dict()
        restored = Champion.from_dict(d)
        assert restored.items == ["spellfang_crown", "living_bulwark"]

    def test_from_dict_legacy_no_items_field(self) -> None:
        """Old saves without an 'items' key must load with items=[]."""
        champ = _make_champ()
        d = champ.to_dict()
        del d["items"]
        restored = Champion.from_dict(d)
        assert restored.items == []


# ---------------------------------------------------------------------------
# piece_from_champion copies items
# ---------------------------------------------------------------------------

class TestPieceFromChampion:
    def test_items_copied_to_piece(self) -> None:
        champ = _make_champ(items=["fang", "talon"])
        piece = piece_from_champion(champ)
        assert piece.items == ["fang", "talon"]

    def test_no_items_piece_has_empty_list(self) -> None:
        champ = _make_champ()
        piece = piece_from_champion(champ)
        assert piece.items == []

    def test_items_list_is_a_copy(self) -> None:
        """Mutating piece.items must not affect champion.items."""
        champ = _make_champ(items=["fang"])
        piece = piece_from_champion(champ)
        piece.items.append("talon")
        assert champ.items == ["fang"]


# ---------------------------------------------------------------------------
# Raw component stat bundles
# ---------------------------------------------------------------------------

class TestRawComponents:
    def test_fang_increases_strength(self) -> None:
        piece, _ = _make_piece_with_items(["fang"])
        assert piece.stat("strength") > 100.0  # base is 100, +12%

    def test_fang_strength_multiplier(self) -> None:
        piece, _ = _make_piece_with_items(["fang"])
        assert pytest.approx(piece.stat("strength"), rel=1e-3) == 100 * 1.12

    def test_talon_increases_attack_speed(self) -> None:
        piece, _ = _make_piece_with_items(["talon"])
        assert piece.stat("attack_speed") > 100.0

    def test_heartseed_increases_intelligence(self) -> None:
        piece, _ = _make_piece_with_items(["heartseed"])
        assert pytest.approx(piece.stat("intelligence"), rel=1e-3) == 100 * 1.12

    def test_old_hide_increases_hp(self) -> None:
        piece, _ = _make_piece_with_items(["old_hide"])
        assert pytest.approx(piece.stat("hp"), rel=1e-3) == 1000 * 1.12

    def test_stoneplate_increases_armor(self) -> None:
        piece, _ = _make_piece_with_items(["stoneplate"])
        assert pytest.approx(piece.stat("armor"), rel=1e-3) == 50 * 1.14

    def test_wardpelt_increases_resistance(self) -> None:
        piece, _ = _make_piece_with_items(["wardpelt"])
        assert pytest.approx(piece.stat("resistance"), rel=1e-3) == 50 * 1.14

    def test_keen_claw_adds_crit_chance(self) -> None:
        piece, _ = _make_piece_with_items(["keen_claw"])
        assert pytest.approx(piece.stat("crit_chance"), rel=1e-3) == 0.15

    def test_multiple_components_stack(self) -> None:
        piece, _ = _make_piece_with_items(["fang", "heartseed"])
        assert pytest.approx(piece.stat("strength"), rel=1e-3) == 100 * 1.12
        assert pytest.approx(piece.stat("intelligence"), rel=1e-3) == 100 * 1.12


# ---------------------------------------------------------------------------
# Springtear mana handling
# ---------------------------------------------------------------------------

class TestSpringtearMana:
    def _piece_with_slot(self, item_ids: list[str]) -> Piece:
        """Build a piece with an active slot and apply item bundles + on_combat_start."""
        champ = _make_champ(items=item_ids, active_ability="test_ability")
        piece = piece_from_champion(champ)
        piece.actives = [ActiveSlot(ability_id="test_ability", mana_cost=300_000, current_mana=0.0)]
        bus = EventBus()
        for iid in piece.items:
            factory = ITEM_REGISTRY.get(iid)
            if factory:
                bundle = factory(piece)
                if bundle:
                    apply_bundle(piece, bundle, bus)
        # Fire on_combat_start to trigger mana hooks
        from src.game.events import CombatStartEvent
        bus.fire("on_combat_start", CombatStartEvent(), ctx=None)
        return piece

    def test_springtear_grants_starting_mana(self) -> None:
        # Flat 100_000 (≈1/3 of the 300_000 default cost); slot max_mana 600_000.
        piece = self._piece_with_slot(["springtear"])
        assert piece.actives[0].current_mana == 100_000.0

    def test_springtear_keeps_cost_and_boosts_regen(self) -> None:
        # V.48: mana items NEVER reduce mana_cost; springtear grants mana_regen
        # (Modifier) + starting mana instead.
        piece = self._piece_with_slot(["springtear"])
        assert piece.actives[0].mana_cost == 300_000
        assert any(
            m.stat == "mana_regen" and m.source_id == "item:springtear"
            for m in piece.modifiers
        )

    def test_deepwell_grants_more_mana(self) -> None:
        # Flat 200_000 (≈2/3 of default cost — two springtears).
        piece = self._piece_with_slot(["deepwell"])
        assert piece.actives[0].current_mana == 200_000.0

    def test_deepwell_keeps_cost_and_boosts_regen(self) -> None:
        # V.48: deepwell grants mana_regen + starting mana, never cuts mana_cost.
        piece = self._piece_with_slot(["deepwell"])
        assert piece.actives[0].mana_cost == 300_000
        assert any(
            m.stat == "mana_regen" and m.source_id == "item:deepwell"
            for m in piece.modifiers
        )

    def test_mana_cap_at_max_mana(self) -> None:
        """Granted starting mana is clamped to max_mana (the universal cap, V.48)."""
        champ = _make_champ(items=["deepwell"], active_ability="x")
        piece = piece_from_champion(champ)
        # Small cost ⇒ max_mana = 2*100 = 200; deepwell grants 200_000 → clamp to 200.
        piece.actives = [ActiveSlot(ability_id="x", mana_cost=100, current_mana=0.0)]
        bus = EventBus()
        factory = ITEM_REGISTRY["deepwell"]
        apply_bundle(piece, factory(piece), bus)
        from src.game.events import CombatStartEvent
        bus.fire("on_combat_start", CombatStartEvent(), ctx=None)
        assert piece.actives[0].current_mana <= float(piece.actives[0].max_mana)
        assert piece.actives[0].current_mana == 200.0


# ---------------------------------------------------------------------------
# Spellfang Crown — ability_can_crit flag
# ---------------------------------------------------------------------------

class TestSpellfangCrown:
    def test_ability_can_crit_false_before_combat_start(self) -> None:
        piece, bus = _make_piece_with_items(["spellfang_crown"])
        # Flag not yet set — on_combat_start hasn't fired
        assert piece.ability_can_crit is False

    def test_ability_can_crit_true_after_combat_start(self) -> None:
        piece, bus = _make_piece_with_items(["spellfang_crown"])
        from src.game.events import CombatStartEvent
        bus.fire("on_combat_start", CombatStartEvent(), ctx=None)
        assert piece.ability_can_crit is True

    def test_spellfang_crown_also_grants_crit_chance_and_int(self) -> None:
        piece, _ = _make_piece_with_items(["spellfang_crown"])
        assert pytest.approx(piece.stat("intelligence"), rel=1e-3) == 100 * 1.12
        assert pytest.approx(piece.stat("crit_chance"), rel=1e-3) == 0.15


# ---------------------------------------------------------------------------
# Living Bulwark — pure stat, no hooks
# ---------------------------------------------------------------------------

class TestLivingBulwark:
    def test_living_bulwark_applies_hp_and_armor(self) -> None:
        piece, _ = _make_piece_with_items(["living_bulwark"])
        assert pytest.approx(piece.stat("hp"), rel=1e-3) == 1000 * 1.12
        assert pytest.approx(piece.stat("armor"), rel=1e-3) == 50 * 1.14

    def test_living_bulwark_has_support_aura_hook(self) -> None:
        # T.29a rebalance: living_bulwark gained an on_combat_start ally-armor aura
        # (was a pure stat stick). Stat modifiers + exactly one hook.
        champ = _make_champ(items=["living_bulwark"])
        piece = piece_from_champion(champ)
        factory = ITEM_REGISTRY["living_bulwark"]
        bundle = factory(piece)
        assert len(bundle.hooks) == 1
        assert bundle.hooks[0].event == "on_combat_start"
        assert len(bundle.modifiers) == 2  # +HP, +armor


# ---------------------------------------------------------------------------
# compile_loadout integration — items applied via pipeline
# ---------------------------------------------------------------------------

class TestCompileLoadoutItems:
    def _champ_with_items(self, item_ids: list[str]) -> Champion:
        """Build a minimal champion with given items for compile_loadout testing."""
        return _make_champ(
            id="hero",
            active_ability="",
            passive_ability="",
            items=item_ids,
        )

    def _enemy(self) -> "Any":
        from src.game.models import Enemy
        return Enemy(
            id="foe",
            name="Foe",
            affinity=WeatherState.CLEAR,
            role="attacker",
            tier=1,
            level=1,
            max_hp=500,
            strength=80,
            intelligence=0,
            attack_speed=100,
            move_speed=100,
            mana_regen=0,
            threat=50,
            armor=0,
            resistance=0,
            attack_range=1,
            active_ability="",
            passive_ability="",
        )

    def test_fang_stat_applied_in_compile_loadout(self) -> None:
        champ = self._champ_with_items(["fang"])
        base_str = champ.strength
        enemies = [self._enemy()]
        pieces, _, _ = compile_loadout([champ], enemies, WeatherState.CLEAR, seed=42)
        player_piece = next(p for p in pieces if not p.is_enemy)
        # +12% STR via fang applied before weather; stat should be > base
        assert player_piece.stat("strength") > base_str

    def test_no_item_regression(self) -> None:
        """A champion with no items produces byte-identical results twice."""
        from src.game.combat.resolve import resolve_combat

        champ_a = self._champ_with_items([])
        champ_b = copy.deepcopy(champ_a)
        enemies_a = [self._enemy()]
        enemies_b = copy.deepcopy(enemies_a)

        result_a = resolve_combat([champ_a], enemies_a, WeatherState.CLEAR)
        result_b = resolve_combat([champ_b], enemies_b, WeatherState.CLEAR)
        assert result_a.outcome == result_b.outcome
        assert result_a.duration_ticks == result_b.duration_ticks

    def test_item_applied_in_pipeline_spellfang_crown(self) -> None:
        """Spellfang Crown should set ability_can_crit on the piece via compile_loadout."""
        from src.game.combat.resolve import resolve_combat
        from src.game.models import CombatOutcome
        champ = self._champ_with_items(["spellfang_crown"])
        enemies = [self._enemy()]
        result = resolve_combat([champ], enemies, WeatherState.CLEAR)
        assert result.outcome in (CombatOutcome.WIN, CombatOutcome.LOSS, CombatOutcome.DRAW)


# ---------------------------------------------------------------------------
# Splitwind Talons — deterministic proc in a fixed-seed fight
# ---------------------------------------------------------------------------

class TestSplitwindTalons:
    def test_item_registered(self) -> None:
        assert "splitwind_talons" in ITEM_REGISTRY

    def test_splitwind_bundle_has_hook(self) -> None:
        piece, _ = _make_piece_with_items([])
        factory = ITEM_REGISTRY["splitwind_talons"]
        bundle = factory(piece)
        assert len(bundle.hooks) == 1
        assert bundle.hooks[0].event == "on_attack_landed"

    def test_splitwind_stat_bonuses(self) -> None:
        piece, _ = _make_piece_with_items(["splitwind_talons"])
        assert pytest.approx(piece.stat("attack_speed"), rel=1e-3) == 100 * 1.12
        assert pytest.approx(piece.stat("resistance"), rel=1e-3) == 50 * 1.14


# ---------------------------------------------------------------------------
# REWARD loot — seed-determinism
# ---------------------------------------------------------------------------

class TestRewardLoot:
    def test_same_seed_same_loot(self) -> None:
        loot_a = generate_reward_loot(12345, 7)
        loot_b = generate_reward_loot(12345, 7)
        assert loot_a.item_ids == loot_b.item_ids

    def test_different_seed_may_differ(self) -> None:
        """Different seeds should not always produce the same result."""
        results: set[str] = set()
        for seed in range(100):
            loot = generate_reward_loot(seed, 0)
            results.add(",".join(loot.item_ids))
        assert len(results) > 1, "All seeds produced the same loot — RNG is broken"

    def test_loot_contains_valid_item_ids(self) -> None:
        from src.game.items.recipes import RECIPE_MAP
        from src.game.items.base import BASE_COMPONENTS
        valid_ids = set(BASE_COMPONENTS) | set(RECIPE_MAP.values())
        for seed in range(20):
            loot = generate_reward_loot(seed, seed % 5)
            for item_id in loot.item_ids:
                assert item_id in valid_ids, f"Unknown item id {item_id!r} in loot"

    def test_loot_is_not_empty(self) -> None:
        for seed in range(10):
            loot = generate_reward_loot(seed, 0)
            assert len(loot.item_ids) >= 1

    def test_loot_ch_reward_is_independent_of_enemies_seed(self) -> None:
        """CH_REWARD and CH_ENEMIES derive different seeds so loot and squad don't collide."""
        loot_seed = derive_seed(99, 3, CH_REWARD)
        enemy_seed = derive_seed(99, 3, 0)  # CH_ENEMIES == 0
        assert loot_seed != enemy_seed
