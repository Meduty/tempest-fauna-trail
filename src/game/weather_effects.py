"""Weather effects (T2) — directional predator/prey ring, two decoupled systems.

- **System A** (`combat_modifier` / `apply_weather`): the node weather buffs or
  debuffs each piece by its affinity, on five tiers. Applied once at combat init.
- **System B** (`damage_modifier`): a per-hit multiplier on every damage
  instance, by attacker affinity vs defender affinity. Resolved per hit in the
  combat engine — it depends on the defender, so it cannot be pre-snapshotted.

The two systems are decoupled — System A asks "does the weather suit me?",
System B asks "do I beat this enemy?". They are never summed. `CLEAR` sits
outside the ring and is inert in both. See `docs/design/tasks/t2_weather_effects_plan.md`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.game.models import Champion, CombatPieceState, Enemy, WeatherState


class RingRelation(str, Enum):
    """How one affinity/weather stands relative to another on the ring."""

    SELF = "self"
    PRIMARY_PREDATOR = "primary_predator"
    SECONDARY_PREDATOR = "secondary_predator"
    SECONDARY_PREY = "secondary_prey"
    PRIMARY_PREY = "primary_prey"
    NEUTRAL = "neutral"  # CLEAR on either side


# Directed predator/prey ring of the 5 active weathers. Member `i` preys on
# `i-1` (primary prey) and `i-2` (secondary prey); its predators are `i+1` and
# `i+2`. CLEAR sits outside the ring.
CYCLE_ORDER: tuple[WeatherState, ...] = (
    WeatherState.MIST,
    WeatherState.CLOUDY,
    WeatherState.RAIN,
    WeatherState.SNOW,
    WeatherState.THUNDER,
)

_RELATION_BY_DISTANCE: dict[int, RingRelation] = {
    0: RingRelation.SELF,
    1: RingRelation.PRIMARY_PREDATOR,
    2: RingRelation.SECONDARY_PREDATOR,
    3: RingRelation.SECONDARY_PREY,
    4: RingRelation.PRIMARY_PREY,
}


def ring_relation(a: WeatherState, b: WeatherState) -> RingRelation:
    """Relation of `a` relative to `b` on the predator/prey ring.

    `PRIMARY_PREDATOR` means `a` hunts `b` as its primary prey. `NEUTRAL`
    whenever either side is `CLEAR`.
    """
    if a == WeatherState.CLEAR or b == WeatherState.CLEAR:
        return RingRelation.NEUTRAL
    distance = (CYCLE_ORDER.index(a) - CYCLE_ORDER.index(b)) % len(CYCLE_ORDER)
    return _RELATION_BY_DISTANCE[distance]


# --- System A — node weather buff/debuff -------------------------------------

# Tier scalar: strong (self) full, medium (primary) 0.6, weak (secondary) 0.3.
# Applied to a modifier's deviation from 1.0. Buffs use all three tiers; debuffs
# only reach medium — there is no strong debuff.
_BUFF_RELATIONS = (
    RingRelation.SELF,
    RingRelation.PRIMARY_PREDATOR,
    RingRelation.SECONDARY_PREDATOR,
)
_DEBUFF_RELATIONS = (RingRelation.PRIMARY_PREY, RingRelation.SECONDARY_PREY)

TIER_SCALAR: dict[RingRelation, float] = {
    RingRelation.SELF: 1.0,
    RingRelation.PRIMARY_PREDATOR: 0.6,
    RingRelation.SECONDARY_PREDATOR: 0.3,
    RingRelation.PRIMARY_PREY: 0.6,
    RingRelation.SECONDARY_PREY: 0.3,
}


@dataclass(frozen=True, slots=True)
class CombatModifier:
    """Multiplicative stat modifier from System A. `1.0` / `0` is no change."""

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

# Strong-tier (±10%) base stat packs per weather. `combat_modifier` scales the
# deviation from 1.0 down for the medium/weak tiers.
WEATHER_BUFF_BASE: dict[WeatherState, CombatModifier] = {
    WeatherState.CLOUDY: CombatModifier(hp_mult=1.10, res_mult=1.10),
    WeatherState.MIST: CombatModifier(ms_mult=1.10, thr_mult=1.10),
    WeatherState.SNOW: CombatModifier(armor_mult=1.10, res_mult=1.10),
    WeatherState.RAIN: CombatModifier(as_mult=1.10, mr_mult=1.10),
    WeatherState.THUNDER: CombatModifier(str_mult=1.10, as_mult=1.10),
    WeatherState.CLEAR: IDENTITY,
}

WEATHER_DEBUFF_BASE: dict[WeatherState, CombatModifier] = {
    WeatherState.CLOUDY: CombatModifier(as_mult=0.90),
    WeatherState.MIST: CombatModifier(attack_range_delta=-1),
    WeatherState.SNOW: CombatModifier(ms_mult=0.90),
    WeatherState.RAIN: CombatModifier(str_mult=0.90),
    WeatherState.THUNDER: CombatModifier(int_mult=0.90, mr_mult=0.90),
    WeatherState.CLEAR: IDENTITY,
}


def _scale_modifier(modifier: CombatModifier, scalar: float) -> CombatModifier:
    """Scale a modifier's deviation from identity by `scalar`.

    `attack_range_delta` is scaled then rounded — `-1` survives the medium tier
    (`round(-0.6) == -1`) and vanishes at the weak tier (`round(-0.3) == 0`).
    """

    def dev(mult: float) -> float:
        return 1.0 + (mult - 1.0) * scalar

    return CombatModifier(
        str_mult=dev(modifier.str_mult),
        int_mult=dev(modifier.int_mult),
        as_mult=dev(modifier.as_mult),
        ms_mult=dev(modifier.ms_mult),
        mr_mult=dev(modifier.mr_mult),
        hp_mult=dev(modifier.hp_mult),
        armor_mult=dev(modifier.armor_mult),
        res_mult=dev(modifier.res_mult),
        thr_mult=dev(modifier.thr_mult),
        attack_range_delta=round(modifier.attack_range_delta * scalar),
    )


def combat_modifier(affinity: WeatherState, weather: WeatherState) -> CombatModifier:
    """System A — the node weather's stat modifier for a piece of `affinity`."""
    relation = ring_relation(affinity, weather)
    if relation == RingRelation.NEUTRAL:
        return IDENTITY
    base = (
        WEATHER_BUFF_BASE[weather]
        if relation in _BUFF_RELATIONS
        else WEATHER_DEBUFF_BASE[weather]
    )
    scalar = TIER_SCALAR[relation]
    if scalar == 1.0:
        return base
    return _scale_modifier(base, scalar)


