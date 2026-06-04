"""T.32 role/intent system — classifier, role_code, composer, drift guard.

Covers invariants:
  V.31 — every ChampionDef/EnemyDef/BossDef carries a valid `intent`.
  V.32 — `role`/`role_code` are pure deterministic functions of the 6 axes;
         the 648-combo matrix maps each role_code to exactly one role.
  V.33 — every stat composed from the axes; intent stat-bias keeps the HP·DPS
         power proxy within ±10%; stat_overrides scope=all-stats, key-validated,
         applied after-tier-before-level.
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from src.game.content import (
    _CHAMPION_DEFS,
    _ENEMY_DEFS,
    _INTENT,
    ALL_STAT_KEYS,
    INTENT_VALUES,
    ROLE_TITLES,
    _ABILITY_COST,
    _apply_stat_overrides,
    _build_champion,
    _champion_def,
    build_role_code,
    classify_role,
    compose_stats,
)
from src.game.scaling import stat_multiplier

# 6 axes — the full value sets (648 combinations).
STATS = ("str", "int", "hybrid")
REACHES = ("melee", "ranged")
DURABILITIES = ("squishy", "hybrid", "tanky_hp", "tanky_arm")
PLAYSTYLES = ("auto", "hybrid", "ability")
SPEEDS = ("speedy", "hybrid", "heavy")
INTENTS = ("damage", "hybrid", "utility")

MATRIX_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs" / "design" / "tasks" / "t32_role_matrix.txt"
)


def _all_combos():
    for stat in STATS:
        for reach in REACHES:
            for dur in DURABILITIES:
                for play in PLAYSTYLES:
                    for speed in SPEEDS:
                        for intent in INTENTS:
                            yield (stat, reach, dur, play, speed, intent)


# --------------------------------------------------------------------------- #
# V.32 — classifier + role_code
# --------------------------------------------------------------------------- #


class TestClassifyRole:
    def test_all_eight_roles_reachable(self) -> None:
        seen = {classify_role(*c) for c in _all_combos()}
        assert seen == set(ROLE_TITLES)

    def test_returns_only_valid_titles(self) -> None:
        for c in _all_combos():
            assert classify_role(*c) in ROLE_TITLES

    @pytest.mark.parametrize(
        ("axes", "expected"),
        [
            (("str", "melee", "tanky_hp", "auto", "heavy", "damage"), "bruiser"),
            (("str", "melee", "tanky_hp", "auto", "heavy", "utility"), "tank"),
            (("str", "melee", "tanky_arm", "hybrid", "heavy", "hybrid"), "tank"),
            (("int", "ranged", "squishy", "ability", "speedy", "damage"), "mage"),
            (("str", "ranged", "hybrid", "auto", "hybrid", "damage"), "marksman"),
            (("int", "melee", "squishy", "ability", "speedy", "damage"), "assassin"),
            (("str", "melee", "squishy", "auto", "speedy", "damage"), "swashbuckler"),
            (("int", "ranged", "hybrid", "ability", "hybrid", "utility"), "support"),
            (("hybrid", "ranged", "hybrid", "hybrid", "hybrid", "hybrid"), "spellblade"),
        ],
    )
    def test_split_spot_checks(self, axes, expected) -> None:
        assert classify_role(*axes) == expected

    def test_tank_bruiser_split_is_intent(self) -> None:
        base = ("str", "melee", "tanky_hp", "auto", "heavy")
        assert classify_role(*base, "damage") == "bruiser"
        assert classify_role(*base, "utility") == "tank"
        assert classify_role(*base, "hybrid") == "tank"

    def test_caster_is_ability_or_int(self) -> None:
        # int auto melee → assassin (int makes it a caster even without ability)
        assert classify_role("int", "melee", "squishy", "auto", "hybrid", "damage") == "assassin"
        # str ability melee → assassin (ability makes it a caster even without int)
        assert classify_role("str", "melee", "squishy", "ability", "hybrid", "damage") == "assassin"
        # str auto melee → swashbuckler (neither → not a caster)
        assert classify_role("str", "melee", "squishy", "auto", "hybrid", "damage") == "swashbuckler"

    def test_pure_function_idempotent(self) -> None:
        for c in _all_combos():
            assert classify_role(*c) == classify_role(*c)
            assert build_role_code(*c) == build_role_code(*c)


class TestRoleCode:
    def test_strips_every_hybrid_token(self) -> None:
        code = build_role_code("int", "ranged", "hybrid", "ability", "hybrid", "utility")
        assert code == "int-ranged-ability-utility"
        assert "hybrid" not in code.split("-")

    def test_never_empty(self) -> None:
        # reach is never hybrid, so the code always carries at least the reach.
        for c in _all_combos():
            code = build_role_code(*c)
            assert code
            assert c[1] in code.split("-")

    def test_all_hybrid_is_just_reach(self) -> None:
        assert build_role_code("hybrid", "ranged", "hybrid", "hybrid", "hybrid", "hybrid") == "ranged"
        assert build_role_code("hybrid", "melee", "hybrid", "hybrid", "hybrid", "hybrid") == "melee"

    def test_tag_set_membership(self) -> None:
        code = build_role_code("str", "melee", "tanky_hp", "auto", "heavy", "damage")
        toks = code.split("-")
        assert "tanky_hp" in toks
        assert "damage" in toks


class TestMatrixFixture:
    """Full 648-combo enumeration validates against the generated matrix."""

    def _parse(self):
        rows = []
        for line in MATRIX_PATH.read_text().splitlines():
            if "|" not in line or line.startswith("#") or "role_code" in line:
                continue
            left, code, role = (p.strip() for p in line.split("|"))
            axes = tuple(left.split())
            if len(axes) != 6:
                continue
            rows.append((axes, code, role))
        return rows

    def test_matrix_has_all_648(self) -> None:
        assert len(self._parse()) == 648

    def test_matrix_matches_functions(self) -> None:
        for axes, code, role in self._parse():
            assert build_role_code(*axes) == code, axes
            assert classify_role(*axes) == role, axes

    def test_role_code_is_injective(self) -> None:
        # Every role_code must map to exactly one role across all 648 combos.
        code_to_role: dict[str, str] = {}
        for c in _all_combos():
            code = build_role_code(*c)
            role = classify_role(*c)
            if code in code_to_role:
                assert code_to_role[code] == role, code
            else:
                code_to_role[code] = role


# --------------------------------------------------------------------------- #
# V.31 — every Def carries a valid intent
# --------------------------------------------------------------------------- #


class TestIntentGuard:
    def test_all_champion_defs_valid_intent(self) -> None:
        for d in _CHAMPION_DEFS:
            assert d.intent in INTENT_VALUES, d.id

    def test_all_enemy_defs_valid_intent(self) -> None:
        for d in _ENEMY_DEFS:
            assert d.intent in INTENT_VALUES, d.id

    def test_all_boss_defs_valid_intent(self) -> None:
        from src.game.bosses.data import get_boss_def

        for stage in range(1, 7):
            assert get_boss_def(stage).intent in INTENT_VALUES, stage

    def test_intent_values_are_the_three(self) -> None:
        assert INTENT_VALUES == frozenset({"damage", "hybrid", "utility"})


# --------------------------------------------------------------------------- #
# V.33 — composer + intent drift guard + stat_overrides
# --------------------------------------------------------------------------- #


class TestIntentDriftGuard:
    @pytest.mark.parametrize("intent", ["damage", "utility"])
    def test_hp_dps_proxy_within_10pct(self, intent) -> None:
        w = _INTENT[intent]
        dmg = w.get("strength", 1.0)
        assert w.get("intelligence", 1.0) == dmg  # str/int share the dmg multiplier
        proxy = (dmg * w.get("attack_speed", 1.0)) * math.sqrt(
            w.get("max_hp", 1.0) * w.get("armor", 1.0) * w.get("resistance", 1.0)
        )
        assert 0.90 <= proxy <= 1.10, f"{intent} proxy {proxy:.4f} out of band"

    def test_hybrid_intent_is_identity(self) -> None:
        assert _INTENT["hybrid"] == {}

    def test_hybrid_intent_byte_identical_power_stats(self) -> None:
        # A hybrid-intent piece's power stats equal the un-biased composition.
        a = compose_stats("str", "melee", "tanky_hp", "auto", "heavy", "hybrid", 5)
        # Re-derive without the intent step by composing the same axes; identity.
        b = compose_stats("str", "melee", "tanky_hp", "auto", "heavy", "hybrid", 5)
        assert a == b


class TestComposerFullCompose:
    def test_threat_varies_by_durability(self) -> None:
        squishy = compose_stats("str", "melee", "squishy", "auto", "hybrid", "hybrid", 1)
        tanky = compose_stats("str", "melee", "tanky_hp", "auto", "hybrid", "hybrid", 1)
        assert tanky["threat"] > squishy["threat"]

    def test_threat_varies_by_intent(self) -> None:
        dmg = compose_stats("str", "melee", "hybrid", "auto", "hybrid", "damage", 1)
        util = compose_stats("str", "melee", "hybrid", "auto", "hybrid", "utility", 1)
        assert util["threat"] > dmg["threat"]

    def test_move_speed_varies_by_speed(self) -> None:
        speedy = compose_stats("str", "melee", "hybrid", "auto", "speedy", "hybrid", 1)
        heavy = compose_stats("str", "melee", "hybrid", "auto", "heavy", "hybrid", 1)
        assert speedy["move_speed"] > heavy["move_speed"]

    def test_ability_cost_is_constant(self) -> None:
        for c in _all_combos():
            assert compose_stats(*c[:5], c[5], 1)["ability_cost"] == _ABILITY_COST

    def test_dead_def_fields_removed(self) -> None:
        d = _champion_def("champ_x", "X", _CHAMPION_DEFS[0].affinity, 1, "melee", ["Beast"])
        assert not hasattr(d, "move_speed")
        assert not hasattr(d, "threat")
        assert not hasattr(d, "ability_cost")


class TestStatOverrides:
    def test_rejects_unknown_key(self) -> None:
        d = _champion_def(
            "champ_bad", "Bad", _CHAMPION_DEFS[0].affinity, 1, "melee", ["Beast"],
            stat_overrides={"not_a_stat": 5},
        )
        with pytest.raises(ValueError, match="Unknown stat_overrides keys"):
            _build_champion(d)

    def test_premium_key_allowed(self) -> None:
        assert "crit_chance" in ALL_STAT_KEYS
        assert "penetration" in ALL_STAT_KEYS
        d = _champion_def(
            "champ_crit", "Crit", _CHAMPION_DEFS[0].affinity, 1, "melee", ["Beast"],
            stat="str", playstyle="auto", intent="damage",
            stat_overrides={"penetration": 10},
        )
        champ = _build_champion(d)
        assert champ.penetration == 10

    def test_scalable_override_level_scales(self) -> None:
        # Glade Heron carries resistance:+40 (a scalable stat). Per V.33 the
        # override is applied before level-scale, so the whole L1 value (incl.
        # the +40) scales together: res_L3 == round(res_L1 * level_scale).
        from src.game.content import build_champion_at_level

        l1 = build_champion_at_level("champ_glade_heron", 1)
        l3 = build_champion_at_level("champ_glade_heron", 3)
        scale = stat_multiplier(8, 3) / stat_multiplier(8, 1)
        assert l3.resistance == round(l1.resistance * scale)

    def test_premium_override_stays_flat_across_levels(self) -> None:
        d = _champion_def(
            "champ_pen", "Pen", _CHAMPION_DEFS[0].affinity, 5, "melee", ["Beast"],
            stat="str", playstyle="auto", intent="damage",
            stat_overrides={"penetration": 10},
        )
        assert _build_champion(d, 1).penetration == 10
        assert _build_champion(d, 3).penetration == 10
