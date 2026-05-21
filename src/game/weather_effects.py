from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.game.models import Champion, CombatPieceState, Enemy, WeatherState


class Relation(str, Enum):
    STRONG = "strong"
    WEAK = "weak"
    NEUTRAL = "neutral"


CYCLE_ORDER: tuple[WeatherState, ...] = (
    WeatherState.CLOUDY,
    WeatherState.MIST,
    WeatherState.SNOW,
    WeatherState.RAIN,
    WeatherState.THUNDER,
)


def _cycle_index(weather: WeatherState) -> int:
    return CYCLE_ORDER.index(weather)


def _buffed_for(weather: WeatherState) -> frozenset[WeatherState]:
    if weather == WeatherState.CLEAR:
        return frozenset()
    i = _cycle_index(weather)
    n = len(CYCLE_ORDER)
    return frozenset(
        {
            CYCLE_ORDER[(i - 1) % n],
            CYCLE_ORDER[i],
            CYCLE_ORDER[(i + 1) % n],
        }
    )


def _debuffed_for(weather: WeatherState) -> frozenset[WeatherState]:
    if weather == WeatherState.CLEAR:
        return frozenset()
    i = _cycle_index(weather)
    n = len(CYCLE_ORDER)
    return frozenset(
        {
            CYCLE_ORDER[(i + 2) % n],
            CYCLE_ORDER[(i - 2) % n],
        }
    )


BUFFED_AFFINITIES: dict[WeatherState, frozenset[WeatherState]] = {
    weather: _buffed_for(weather) for weather in WeatherState
}

DEBUFFED_AFFINITIES: dict[WeatherState, frozenset[WeatherState]] = {
    weather: _debuffed_for(weather) for weather in WeatherState
}


@dataclass(frozen=True, slots=True)
class CombatModifier:
    str_mult: float = 1.0
    int_mult: float = 1.0
    as_mult: float = 1.0
    ms_mult: float = 1.0
    mr_mult: float = 1.0
    hp_mult: float = 1.0
    armor_mult: float = 1.0
    res_mult: float = 1.0
    thr_mult: float = 1.0
    attack_range_delta: int = 0


IDENTITY = CombatModifier()


WEATHER_BUFFS: dict[WeatherState, CombatModifier] = {
    WeatherState.CLOUDY: CombatModifier(hp_mult=1.10, res_mult=1.10),
    WeatherState.MIST: CombatModifier(ms_mult=1.10, thr_mult=1.10),
    WeatherState.SNOW: CombatModifier(armor_mult=1.10, res_mult=1.10),
    WeatherState.RAIN: CombatModifier(as_mult=1.10, mr_mult=1.10),
    WeatherState.THUNDER: CombatModifier(str_mult=1.10, as_mult=1.10),
    WeatherState.CLEAR: IDENTITY,
}


WEATHER_DEBUFFS: dict[WeatherState, CombatModifier] = {
    WeatherState.CLOUDY: CombatModifier(as_mult=0.90),
    WeatherState.MIST: CombatModifier(attack_range_delta=-1),
    WeatherState.SNOW: CombatModifier(ms_mult=0.90),
    WeatherState.RAIN: CombatModifier(str_mult=0.90),
    WeatherState.THUNDER: CombatModifier(int_mult=0.90, mr_mult=0.90),
    WeatherState.CLEAR: IDENTITY,
}


def relation(affinity: WeatherState, weather: WeatherState) -> Relation:
    if affinity == WeatherState.CLEAR or weather == WeatherState.CLEAR:
        return Relation.NEUTRAL
    if affinity in BUFFED_AFFINITIES[weather]:
        return Relation.STRONG
    if affinity in DEBUFFED_AFFINITIES[weather]:
        return Relation.WEAK
    return Relation.NEUTRAL


def combat_modifier(affinity: WeatherState, weather: WeatherState) -> CombatModifier:
    rel = relation(affinity, weather)
    if rel == Relation.STRONG:
        return WEATHER_BUFFS[weather]
    if rel == Relation.WEAK:
        return WEATHER_DEBUFFS[weather]
    return IDENTITY


def shop_weight(affinity: WeatherState, weather: WeatherState) -> float:
    if affinity == WeatherState.CLEAR or weather == WeatherState.CLEAR:
        return 1.0
    if affinity == weather:
        return 2.0
    rel = relation(affinity, weather)
    if rel == Relation.STRONG:
        return 1.5
    if rel == Relation.WEAK:
        return 0.5
    return 1.0


def _scale_int(value: int, mult: float) -> int:
    return max(0, round(value * mult))


def apply_modifier(
    piece: Champion | Enemy,
    weather: WeatherState,
) -> CombatPieceState:
    modifier = combat_modifier(piece.affinity, weather)
    is_enemy = isinstance(piece, Enemy)

    max_hp = max(1, _scale_int(piece.max_hp, modifier.hp_mult))
    attack_range = max(1, piece.attack_range + modifier.attack_range_delta)

    return CombatPieceState(
        piece_id=piece.id,
        is_enemy=is_enemy,
        tier=piece.tier,
        level=piece.level,
        max_hp=max_hp,
        hp=max_hp,
        strength=_scale_int(piece.strength, modifier.str_mult),
        intelligence=_scale_int(piece.intelligence, modifier.int_mult),
        attack_speed=_scale_int(piece.attack_speed, modifier.as_mult),
        move_speed=_scale_int(piece.move_speed, modifier.ms_mult),
        mana_regen=_scale_int(piece.mana_regen, modifier.mr_mult),
        threat=_scale_int(piece.threat, modifier.thr_mult),
        armor=_scale_int(piece.armor, modifier.armor_mult),
        resistance=_scale_int(piece.resistance, modifier.res_mult),
        attack_range=attack_range,
        ability_cost=piece.ability_cost,
    )