# --- System B — affinity damage triangle -------------------------------------

DAMAGE_MULT: dict[RingRelation, float] = {
    RingRelation.PRIMARY_PREDATOR: 1.10,
    RingRelation.SECONDARY_PREDATOR: 1.05,
    RingRelation.SELF: 1.00,
    RingRelation.NEUTRAL: 1.00,
    RingRelation.SECONDARY_PREY: 0.95,
    RingRelation.PRIMARY_PREY: 0.90,
}


def damage_modifier(
    attacker_affinity: WeatherState, defender_affinity: WeatherState
) -> float:
    """System B — per-hit damage multiplier for attacker vs defender affinity."""
    return DAMAGE_MULT[ring_relation(attacker_affinity, defender_affinity)]


# --- Shop drop weight (prep phase) -------------------------------------------

SHOP_WEIGHT: dict[RingRelation, float] = {
    RingRelation.SELF: 2.0,
    RingRelation.PRIMARY_PREDATOR: 1.5,
    RingRelation.SECONDARY_PREDATOR: 1.2,
    RingRelation.NEUTRAL: 1.0,
    RingRelation.SECONDARY_PREY: 0.8,
    RingRelation.PRIMARY_PREY: 0.6,
}


def shop_weight(affinity: WeatherState, weather: WeatherState) -> float:
    """Prep-shop pull weight for `affinity` given the upcoming node weather."""
    return SHOP_WEIGHT[ring_relation(affinity, weather)]


# --- Combat-init bridge ------------------------------------------------------


def _scale_int(value: int, mult: float) -> int:
    return max(0, round(value * mult))


def apply_weather(piece: Champion | Enemy, weather: WeatherState) -> CombatPieceState:
    """Snapshot a roster piece into a `CombatPieceState` with System A applied.

    Copies `affinity` onto the snapshot so the combat engine can resolve
    System B (`damage_modifier`) per hit. Does not mutate `piece`.
    """
    modifier = combat_modifier(piece.affinity, weather)
    is_enemy = isinstance(piece, Enemy)

    max_hp = max(1, _scale_int(piece.max_hp, modifier.hp_mult))
    attack_range = max(1, piece.attack_range + modifier.attack_range_delta)

    return CombatPieceState(
        piece_id=piece.id,
        is_enemy=is_enemy,
        affinity=piece.affinity,
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
        crit_chance=piece.crit_chance,
        penetration=piece.penetration,
        penetration_pct=piece.penetration_pct,
    )
