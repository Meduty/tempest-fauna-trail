"""Tests for src/game/content (T5 acceptance criteria)."""

from __future__ import annotations

import re

import pytest

from src.game.content import (
    ALL_TRAIT_TAGS,
    CALLING_TAGS,
    CHAMPION_ROSTER,
    ENEMY_ROSTER,
    ENEMY_TAGS,
    ENEMY_TAGS_MAP,
    KINSHIP_TAGS,
    discover_abilities,
    champions_by_affinity,
    compose_stats,
    enemies_by_affinity,
    get_champion,
    get_enemy,
)
from src.game.models import WeatherState


# --------------------------------------------------------------------------- #
# §10.1 Schema correctness
# --------------------------------------------------------------------------- #


class TestSchemaCorrectness:
    """Every champion and enemy constructs without raising ValueError."""

    def test_all_champions_valid(self) -> None:
        # If any Champion.__post_init__ raised, the roster wouldn't have built.
        assert len(CHAMPION_ROSTER) > 0

    def test_all_enemies_valid(self) -> None:
        assert len(ENEMY_ROSTER) > 0


# --------------------------------------------------------------------------- #
# §10.2 Roster shape
# --------------------------------------------------------------------------- #


class TestRosterShape:
    def test_champion_roster_size(self) -> None:
        assert len(CHAMPION_ROSTER) == 60

    @pytest.mark.parametrize("weather", list(WeatherState))
    def test_champions_per_affinity(self, weather: WeatherState) -> None:
        assert len(champions_by_affinity(weather)) == 10

    def test_enemy_roster_size(self) -> None:
        assert len(ENEMY_ROSTER) == 60

    def test_clear_enemies_count(self) -> None:
        assert len(enemies_by_affinity(WeatherState.CLEAR)) == 30

    @pytest.mark.parametrize(
        "weather",
        [w for w in WeatherState if w != WeatherState.CLEAR],
    )
    def test_non_clear_enemies_count(self, weather: WeatherState) -> None:
        assert len(enemies_by_affinity(weather)) == 6


# --------------------------------------------------------------------------- #
# §10.3 ID uniqueness and format
# --------------------------------------------------------------------------- #


class TestIDFormat:
    def test_no_duplicate_champion_ids(self) -> None:
        ids = list(CHAMPION_ROSTER.keys())
        assert len(ids) == len(set(ids))

    def test_no_duplicate_enemy_ids(self) -> None:
        ids = list(ENEMY_ROSTER.keys())
        assert len(ids) == len(set(ids))

    def test_disjoint_namespaces(self) -> None:
        assert set(CHAMPION_ROSTER.keys()).isdisjoint(set(ENEMY_ROSTER.keys()))

    def test_champion_id_format(self) -> None:
        for cid in CHAMPION_ROSTER:
            assert re.fullmatch(r"champ_[a-z0-9_]+", cid), f"Bad champion id: {cid}"

    def test_enemy_id_format(self) -> None:
        for eid in ENEMY_ROSTER:
            assert re.fullmatch(r"enemy_[a-z0-9_]+", eid), f"Bad enemy id: {eid}"


# --------------------------------------------------------------------------- #
# §10.4 Level lock
# --------------------------------------------------------------------------- #


class TestLevelLock:
    def test_all_champions_level_1(self) -> None:
        for c in CHAMPION_ROSTER.values():
            assert c.level == 1, f"{c.id} has level {c.level}"

    def test_all_enemies_level_1(self) -> None:
        for e in ENEMY_ROSTER.values():
            assert e.level == 1, f"{e.id} has level {e.level}"


# --------------------------------------------------------------------------- #
# §10.5 Trait validity
# --------------------------------------------------------------------------- #


