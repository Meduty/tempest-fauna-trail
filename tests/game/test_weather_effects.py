from dataclasses import replace

import pytest

from src.game.models import Champion, Enemy, WeatherState
from src.game.weather_effects import (
    CYCLE_ORDER,
    DAMAGE_MULT,
    IDENTITY,
    TIER_SCALAR,
    WEATHER_BUFF_BASE,
    WEATHER_DEBUFF_BASE,
    CombatModifier,
    RingRelation,
    apply_weather,
    combat_modifier,
    damage_modifier,
    ring_relation,
    shop_weight,
)

ACTIVE_WEATHERS = tuple(w for w in WeatherState if w != WeatherState.CLEAR)


def _make_champion(affinity: WeatherState) -> Champion:
    return Champion(
        id=f"champ_{affinity.value}",
        name=f"Test {affinity.value}",
        affinity=affinity,
        role="attacker",
        tier=3,
        level=1,
        max_hp=100,
        strength=20,
        intelligence=20,
        attack_speed=100,
        move_speed=100,
        mana_regen=10,
        threat=20,
        armor=10,
        resistance=10,
        attack_range=2,
        active_ability="Test Cast",
        passive_ability="Test Passive",
        ability_cost=100,
        traits=["Mammal", "Hunter"],
    )


def _make_enemy(affinity: WeatherState) -> Enemy:
    return Enemy(
        id=f"enemy_{affinity.value}",
        name=f"Test Enemy {affinity.value}",
        affinity=affinity,
        role="bruiser",
        tier=2,
        level=1,
        max_hp=80,
        strength=15,
        intelligence=15,
        attack_speed=100,
        move_speed=100,
        mana_regen=5,
        threat=15,
        armor=8,
        resistance=8,
        attack_range=1,
        active_ability="Test Cast",
        passive_ability="Test Passive",
        ability_cost=100,
    )


# --- Ring --------------------------------------------------------------------


def test_cycle_order_is_the_five_active_weathers_in_ring_order() -> None:
    assert CYCLE_ORDER == (
        WeatherState.MIST,
        WeatherState.CLOUDY,
        WeatherState.RAIN,
        WeatherState.SNOW,
        WeatherState.THUNDER,
    )
    assert WeatherState.CLEAR not in CYCLE_ORDER
    assert set(CYCLE_ORDER) == set(ACTIVE_WEATHERS)


def test_ring_relation_self_on_diagonal() -> None:
    for weather in ACTIVE_WEATHERS:
        assert ring_relation(weather, weather) == RingRelation.SELF


def test_ring_relation_neutral_when_clear_involved() -> None:
    for weather in WeatherState:
        assert ring_relation(WeatherState.CLEAR, weather) == RingRelation.NEUTRAL
        assert ring_relation(weather, WeatherState.CLEAR) == RingRelation.NEUTRAL


def test_ring_relation_predator_prey_are_inverse() -> None:
    # a is b's primary predator <=> b is a's primary prey (same for secondary).
    inverse = {
        RingRelation.PRIMARY_PREDATOR: RingRelation.PRIMARY_PREY,
        RingRelation.SECONDARY_PREDATOR: RingRelation.SECONDARY_PREY,
        RingRelation.PRIMARY_PREY: RingRelation.PRIMARY_PREDATOR,
        RingRelation.SECONDARY_PREY: RingRelation.SECONDARY_PREDATOR,
        RingRelation.SELF: RingRelation.SELF,
    }
    for a in ACTIVE_WEATHERS:
        for b in ACTIVE_WEATHERS:
            assert ring_relation(a, b) == inverse[ring_relation(b, a)]


def test_ring_relation_known_pairs() -> None:
    # Ring: MIST CLOUDY RAIN SNOW THUNDER. SNOW preys on RAIN.
    assert ring_relation(WeatherState.SNOW, WeatherState.RAIN) == RingRelation.PRIMARY_PREDATOR
    assert ring_relation(WeatherState.THUNDER, WeatherState.RAIN) == RingRelation.SECONDARY_PREDATOR
    assert ring_relation(WeatherState.CLOUDY, WeatherState.RAIN) == RingRelation.PRIMARY_PREY
    assert ring_relation(WeatherState.MIST, WeatherState.RAIN) == RingRelation.SECONDARY_PREY


def test_every_active_weather_has_one_self_two_predators_two_prey() -> None:
    for weather in ACTIVE_WEATHERS:
        counts = {relation: 0 for relation in RingRelation}
        for affinity in ACTIVE_WEATHERS:
            counts[ring_relation(affinity, weather)] += 1
        assert counts[RingRelation.SELF] == 1
        assert counts[RingRelation.PRIMARY_PREDATOR] == 1
        assert counts[RingRelation.SECONDARY_PREDATOR] == 1
        assert counts[RingRelation.PRIMARY_PREY] == 1
        assert counts[RingRelation.SECONDARY_PREY] == 1


