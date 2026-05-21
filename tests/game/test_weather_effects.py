from dataclasses import replace

import pytest

from src.game.models import Champion, Enemy, WeatherState
from src.game.weather_effects import (
    BUFFED_AFFINITIES,
    CYCLE_ORDER,
    DEBUFFED_AFFINITIES,
    IDENTITY,
    WEATHER_BUFFS,
    WEATHER_DEBUFFS,
    CombatModifier,
    Relation,
    apply_modifier,
    combat_modifier,
    relation,
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


def test_cycle_order_excludes_clear_and_covers_all_active_weathers() -> None:
    assert WeatherState.CLEAR not in CYCLE_ORDER
    assert set(CYCLE_ORDER) == set(ACTIVE_WEATHERS)
    assert len(CYCLE_ORDER) == 5


def test_active_weathers_buff_three_affinities_each() -> None:
    for weather in ACTIVE_WEATHERS:
        buffed = BUFFED_AFFINITIES[weather]
        assert len(buffed) == 3
        assert weather in buffed
        assert WeatherState.CLEAR not in buffed


def test_active_weathers_debuff_two_affinities_each() -> None:
    for weather in ACTIVE_WEATHERS:
        debuffed = DEBUFFED_AFFINITIES[weather]
        assert len(debuffed) == 2
        assert weather not in debuffed
        assert WeatherState.CLEAR not in debuffed


def test_clear_has_no_buffs_or_debuffs() -> None:
    assert BUFFED_AFFINITIES[WeatherState.CLEAR] == frozenset()
    assert DEBUFFED_AFFINITIES[WeatherState.CLEAR] == frozenset()


def test_buff_and_debuff_sets_are_disjoint_per_weather() -> None:
    for weather in ACTIVE_WEATHERS:
        assert BUFFED_AFFINITIES[weather].isdisjoint(DEBUFFED_AFFINITIES[weather])


def test_buff_edges_are_mutual_among_active_weathers() -> None:
    for w1 in ACTIVE_WEATHERS:
        for w2 in BUFFED_AFFINITIES[w1]:
            assert w1 in BUFFED_AFFINITIES[w2]


def test_debuff_edges_are_mutual_among_active_weathers() -> None:
    for w1 in ACTIVE_WEATHERS:
        for w2 in DEBUFFED_AFFINITIES[w1]:
            assert w1 in DEBUFFED_AFFINITIES[w2]


def test_every_active_affinity_has_three_strong_and_two_weak_weathers() -> None:
    for affinity in ACTIVE_WEATHERS:
        strong = [w for w in ACTIVE_WEATHERS if affinity in BUFFED_AFFINITIES[w]]
        weak = [w for w in ACTIVE_WEATHERS if affinity in DEBUFFED_AFFINITIES[w]]
        assert len(strong) == 3
        assert len(weak) == 2


def test_active_pair_is_either_strong_or_weak_never_neutral() -> None:
    for affinity in ACTIVE_WEATHERS:
        for weather in ACTIVE_WEATHERS:
            rel = relation(affinity, weather)
            assert rel in {Relation.STRONG, Relation.WEAK}


def test_clear_affinity_is_neutral_against_all_weathers() -> None:
    for weather in WeatherState:
        assert relation(WeatherState.CLEAR, weather) == Relation.NEUTRAL


def test_clear_weather_is_neutral_against_all_affinities() -> None:
    for affinity in WeatherState:
        assert relation(affinity, WeatherState.CLEAR) == Relation.NEUTRAL


def test_self_affinity_is_always_strong_under_own_active_weather() -> None:
    for weather in ACTIVE_WEATHERS:
        assert relation(weather, weather) == Relation.STRONG


def test_combat_modifier_returns_identity_when_clear_involved() -> None:
    for affinity in WeatherState:
        assert combat_modifier(affinity, WeatherState.CLEAR) is IDENTITY
    for weather in WeatherState:
        assert combat_modifier(WeatherState.CLEAR, weather) is IDENTITY


def test_combat_modifier_returns_weather_buff_for_strong_pair() -> None:
    assert combat_modifier(WeatherState.RAIN, WeatherState.THUNDER) is WEATHER_BUFFS[WeatherState.THUNDER]


def test_combat_modifier_returns_weather_debuff_for_weak_pair() -> None:
    assert combat_modifier(WeatherState.SNOW, WeatherState.THUNDER) is WEATHER_DEBUFFS[WeatherState.THUNDER]


def test_shop_weight_exact_match_doubles_pull() -> None:
    for weather in ACTIVE_WEATHERS:
        assert shop_weight(weather, weather) == 2.0


def test_shop_weight_strong_neighbour_boosts() -> None:
    assert shop_weight(WeatherState.MIST, WeatherState.CLOUDY) == 1.5
    assert shop_weight(WeatherState.THUNDER, WeatherState.CLOUDY) == 1.5


def test_shop_weight_weak_diagonal_halves() -> None:
    assert shop_weight(WeatherState.SNOW, WeatherState.CLOUDY) == 0.5
    assert shop_weight(WeatherState.RAIN, WeatherState.CLOUDY) == 0.5


def test_shop_weight_neutral_when_clear_involved() -> None:
    for weather in WeatherState:
        assert shop_weight(WeatherState.CLEAR, weather) == 1.0
    for affinity in WeatherState:
        assert shop_weight(affinity, WeatherState.CLEAR) == 1.0


def test_apply_modifier_clear_weather_returns_unscaled_stats() -> None:
    champion = _make_champion(WeatherState.RAIN)
    piece = apply_modifier(champion, WeatherState.CLEAR)

    assert piece.piece_id == champion.id
    assert piece.is_enemy is False
    assert piece.max_hp == champion.max_hp
    assert piece.hp == champion.max_hp
    assert piece.strength == champion.strength
    assert piece.attack_range == champion.attack_range


def test_apply_modifier_thunder_buff_scales_str_and_as() -> None:
    champion = _make_champion(WeatherState.RAIN)
    piece = apply_modifier(champion, WeatherState.THUNDER)

    assert piece.strength == round(champion.strength * 1.10)
    assert piece.attack_speed == round(champion.attack_speed * 1.10)
    assert piece.intelligence == champion.intelligence


def test_apply_modifier_mist_debuff_drops_attack_range_with_floor() -> None:
    champion = _make_champion(WeatherState.THUNDER)
    piece = apply_modifier(champion, WeatherState.MIST)
    assert piece.attack_range == champion.attack_range - 1

    melee = replace(_make_champion(WeatherState.THUNDER), attack_range=1)
    melee_piece = apply_modifier(melee, WeatherState.MIST)
    assert melee_piece.attack_range == 1


def test_apply_modifier_works_with_enemy_and_flags_is_enemy() -> None:
    enemy = _make_enemy(WeatherState.SNOW)
    piece = apply_modifier(enemy, WeatherState.MIST)

    assert piece.is_enemy is True
    assert piece.move_speed == round(enemy.move_speed * 1.10)
    assert piece.threat == round(enemy.threat * 1.10)


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


def test_combat_modifier_is_deterministic() -> None:
    first = combat_modifier(WeatherState.RAIN, WeatherState.THUNDER)
    second = combat_modifier(WeatherState.RAIN, WeatherState.THUNDER)
    assert first == second


def test_combat_modifier_dataclass_is_hashable_and_frozen() -> None:
    modifier = CombatModifier(str_mult=1.10)
    with pytest.raises(Exception):
        modifier.str_mult = 2.0  # type: ignore[misc]