class TestTraitValidity:
    def test_traits_in_all_trait_tags(self) -> None:
        for c in CHAMPION_ROSTER.values():
            for tag in c.traits:
                assert tag in ALL_TRAIT_TAGS, f"{c.id} has unknown trait: {tag}"

    def test_tier_10_has_primordial(self) -> None:
        for c in CHAMPION_ROSTER.values():
            if c.tier == 10:
                assert "Primordial" in c.traits, f"{c.id} (T10) missing Primordial"

    def test_no_empty_traits(self) -> None:
        for c in CHAMPION_ROSTER.values():
            assert len(c.traits) > 0, f"{c.id} has empty traits"


# --------------------------------------------------------------------------- #
# §10.6 Stat monotonicity (scaling sanity)
# --------------------------------------------------------------------------- #


class TestStatMonotonicity:
    def test_higher_tier_stronger_scaled_stats(self) -> None:
        """For champions sharing archetype axes, higher tier has bigger scaled stats."""
        # Group champions by archetype (using role as a proxy since it derives from axes)
        from src.game.content import _CHAMPION_DEFS

        by_archetype: dict[tuple, list] = {}
        for d in _CHAMPION_DEFS:
            key = (d.stat, d.reach, d.durability, d.playstyle, d.speed, d.intent)
            by_archetype.setdefault(key, []).append(d)

        for key, defs in by_archetype.items():
            if len(defs) < 2:
                continue
            sorted_defs = sorted(defs, key=lambda d: d.tier)
            for i in range(len(sorted_defs) - 1):
                lo = CHAMPION_ROSTER[sorted_defs[i].id]
                hi = CHAMPION_ROSTER[sorted_defs[i + 1].id]
                assert hi.max_hp >= lo.max_hp, (
                    f"{hi.id}(T{hi.tier}) max_hp < {lo.id}(T{lo.tier})"
                )
                assert (hi.strength + hi.intelligence) >= (
                    lo.strength + lo.intelligence
                ), f"{hi.id} primary < {lo.id}"

    def test_flat_stats_same_across_tiers(self) -> None:
        """Only FLAT_STATS (attack_range) are tier-invariant for a shared
        archetype; speeds now scale with tier (SECONDARY, V.34)."""
        from src.game.content import _CHAMPION_DEFS

        by_archetype: dict[tuple, list] = {}
        for d in _CHAMPION_DEFS:
            key = (d.stat, d.reach, d.durability, d.playstyle, d.speed, d.intent)
            by_archetype.setdefault(key, []).append(d)

        for key, defs in by_archetype.items():
            if len(defs) < 2:
                continue
            champs = sorted(
                (CHAMPION_ROSTER[d.id] for d in defs), key=lambda c: c.tier
            )
            for prev, cur in zip(champs, champs[1:]):
                assert cur.attack_range == prev.attack_range, (
                    f"{cur.id} range != {prev.id} range"
                )
                # attack_speed scales with tier (V.34): higher tier ⇒ ≥ AS.
                assert cur.attack_speed >= prev.attack_speed, (
                    f"{cur.id}(T{cur.tier}) AS < {prev.id}(T{prev.tier})"
                )


# --------------------------------------------------------------------------- #
# §10.7 Lookup helpers
# --------------------------------------------------------------------------- #


class TestLookupHelpers:
    def test_get_champion_success(self) -> None:
        c = get_champion("champ_dawnwisp")
        assert c.name == "Dawnwisp"

    def test_get_champion_miss(self) -> None:
        with pytest.raises(KeyError):
            get_champion("nonexistent_id")

    def test_get_enemy_success(self) -> None:
        e = get_enemy("enemy_conscript")
        assert e.name == "Conscript"

    def test_get_enemy_miss(self) -> None:
        with pytest.raises(KeyError):
            get_enemy("nonexistent_id")

    def test_champions_by_affinity_clear(self) -> None:
        result = champions_by_affinity(WeatherState.CLEAR)
        assert len(result) == 10
        assert all(c.affinity == WeatherState.CLEAR for c in result)


# --------------------------------------------------------------------------- #
# §10.8 Enemy tags map
# --------------------------------------------------------------------------- #