# --- Weather Favor — combat_modifier ----------------------------------------------


def test_combat_modifier_identity_when_clear_involved() -> None:
    for weather in WeatherState:
        assert combat_modifier(WeatherState.CLEAR, weather) is IDENTITY
    for affinity in WeatherState:
        assert combat_modifier(affinity, WeatherState.CLEAR) is IDENTITY


def test_combat_modifier_self_is_strong_full_buff() -> None:
    # Self uses the strong tier (scalar 1.0) — the unscaled buff base.
    assert combat_modifier(WeatherState.THUNDER, WeatherState.THUNDER) is WEATHER_BUFF_BASE[
        WeatherState.THUNDER
    ]


def test_combat_modifier_predator_tiers_scale_the_buff() -> None:
    # RAIN buff base: AS x1.15, MR x1.15. Primary predator SNOW -> medium (0.6).
    primary = combat_modifier(WeatherState.SNOW, WeatherState.RAIN)
    assert primary.as_mult == pytest.approx(1.09)
    assert primary.mr_mult == pytest.approx(1.09)
    # Secondary predator THUNDER -> weak (0.3).
    secondary = combat_modifier(WeatherState.THUNDER, WeatherState.RAIN)
    assert secondary.as_mult == pytest.approx(1.045)
    assert secondary.mr_mult == pytest.approx(1.045)


def test_combat_modifier_prey_tiers_scale_the_debuff() -> None:
    # RAIN debuff base: STR x0.85. Primary prey CLOUDY -> medium (0.6).
    primary = combat_modifier(WeatherState.CLOUDY, WeatherState.RAIN)
    assert primary.str_mult == pytest.approx(0.91)
    # Secondary prey MIST -> weak (0.3).
    secondary = combat_modifier(WeatherState.MIST, WeatherState.RAIN)
    assert secondary.str_mult == pytest.approx(0.955)


def test_self_is_strict_maximum_buff_tier() -> None:
    assert TIER_SCALAR[RingRelation.SELF] > TIER_SCALAR[RingRelation.PRIMARY_PREDATOR]
    assert (
        TIER_SCALAR[RingRelation.PRIMARY_PREDATOR]
        > TIER_SCALAR[RingRelation.SECONDARY_PREDATOR]
    )


def test_no_strong_debuff_tier() -> None:
    # Debuffs only reach medium — primary prey is the deepest.
    assert TIER_SCALAR[RingRelation.PRIMARY_PREY] == 0.6
    assert TIER_SCALAR[RingRelation.SECONDARY_PREY] == 0.3


def test_mist_range_debuff_survives_medium_tier_vanishes_at_weak() -> None:
    # MIST debuff base: attack_range_delta -1. Primary prey of MIST = THUNDER.
    medium = combat_modifier(WeatherState.THUNDER, WeatherState.MIST)
    assert medium.attack_range_delta == -1
    # Secondary prey of MIST = SNOW -> rounds to 0.
    weak = combat_modifier(WeatherState.SNOW, WeatherState.MIST)
    assert weak.attack_range_delta == 0


def test_combat_modifier_is_deterministic() -> None:
    first = combat_modifier(WeatherState.SNOW, WeatherState.RAIN)
    second = combat_modifier(WeatherState.SNOW, WeatherState.RAIN)
    assert first == second


# --- Affinity Clash — damage_modifier ----------------------------------------------


def test_damage_modifier_values_by_relation() -> None:
    # Enemy RAIN; ring positions around it.
    assert damage_modifier(WeatherState.SNOW, WeatherState.RAIN) == pytest.approx(1.30)
    assert damage_modifier(WeatherState.THUNDER, WeatherState.RAIN) == pytest.approx(1.12)
    assert damage_modifier(WeatherState.RAIN, WeatherState.RAIN) == pytest.approx(1.00)
    assert damage_modifier(WeatherState.MIST, WeatherState.RAIN) == pytest.approx(0.88)
    assert damage_modifier(WeatherState.CLOUDY, WeatherState.RAIN) == pytest.approx(0.70)


def test_damage_modifier_clear_is_inert_both_ways() -> None:
    for weather in WeatherState:
        assert damage_modifier(WeatherState.CLEAR, weather) == 1.00
        assert damage_modifier(weather, WeatherState.CLEAR) == 1.00


def test_damage_modifier_predator_beats_one_above_prey() -> None:
    for relation, mult in DAMAGE_MULT.items():
        if relation in (RingRelation.PRIMARY_PREDATOR, RingRelation.SECONDARY_PREDATOR):
            assert mult > 1.0
        elif relation in (RingRelation.PRIMARY_PREY, RingRelation.SECONDARY_PREY):
            assert mult < 1.0
        else:
            assert mult == 1.0