class TestEnemyTagsMap:
    def test_all_keys_in_roster(self) -> None:
        for key in ENEMY_TAGS_MAP:
            assert key in ENEMY_ROSTER, f"{key} not in ENEMY_ROSTER"

    def test_values_are_non_empty_frozensets(self) -> None:
        for key, tags in ENEMY_TAGS_MAP.items():
            assert isinstance(tags, frozenset), f"{key}: not a frozenset"
            assert len(tags) > 0, f"{key}: empty tags"

    def test_tag_values_from_enemy_tags(self) -> None:
        for key, tags in ENEMY_TAGS_MAP.items():
            for t in tags:
                assert t in ENEMY_TAGS, f"{key}: unknown tag {t!r}"


# --------------------------------------------------------------------------- #
# compose_stats smoke test
# --------------------------------------------------------------------------- #


class TestComposeStats:
    def test_returns_dict_with_expected_keys(self) -> None:
        result = compose_stats("str", "melee", "hybrid", "auto", "hybrid", "hybrid", 1)
        expected_keys = {
            "max_hp", "strength", "intelligence", "armor", "resistance",
            "attack_speed", "mana_regen", "move_speed", "threat",
            "attack_range",
        }
        assert expected_keys.issubset(result.keys())

    def test_tier_1_base(self) -> None:
        # At tier 1, stat_multiplier is 1.0; all-hybrid (intent included) is identity.
        result = compose_stats("hybrid", "melee", "hybrid", "hybrid", "hybrid", "hybrid", 1)
        assert result["max_hp"] == 600
        assert result["strength"] == 50
        assert result["intelligence"] == 50

    def test_speed_axis_changes_attack_style_stats(self) -> None:
        speedy = compose_stats("str", "melee", "hybrid", "auto", "speedy", "hybrid", 1)
        neutral = compose_stats("str", "melee", "hybrid", "auto", "hybrid", "hybrid", 1)
        heavy = compose_stats("str", "melee", "hybrid", "auto", "heavy", "hybrid", 1)
        assert speedy["attack_speed"] > neutral["attack_speed"] > heavy["attack_speed"]
        assert speedy["strength"] < neutral["strength"] < heavy["strength"]
        # Speed also drives move_speed (T.32): speedy ↑, heavy ↓.
        assert speedy["move_speed"] > neutral["move_speed"] > heavy["move_speed"]

    def test_speed_axis_changes_ability_style_stats(self) -> None:
        # T.33b: casters express speed as cast tempo — faster ⇒ ↑attack_speed + ↑mana_regen
        # (half the AS deviation, on both), ↓primary_stat. Speed no longer touches resistance.
        speedy = compose_stats("int", "ranged", "hybrid", "ability", "speedy", "hybrid", 1)
        neutral = compose_stats("int", "ranged", "hybrid", "ability", "hybrid", "hybrid", 1)
        heavy = compose_stats("int", "ranged", "hybrid", "ability", "heavy", "hybrid", 1)
        assert speedy["attack_speed"] > neutral["attack_speed"] > heavy["attack_speed"]
        assert speedy["mana_regen"] > neutral["mana_regen"] > heavy["mana_regen"]
        assert speedy["intelligence"] < neutral["intelligence"] < heavy["intelligence"]
        assert speedy["resistance"] == neutral["resistance"] == heavy["resistance"]

    def test_invalid_speed_axis_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown speed axis value"):
            compose_stats("str", "melee", "hybrid", "auto", "ultra", "hybrid", 1)

    @pytest.mark.parametrize(
        ("stat", "reach", "durability", "intent", "msg"),
        [
            ("vigor", "melee", "hybrid", "damage", "Unknown stat axis value"),
            ("str", "sniper", "hybrid", "damage", "Unknown reach axis value"),
            ("str", "melee", "glass", "damage", "Unknown durability axis value"),
            ("str", "melee", "hybrid", "vibes", "Unknown intent axis value"),
        ],
    )
    def test_invalid_axis_values_raise_value_error(
        self,
        stat: str,
        reach: str,
        durability: str,
        intent: str,
        msg: str,
    ) -> None:
        with pytest.raises(ValueError, match=msg):
            compose_stats(stat, reach, durability, "auto", "hybrid", intent, 1)

    def test_invalid_playstyle_axis_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown playstyle axis value"):
            compose_stats("str", "melee", "hybrid", "burst", "hybrid", "hybrid", 1)


# --------------------------------------------------------------------------- #
# V.47 — axis ↔ scaling alignment (T.35b, B.20)
# --------------------------------------------------------------------------- #
#
# A unit whose `stat` axis is INT-heavy must actually *read* INT in its kit, or
# the INT-heavy statline is dead weight (#42 Finding B). The universal auto-attack
# (1.0·STR + 0.2·INT) counts for STR, so `str` units are auto-satisfied; `int` and
# `hybrid` units must reference INT via a Magnitude on their active/passive meta.


def _meta_references_int(ability_id: str) -> bool:
    """True if any Magnitude on this ability's meta scales from intelligence."""
    from src.game.registries import (
        ABILITY_META,
        MaxOfTerm,
        ScalingTerm,
    )

    meta = ABILITY_META.get(ability_id)
    if meta is None:
        return False
    terms = list(meta.terms)
    for clause in meta.clauses:
        terms.extend(clause.terms)
    for t in terms:
        if isinstance(t, ScalingTerm):
            s = t.scaling
            if "intelligence" in s or re.search(r"\bint\b", s):
                return True
        elif isinstance(t, MaxOfTerm):
            if any(st in ("intelligence", "int") for st in t.stats):
                return True
    return False


# INT flows through a non-meta channel (a summon's SummonSpec stat-fraction), so a
# meta-only scan can't see it — but the INT is NOT dead. Allowlisted with reason.
_V47_SUMMON_INT_ALLOWLIST: dict[str, str] = {
    "enemy_steam_engineer": "INT sizes the turret statline via _STEAM_TURRET SummonSpec (intelligence*0.5), not a meta outlet",
}


class TestAxisScalingAlignment:
    """V.47: int/hybrid units must read INT in their kit (no dead INT)."""

    def _defs(self):
        import src.game.abilities  # noqa: F401  (registers ABILITY_META)
        from src.game.content import _CHAMPION_DEFS, _ENEMY_DEFS

        return list(_CHAMPION_DEFS) + list(_ENEMY_DEFS)

    def test_int_and_hybrid_units_reference_int(self) -> None:
        offenders = []
        for d in self._defs():
            if d.stat not in ("int", "hybrid"):
                continue  # str auto-satisfied via the auto-attack (1.0 STR + 0.2 INT)
            if d.id in _V47_SUMMON_INT_ALLOWLIST:
                continue
            # T.29d: a piece may have multiple discovered actives — INT may be
            # referenced in any active or the passive.
            active_ids = d.abilities if d.abilities is not None else discover_abilities(d.id)
            if not (
                any(_meta_references_int(aid) for aid in active_ids)
                or _meta_references_int(d.passive_ability)
            ):
                offenders.append(f"{d.id} (stat={d.stat})")
        assert not offenders, (
            "V.47: these int/hybrid units never read INT in their kit (dead INT):\n"
            + "\n".join(sorted(offenders))
        )

    def test_guard_detects_a_dead_int_meta(self) -> None:
        # Negative control: a meta with no INT magnitude must read as non-referencing.
        from src.game.registries import ABILITY_META, AbilityMeta, ScalingTerm

        ABILITY_META["__test_dead_int__"] = AbilityMeta(
            name="Dead", kind="active", blurb="x",
            terms=(ScalingTerm("damage", 10.0, "strength*1.0"),),
        )
        try:
            assert _meta_references_int("__test_dead_int__") is False
        finally:
            del ABILITY_META["__test_dead_int__"]