def test_damage_modifier_exchange_ratio_is_tamed() -> None:
    # Primary predator/prey exchange ~1.86x; secondary ~1.27x.
    primary = damage_modifier(
        WeatherState.SNOW, WeatherState.RAIN
    ) / damage_modifier(WeatherState.RAIN, WeatherState.SNOW)
    secondary = damage_modifier(
        WeatherState.THUNDER, WeatherState.RAIN
    ) / damage_modifier(WeatherState.RAIN, WeatherState.THUNDER)
    assert primary == pytest.approx(1.30 / 0.70)
    assert secondary == pytest.approx(1.12 / 0.88)
    assert primary > secondary


# --- Shop weight -------------------------------------------------------------


def test_shop_weight_by_relation() -> None:
    assert shop_weight(WeatherState.RAIN, WeatherState.RAIN) == 2.0
    assert shop_weight(WeatherState.SNOW, WeatherState.RAIN) == 1.5
    assert shop_weight(WeatherState.THUNDER, WeatherState.RAIN) == 1.2
    assert shop_weight(WeatherState.MIST, WeatherState.RAIN) == 0.8
    assert shop_weight(WeatherState.CLOUDY, WeatherState.RAIN) == 0.6


def test_shop_weight_neutral_when_clear_involved() -> None:
    for weather in WeatherState:
        assert shop_weight(WeatherState.CLEAR, weather) == 1.0
        assert shop_weight(weather, WeatherState.CLEAR) == 1.0


# --- apply_weather -----------------------------------------------------------


def test_apply_weather_clear_returns_unscaled_stats_and_copies_affinity() -> None:
    champion = _make_champion(WeatherState.RAIN)
    piece = apply_weather(champion, WeatherState.CLEAR)

    assert piece.piece_id == champion.id
    assert piece.is_enemy is False
    assert piece.affinity == WeatherState.RAIN
    assert piece.max_hp == champion.max_hp
    assert piece.hp == champion.max_hp
    assert piece.strength == champion.strength
    assert piece.attack_range == champion.attack_range


def test_apply_weather_self_buff_scales_strong_tier() -> None:
    champion = _make_champion(WeatherState.THUNDER)
    piece = apply_weather(champion, WeatherState.THUNDER)

    assert piece.strength == round(champion.strength * 1.15)
    assert piece.attack_speed == round(champion.attack_speed * 1.15)
    assert piece.intelligence == champion.intelligence
    assert piece.affinity == WeatherState.THUNDER


def test_apply_weather_mist_debuff_drops_attack_range_with_floor() -> None:
    # THUNDER is MIST's primary prey -> medium debuff -> range -1.
    champion = _make_champion(WeatherState.THUNDER)
    piece = apply_weather(champion, WeatherState.MIST)
    assert piece.attack_range == champion.attack_range - 1

    melee = replace(_make_champion(WeatherState.THUNDER), attack_range=1)
    melee_piece = apply_weather(melee, WeatherState.MIST)
    assert melee_piece.attack_range == 1


def test_apply_weather_works_with_enemy_and_flags_is_enemy() -> None:
    enemy = _make_enemy(WeatherState.MIST)
    piece = apply_weather(enemy, WeatherState.MIST)

    assert piece.is_enemy is True
    assert piece.affinity == WeatherState.MIST
    assert piece.move_speed == round(enemy.move_speed * 1.15)
    assert piece.threat == round(enemy.threat * 1.15)


# --- OpenWeather id mapping --------------------------------------------------


def test_from_openweather_id_maps_main_groups() -> None:
    assert WeatherState.from_openweather_id(200) == WeatherState.THUNDER
    assert WeatherState.from_openweather_id(232) == WeatherState.THUNDER
    assert WeatherState.from_openweather_id(300) == WeatherState.RAIN
    assert WeatherState.from_openweather_id(500) == WeatherState.RAIN
    assert WeatherState.from_openweather_id(531) == WeatherState.RAIN
    assert WeatherState.from_openweather_id(600) == WeatherState.SNOW
    assert WeatherState.from_openweather_id(622) == WeatherState.SNOW
    assert WeatherState.from_openweather_id(701) == WeatherState.MIST
    assert WeatherState.from_openweather_id(781) == WeatherState.MIST
    assert WeatherState.from_openweather_id(800) == WeatherState.CLEAR
    assert WeatherState.from_openweather_id(801) == WeatherState.CLOUDY
    assert WeatherState.from_openweather_id(804) == WeatherState.CLOUDY


def test_from_openweather_id_raises_on_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown OpenWeather id"):
        WeatherState.from_openweather_id(999)


# --- CombatModifier dataclass ------------------------------------------------


def test_combat_modifier_dataclass_is_frozen() -> None:
    modifier = CombatModifier(str_mult=1.10)
    with pytest.raises(Exception):
        modifier.str_mult = 2.0  # type: ignore[misc]


def test_weather_debuff_base_has_an_entry_per_weather() -> None:
    for weather in WeatherState:
        assert weather in WEATHER_BUFF_BASE
        assert weather in WEATHER_DEBUFF_BASE
