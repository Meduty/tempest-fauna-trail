from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.game.models import Champion, Enemy, WeatherState
from src.game.scaling import (
    PRIMARY_SCALABLE_STATS,
    SECONDARY_EXPONENT,
    SECONDARY_SCALABLE_STATS,
    level_scale_stats,
    stat_multiplier,
)

_BASE_STATS: dict[str, Any] = {
    "max_hp": 600,
    "strength": 50,
    "intelligence": 50,
    "armor": 25,
    "resistance": 25,
    "attack_speed": 100,
    "mana_regen": 100,
    "move_speed": 100,
    "threat": 60,
    "attack_range": 2,
    "ability_cost": 36_000,
    "crit_chance": 0.0,
    "penetration": 0,
    "penetration_pct": 0.0,
}

_PRIMARY_STAT: dict[str, dict[str, float]] = {
    "str": {"strength": 1.8, "intelligence": 0.2},
    "int": {"strength": 0.2, "intelligence": 1.8},
    "hybrid": {"strength": 1.0, "intelligence": 1.0},
}

_RANGE: dict[str, dict[str, Any]] = {
    "melee": {
        "max_hp": 1.0,
        "armor": 1.3,
        "resistance": 1.2,
        "attack_speed": 1.1,
        "attack_range": 1,
    },
    "ranged": {
        "max_hp": 0.9,
        "armor": 0.8,
        "resistance": 0.8,
        "attack_speed": 0.9,
        "attack_range": 3,
    },
}

_DURABILITY: dict[str, dict[str, float]] = {
    "squishy": {
        "max_hp": 0.65,
        "armor": 0.65,
        "resistance": 0.65,
        "strength": 1.25,
        "intelligence": 1.25,
        "threat": 0.7,
    },
    "hybrid": {
        "max_hp": 1.0,
        "armor": 1.0,
        "resistance": 1.0,
        "strength": 1.0,
        "intelligence": 1.0,
        "threat": 1.0,
    },
    "tanky_hp": {
        "max_hp": 1.8,
        "armor": 0.8,
        "resistance": 0.8,
        "strength": 0.55,
        "intelligence": 0.55,
        "threat": 1.4,
    },
    "tanky_arm": {
        "max_hp": 0.9,
        "armor": 2.0,
        "resistance": 2.0,
        "strength": 0.55,
        "intelligence": 0.55,
        "threat": 1.4,
    },
}

_PLAYSTYLE: dict[str, dict[str, float]] = {
    "auto": {"attack_speed": 1.3, "mana_regen": 0.6, "threat": 1.0},
    "hybrid": {"attack_speed": 1.0, "mana_regen": 1.0, "threat": 1.0},
    "ability": {"attack_speed": 0.75, "mana_regen": 1.5, "threat": 0.85},
}

# Speed axis also drives `move_speed` (speedy ↑, heavy ↓, hybrid baseline 90).
_SPEED: dict[str, dict[str, float]] = {
    "speedy": {"attack_speed": 1.2, "resistance": 1.2, "primary_stat": 0.9, "move_speed": 1.15},
    "hybrid": {"attack_speed": 1.0, "resistance": 1.0, "primary_stat": 1.0, "move_speed": 1.0},
    "heavy": {"attack_speed": 0.85, "resistance": 0.85, "primary_stat": 1.12, "move_speed": 0.85},
}

# Intent stat-bias (T.32, V.33). Applied at one fixed point (after axis + speed,
# before the tier round()). `hybrid` is identity → byte-identical to pre-change.
# Keeps the HP·DPS power proxy within ±10% (re-flavour, not stealth buff);
# `threat` is off the power budget by design (B.6).
_INTENT: dict[str, dict[str, float]] = {
    "damage": {
        "strength": 1.08,
        "intelligence": 1.08,
        "attack_speed": 1.05,
        "max_hp": 0.96,
        "armor": 0.97,
        "resistance": 0.97,
        "mana_regen": 0.97,
        "threat": 0.92,
    },
    "utility": {
        "strength": 0.94,
        "intelligence": 0.94,
        "attack_speed": 0.96,
        "max_hp": 1.08,
        "armor": 1.05,
        "resistance": 1.05,
        "mana_regen": 1.08,
        "threat": 1.10,
    },
    "hybrid": {},
}

# Ability cost is uniform — demoted from a per-unit Def field to a constant (T.32).
# T.33: lifted 36_000→300_000 alongside mana_regen 10→100 (V.35 baseline parity).
# 300_000 (vs cadence-neutral 360_000) bakes a ~20% mage buff. FLAT (never scaled).
_ABILITY_COST = 300_000
# Valid override targets — every base stat key, incl. premium crit/penetration (V.33).
ALL_STAT_KEYS = frozenset(_BASE_STATS)
INTENT_VALUES = frozenset(_INTENT)
# The 8 coarse role titles `classify_role` can return (V.32).
ROLE_TITLES = frozenset(
    {"tank", "bruiser", "support", "mage", "marksman", "assassin", "swashbuckler", "spellblade"}
)


def classify_role(
    stat: str,
    reach: str,
    durability: str,
    playstyle: str,
    speed: str,
    intent: str,
) -> str:
    """Coarse 8-role title — a pure deterministic function of the 6 axes (V.32).

    Replaces the legacy flat `_ROLE_FROM_AXES[stat][reach]` map, which ignored
    durability/playstyle/speed/intent (B.13).
    """
    tanky = durability in ("tanky_hp", "tanky_arm")
    caster = (playstyle == "ability") or (stat == "int")
    if tanky:
        return "bruiser" if intent == "damage" else "tank"
    if intent == "utility":
        return "support"
    if stat == "hybrid" and intent == "hybrid" and not caster:
        return "spellblade"
    if reach == "melee":
        return "assassin" if caster else "swashbuckler"
    return "mage" if caster else "marksman"


def build_role_code(
    stat: str,
    reach: str,
    durability: str,
    playstyle: str,
    speed: str,
    intent: str,
) -> str:
    """Fine descriptor — the 6 axis tokens in fixed order, omitting every `hybrid`.

    Non-positional tag-set (V.32): consumed by membership/substring, never by
    index. `reach` is never `hybrid`, so the code is never empty.
    """
    toks = [stat, reach, durability, playstyle, speed, intent]
    return "-".join(t for t in toks if t != "hybrid")


KINSHIP_TAGS = frozenset({"Beast", "Skyborn", "Scaled", "Tidekin", "Swarm", "Spirit"})
CALLING_TAGS = frozenset(
    {
        "Skirmisher",
        "Warden",
        "Mender",
        "Mystic",
        "Bulwark",
        "Drifter",
        "Harbinger",
        "Emissary",
        "Primordial",
        "Guardian",
        "Bruiser",
        "Hunter",
        "Stalker",
        "Trickster",
        "Channeler",
    }
)
ALL_TRAIT_TAGS = KINSHIP_TAGS | CALLING_TAGS
ENEMY_TAGS = frozenset({"human", "beast", "corrupted", "machine", "spirit"})
_ENEMY_ROSTER_TAGS = ENEMY_TAGS


@dataclass
class ChampionDef:
    id: str
    name: str
    affinity: WeatherState
    tier: int
    stat: str
    reach: str
    durability: str
    playstyle: str
    intent: str
    traits: list[str]
    active_ability: str
    passive_ability: str
    speed: str = "hybrid"
    stat_overrides: dict[str, int] = field(default_factory=dict)


@dataclass
class EnemyDef:
    id: str
    name: str
    affinity: WeatherState
    tier: int
    stat: str
    reach: str
    durability: str
    playstyle: str
    intent: str
    tags: frozenset[str]
    active_ability: str
    passive_ability: str
    speed: str = "hybrid"
    stat_overrides: dict[str, int] = field(default_factory=dict)


def compose_stats(
    stat: str,
    reach: str,
    durability: str,
    playstyle: str,
    speed: str,
    intent: str,
    tier: int,
) -> dict[str, Any]:
    """Generate **every** combat stat from the 6 axes (V.33).

    Order: axis multipliers → reach attack_range → speed (attack_speed/resistance,
    primary stat, move_speed) → intent stat-bias (one fixed point, before the tier
    round()) → ability_cost constant → tier-scale the 5 power stats.
    """
    if stat not in _PRIMARY_STAT:
        raise ValueError(f"Unknown stat axis value: {stat!r}")
    if reach not in _RANGE:
        raise ValueError(f"Unknown reach axis value: {reach!r}")
    if durability not in _DURABILITY:
        raise ValueError(f"Unknown durability axis value: {durability!r}")
    if playstyle not in _PLAYSTYLE:
        raise ValueError(f"Unknown playstyle axis value: {playstyle!r}")
    if speed not in _SPEED:
        raise ValueError(f"Unknown speed axis value: {speed!r}")
    if intent not in _INTENT:
        raise ValueError(f"Unknown intent axis value: {intent!r}")

    stats = dict(_BASE_STATS)
    for axis_weights in (
        _PRIMARY_STAT[stat],
        _RANGE[reach],
        _DURABILITY[durability],
        _PLAYSTYLE[playstyle],
    ):
        for k, v in axis_weights.items():
            if k != "attack_range":
                stats[k] = stats[k] * v

    # Range sets a discrete board-space value instead of scaling a base range.
    stats["attack_range"] = _RANGE[reach]["attack_range"]
    speed_weights = _SPEED[speed]
    if playstyle == "ability":
        stats["resistance"] = stats["resistance"] * speed_weights["resistance"]
    else:
        stats["attack_speed"] = stats["attack_speed"] * speed_weights["attack_speed"]

    if stat in {"str", "hybrid"}:
        stats["strength"] = stats["strength"] * speed_weights["primary_stat"]
    if stat in {"int", "hybrid"}:
        stats["intelligence"] = stats["intelligence"] * speed_weights["primary_stat"]
    stats["move_speed"] = stats["move_speed"] * speed_weights["move_speed"]

    # Intent stat-bias — single fixed point, before the tier round() (V.33).
    for k, v in _INTENT[intent].items():
        stats[k] = stats[k] * v

    stats["ability_cost"] = _ABILITY_COST

    # PRIMARY: sqrt(power) tier-scale, rounded to int.
    sp = stat_multiplier(tier, 1)
    for k in PRIMARY_SCALABLE_STATS:
        stats[k] = round(stats[k] * sp)
    # SECONDARY: gentle tier-scale. milli_AS captures sub-integer attack_speed for
    # the canonical sort order (V.34) BEFORE rounding; all speeds then stored int.
    ss = stat_multiplier(tier, 1, SECONDARY_EXPONENT)
    for k in SECONDARY_SCALABLE_STATS:
        stats[k] = stats[k] * ss
    stats["milli_AS"] = round(stats["attack_speed"] * 1000)
    for k in SECONDARY_SCALABLE_STATS:
        stats[k] = round(stats[k])

    return stats


def _assert_budget(d: Any, base: dict[str, Any]) -> None:
    scalable = PRIMARY_SCALABLE_STATS
    budget = sum(base[k] for k in scalable)
    drift = sum(d.stat_overrides.get(k, 0) for k in scalable)
    if budget > 0:
        drift_ratio = drift / budget
        assert abs(drift_ratio) <= 0.15, (
            f"{d.id}: stat_overrides drift {drift_ratio:.1%} exceeds ±15% budget"
        )


def _apply_stat_overrides(base: dict[str, Any], overrides: dict[str, int]) -> dict[str, Any]:
    unknown = set(overrides) - ALL_STAT_KEYS
    if unknown:
        raise ValueError(f"Unknown stat_overrides keys: {sorted(unknown)}")
    return {k: base[k] + overrides.get(k, 0) for k in base}


def _build_champion(d: ChampionDef, level: int = 1) -> Champion:
    base = compose_stats(
        d.stat, d.reach, d.durability, d.playstyle, d.speed, d.intent, d.tier
    )
    _assert_budget(d, base)
    # Overrides applied after tier-scale, before level-scale (V.33): scalable
    # overrides level-scale; non-scaled/premium ones stay flat.
    base = _apply_stat_overrides(base, d.stat_overrides)
    level_scale_stats(base, d.tier, level)
    return Champion(
        id=d.id,
        name=d.name,
        affinity=d.affinity,
        role=classify_role(d.stat, d.reach, d.durability, d.playstyle, d.speed, d.intent),
        role_code=build_role_code(d.stat, d.reach, d.durability, d.playstyle, d.speed, d.intent),
        intent=d.intent,
        tier=d.tier,
        level=level,
        max_hp=max(1, base["max_hp"]),
        strength=max(0, base["strength"]),
        intelligence=max(0, base["intelligence"]),
        armor=max(0, base["armor"]),
        resistance=max(0, base["resistance"]),
        attack_speed=round(base["attack_speed"]),
        milli_AS=round(base["milli_AS"]),
        mana_regen=round(base["mana_regen"]),
        move_speed=round(base["move_speed"]),
        threat=round(base["threat"]),
        attack_range=base["attack_range"],
        ability_cost=base["ability_cost"],
        traits=d.traits,
        active_ability=d.active_ability,
        passive_ability=d.passive_ability,
        crit_chance=base["crit_chance"],
        penetration=base["penetration"],
        penetration_pct=base["penetration_pct"],
    )


def _build_enemy(d: EnemyDef, level: int = 1) -> Enemy:
    base = compose_stats(
        d.stat, d.reach, d.durability, d.playstyle, d.speed, d.intent, d.tier
    )
    _assert_budget(d, base)
    base = _apply_stat_overrides(base, d.stat_overrides)
    level_scale_stats(base, d.tier, level)
    return Enemy(
        id=d.id,
        name=d.name,
        affinity=d.affinity,
        role=classify_role(d.stat, d.reach, d.durability, d.playstyle, d.speed, d.intent),
        role_code=build_role_code(d.stat, d.reach, d.durability, d.playstyle, d.speed, d.intent),
        intent=d.intent,
        tier=d.tier,
        level=level,
        max_hp=max(1, base["max_hp"]),
        strength=max(0, base["strength"]),
        intelligence=max(0, base["intelligence"]),
        armor=max(0, base["armor"]),
        resistance=max(0, base["resistance"]),
        attack_speed=round(base["attack_speed"]),
        milli_AS=round(base["milli_AS"]),
        mana_regen=round(base["mana_regen"]),
        move_speed=round(base["move_speed"]),
        threat=round(base["threat"]),
        attack_range=base["attack_range"],
        ability_cost=base["ability_cost"],
        active_ability=d.active_ability,
        passive_ability=d.passive_ability,
        crit_chance=base["crit_chance"],
        penetration=base["penetration"],
        penetration_pct=base["penetration_pct"],
    )


def _champion_def(
    id: str,
    name: str,
    affinity: WeatherState,
    tier: int,
    reach: str,
    traits: list[str],
    *,
    stat: str = "hybrid",
    durability: str = "hybrid",
    playstyle: str = "hybrid",
    intent: str = "hybrid",
    speed: str = "hybrid",
    stat_overrides: dict[str, int] | None = None,
) -> ChampionDef:
    # Every axis defaults to `hybrid` and is named only when it deviates (like
    # `speed`); `reach` (melee/ranged — no hybrid value) is the one positional axis.
    return ChampionDef(
        id=id,
        name=name,
        affinity=affinity,
        tier=tier,
        stat=stat,
        reach=reach,
        durability=durability,
        playstyle=playstyle,
        intent=intent,
        speed=speed,
        traits=traits,
        active_ability=f"{id}.active",
        passive_ability=f"{id}.passive",
        stat_overrides=stat_overrides or {},
    )


def _enemy_def(
    id: str,
    name: str,
    affinity: WeatherState,
    tier: int,
    reach: str,
    tags: frozenset[str],
    *,
    stat: str = "hybrid",
    durability: str = "hybrid",
    playstyle: str = "hybrid",
    intent: str = "hybrid",
    speed: str = "hybrid",
    stat_overrides: dict[str, int] | None = None,
) -> EnemyDef:
    return EnemyDef(
        id=id,
        name=name,
        affinity=affinity,
        tier=tier,
        stat=stat,
        reach=reach,
        durability=durability,
        playstyle=playstyle,
        intent=intent,
        speed=speed,
        tags=tags,
        active_ability=f"{id}.active",
        passive_ability=f"{id}.passive",
        stat_overrides=stat_overrides or {},
    )


_CHAMPION_DEFS: tuple[ChampionDef, ...] = (
    _champion_def("champ_dawnwisp", "Dawnwisp", WeatherState.CLEAR, 1, "ranged", ["Spirit", "Mender"], stat="int", playstyle="ability", intent="utility"),
    _champion_def("champ_veldt_pronghorn", "Veldt Pronghorn", WeatherState.CLEAR, 2, "melee", ["Beast", "Skirmisher"], stat="str", playstyle="auto", intent="damage"),
    _champion_def("champ_ember_salamander", "Ember Salamander", WeatherState.CLEAR, 3, "ranged", ["Scaled", "Mystic"], stat="int", durability="squishy", playstyle="ability", intent="damage"),
    _champion_def("champ_goldcrest_lark", "Goldcrest Lark", WeatherState.CLEAR, 4, "ranged", ["Skyborn", "Warden"], stat="int", playstyle="ability", intent="utility"),
    _champion_def("champ_aegis_tortoise", "Aegis Tortoise", WeatherState.CLEAR, 5, "melee", ["Scaled", "Guardian"], stat="str", durability="tanky_arm", intent="utility", speed="heavy"),
    _champion_def("champ_sunmane_lion", "Sunmane Lion", WeatherState.CLEAR, 6, "melee", ["Beast", "Bruiser"], stat="str", playstyle="auto", intent="utility"),
    _champion_def("champ_goldhide_rhino", "Goldhide Rhino", WeatherState.CLEAR, 7, "melee", ["Beast", "Bruiser", "Mender"], durability="tanky_hp", speed="heavy"),
    _champion_def("champ_mirage_caracal", "Mirage Caracal", WeatherState.CLEAR, 8, "melee", ["Beast", "Stalker"], stat="int", durability="squishy", playstyle="ability", intent="damage", speed="speedy"),
    _champion_def("champ_sunspear_falcon", "Sunspear Falcon", WeatherState.CLEAR, 9, "ranged", ["Skyborn", "Hunter"], stat="str", playstyle="auto", intent="damage"),
    _champion_def("champ_aurion", "Aurion, the First Dawn", WeatherState.CLEAR, 10, "ranged", ["Spirit", "Primordial", "Channeler"]),
    _champion_def("champ_springfrog", "Springfrog", WeatherState.RAIN, 1, "ranged", ["Tidekin", "Mender"], stat="int", playstyle="ability", intent="utility"),
    _champion_def("champ_reedbank_otter", "Reedbank Otter", WeatherState.RAIN, 2, "melee", ["Tidekin", "Skirmisher"], stat="str", playstyle="auto", intent="damage", speed="speedy"),
    _champion_def("champ_torrent_heron", "Torrent Heron", WeatherState.RAIN, 3, "ranged", ["Skyborn", "Mystic"], stat="str", durability="squishy", playstyle="ability", intent="damage"),
    _champion_def("champ_grovekeeper_tapir", "Grovekeeper Tapir", WeatherState.RAIN, 4, "melee", ["Beast", "Bruiser", "Mender"], durability="tanky_hp"),
    _champion_def("champ_coral_colossus", "Coral Colossus", WeatherState.RAIN, 5, "melee", ["Tidekin", "Guardian", "Mender"], stat="str", durability="tanky_hp", intent="utility", speed="heavy"),
    _champion_def("champ_marsh_thrush", "Marsh Thrush", WeatherState.RAIN, 6, "ranged", ["Skyborn", "Warden"], stat="int", playstyle="ability", intent="utility"),
    _champion_def("champ_mirewarden_toad", "Mirewarden Toad", WeatherState.RAIN, 7, "melee", ["Tidekin", "Guardian"], stat="int", durability="tanky_hp", playstyle="ability", intent="utility"),
    _champion_def("champ_glade_heron", "Glade Heron", WeatherState.RAIN, 8, "ranged", ["Skyborn", "Hunter", "Trickster"], stat="int", playstyle="ability", intent="damage", stat_overrides={"resistance": 40}),
    _champion_def("champ_riptide_caiman", "Riptide Caiman", WeatherState.RAIN, 9, "melee", ["Scaled", "Stalker"], stat="str", durability="squishy", playstyle="auto", intent="damage", speed="speedy"),
    _champion_def("champ_nerei", "Nerei, the Floodmother", WeatherState.RAIN, 10, "ranged", ["Spirit", "Primordial", "Channeler"]),
    _champion_def("champ_snowpelt_cub", "Snowpelt Cub", WeatherState.SNOW, 1, "melee", ["Beast", "Guardian"], stat="str", durability="tanky_hp", intent="utility", speed="heavy"),
    _champion_def("champ_wintermoth", "Wintermoth", WeatherState.SNOW, 2, "ranged", ["Swarm", "Warden"], stat="int", playstyle="ability", intent="utility"),
    _champion_def("champ_permafrost_walrus", "Permafrost Walrus", WeatherState.SNOW, 3, "ranged", ["Tidekin", "Mystic"], stat="str", durability="squishy", playstyle="ability", intent="damage"),
    _champion_def("champ_hoarfrost_owl", "Hoarfrost Owl", WeatherState.SNOW, 4, "ranged", ["Skyborn", "Warden"], stat="int", playstyle="ability", intent="utility"),
    _champion_def("champ_frostplate_tortoise", "Frostplate Tortoise", WeatherState.SNOW, 5, "melee", ["Scaled", "Guardian"], stat="str", durability="tanky_arm", intent="utility"),
    _champion_def("champ_iceclaw_lynx", "Iceclaw Lynx", WeatherState.SNOW, 6, "melee", ["Beast", "Skirmisher", "Trickster"], stat="int", playstyle="ability", intent="damage", speed="speedy"),
    _champion_def("champ_glacierback_mammoth", "Glacierback Mammoth", WeatherState.SNOW, 7, "melee", ["Beast", "Bruiser"], durability="tanky_hp", speed="heavy"),
    _champion_def("champ_frostfang_wolverine", "Frostfang Wolverine", WeatherState.SNOW, 8, "melee", ["Beast", "Stalker"], stat="str", durability="squishy", playstyle="auto", intent="damage"),
    _champion_def("champ_frostquill_porcupine", "Frostquill Porcupine", WeatherState.SNOW, 9, "ranged", ["Beast", "Hunter", "Trickster"], stat="str", playstyle="auto", intent="damage"),
    _champion_def("champ_borealis", "Borealis, the Pale Aurora", WeatherState.SNOW, 10, "ranged", ["Spirit", "Primordial", "Mystic"]),
    _champion_def("champ_pebbleback_pangolin", "Pebbleback Pangolin", WeatherState.CLOUDY, 1, "melee", ["Scaled", "Guardian"], stat="str", durability="tanky_hp", intent="utility"),
    _champion_def("champ_dusk_bat", "Dusk Bat", WeatherState.CLOUDY, 2, "ranged", ["Beast", "Trickster"], stat="int", playstyle="ability", intent="utility", speed="speedy"),
    _champion_def("champ_boulderhide_skink", "Boulderhide Skink", WeatherState.CLOUDY, 3, "ranged", ["Scaled", "Mystic"], stat="str", durability="squishy", playstyle="ability", intent="damage"),
    _champion_def("champ_geode_beetle", "Geode Beetle", WeatherState.CLOUDY, 4, "ranged", ["Swarm", "Warden"], stat="int", playstyle="ability", intent="utility"),
    _champion_def("champ_duskstep_marten", "Duskstep Marten", WeatherState.CLOUDY, 5, "melee", ["Beast", "Skirmisher", "Stalker"], stat="int", playstyle="ability", intent="damage"),
    _champion_def("champ_granite_gorilla", "Granite Gorilla", WeatherState.CLOUDY, 6, "melee", ["Beast", "Guardian"], stat="int", durability="tanky_hp", playstyle="ability", intent="utility", speed="heavy"),
    _champion_def("champ_eclipse_jaguar", "Eclipse Jaguar", WeatherState.CLOUDY, 7, "ranged", ["Beast", "Stalker", "Channeler"]),
    _champion_def("champ_nightglass_mantis", "Nightglass Mantis", WeatherState.CLOUDY, 8, "melee", ["Swarm", "Stalker"], stat="int", durability="squishy", playstyle="ability", intent="damage", speed="speedy"),
    _champion_def("champ_cliffeyrie_eagle", "Cliffeyrie Eagle", WeatherState.CLOUDY, 9, "ranged", ["Skyborn", "Hunter"], stat="str", playstyle="auto", intent="damage"),
    _champion_def("champ_umbra", "Umbra, the Mountain's Shadow", WeatherState.CLOUDY, 10, "ranged", ["Spirit", "Primordial", "Stalker"]),
    _champion_def("champ_lostlight_wisp", "Lostlight Wisp", WeatherState.MIST, 1, "ranged", ["Spirit", "Mender"], stat="int", playstyle="ability", intent="utility"),
    _champion_def("champ_will_o_fawn", "Will-o-Fawn", WeatherState.MIST, 2, "ranged", ["Spirit", "Mystic"], stat="int", durability="squishy", playstyle="ability", intent="damage", speed="speedy"),
    _champion_def("champ_phantom_lynx", "Phantom Lynx", WeatherState.MIST, 3, "melee", ["Spirit", "Stalker"], stat="int", durability="squishy", playstyle="ability", intent="damage"),
    _champion_def("champ_hollow_elk", "Hollow Elk", WeatherState.MIST, 4, "melee", ["Spirit", "Guardian", "Channeler"], stat="int", durability="tanky_hp", playstyle="ability", intent="utility", speed="heavy"),
    _champion_def("champ_fogveil_moth", "Fogveil Moth", WeatherState.MIST, 5, "ranged", ["Swarm", "Trickster"], stat="int", playstyle="ability", intent="utility"),
    _champion_def("champ_wraithorn_stag", "Wraithorn Stag", WeatherState.MIST, 6, "melee", ["Spirit", "Bruiser"], stat="str", playstyle="auto", intent="utility"),
    _champion_def("champ_marshghast_boar", "Marshghast Boar", WeatherState.MIST, 7, "melee", ["Spirit", "Bruiser", "Stalker"], durability="tanky_hp"),
    _champion_def("champ_veilfang_wolf", "Veilfang Wolf", WeatherState.MIST, 8, "melee", ["Spirit", "Skirmisher"], stat="int", playstyle="ability", intent="damage", speed="speedy"),
    _champion_def("champ_spectral_heron", "Spectral Heron", WeatherState.MIST, 9, "ranged", ["Spirit", "Hunter"], stat="int", playstyle="ability", intent="damage"),
    _champion_def("champ_mournhollow", "Mournhollow, the Pale Stag", WeatherState.MIST, 10, "ranged", ["Spirit", "Primordial", "Channeler"]),
    _champion_def("champ_sparkfly", "Sparkfly", WeatherState.THUNDER, 1, "ranged", ["Swarm", "Trickster"], stat="int", playstyle="ability", intent="utility"),
    _champion_def("champ_thunderhoof_colt", "Thunderhoof Colt", WeatherState.THUNDER, 2, "melee", ["Beast", "Skirmisher"], stat="str", playstyle="auto", intent="damage", speed="speedy"),
    _champion_def("champ_voltscale_mamba", "Voltscale Mamba", WeatherState.THUNDER, 3, "melee", ["Scaled", "Stalker"], stat="str", durability="squishy", playstyle="auto", intent="damage"),
    _champion_def("champ_coppercrest_stork", "Coppercrest Stork", WeatherState.THUNDER, 4, "ranged", ["Skyborn", "Warden"], stat="int", playstyle="ability", intent="utility"),
    _champion_def("champ_thunderhide_bison", "Thunderhide Bison", WeatherState.THUNDER, 5, "melee", ["Beast", "Guardian"], stat="str", durability="tanky_arm", intent="utility", speed="heavy"),
    _champion_def("champ_tempest_eel", "Tempest Eel", WeatherState.THUNDER, 6, "ranged", ["Tidekin", "Mystic"], stat="int", durability="squishy", playstyle="ability", intent="damage"),
    _champion_def("champ_voltmane_jackal", "Voltmane Jackal", WeatherState.THUNDER, 7, "ranged", ["Beast", "Skirmisher", "Channeler"]),
    _champion_def("champ_thunderclap_gorilla", "Thunderclap Gorilla", WeatherState.THUNDER, 8, "melee", ["Beast", "Bruiser"], stat="str", playstyle="auto", intent="utility"),
    _champion_def("champ_storm_eagle", "Storm Eagle", WeatherState.THUNDER, 9, "ranged", ["Skyborn", "Hunter", "Channeler"], stat="int", playstyle="ability", intent="damage", speed="speedy"),
    _champion_def("champ_aerion", "Aerion, the Skybreaker", WeatherState.THUNDER, 10, "ranged", ["Spirit", "Primordial", "Hunter"]),
)


_ENEMY_DEFS: tuple[EnemyDef, ...] = (
    _enemy_def("enemy_conscript", "Conscript", WeatherState.CLEAR, 1, "melee", frozenset({"human"}), stat="str", playstyle="auto", intent="damage"),
    _enemy_def("enemy_levyman", "Levyman", WeatherState.CLEAR, 1, "melee", frozenset({"human"}), stat="str", durability="tanky_hp", intent="utility"),
    _enemy_def("enemy_picket", "Picket", WeatherState.CLEAR, 1, "ranged", frozenset({"human"}), stat="str", playstyle="auto", intent="damage"),
    _enemy_def("enemy_stretcher_hand", "Stretcher-Hand", WeatherState.CLEAR, 1, "ranged", frozenset({"human"}), stat="int", playstyle="ability", intent="utility"),
    _enemy_def("enemy_signal_drummer", "Signal Drummer", WeatherState.CLEAR, 1, "ranged", frozenset({"human"}), stat="int", playstyle="ability", intent="utility"),
    _enemy_def("enemy_pikeman", "Pikeman", WeatherState.CLEAR, 2, "melee", frozenset({"human"}), stat="str", durability="tanky_arm", intent="utility"),
    _enemy_def("enemy_crossbow_levy", "Crossbow Levy", WeatherState.CLEAR, 2, "ranged", frozenset({"human"}), stat="str", playstyle="auto", intent="damage"),
    _enemy_def("enemy_field_medic", "Field Medic", WeatherState.CLEAR, 2, "ranged", frozenset({"human"}), stat="int", playstyle="ability", intent="utility"),
    _enemy_def("enemy_powder_sapper", "Powder Sapper", WeatherState.CLEAR, 2, "ranged", frozenset({"human"}), stat="str", durability="squishy", playstyle="ability", intent="damage"),
    _enemy_def("enemy_sergeant_at_arms", "Sergeant-at-Arms", WeatherState.CLEAR, 3, "melee", frozenset({"human"}), durability="tanky_hp"),
    _enemy_def("enemy_field_chaplain", "Field Chaplain", WeatherState.CLEAR, 3, "ranged", frozenset({"human"}), stat="int", playstyle="ability", intent="utility"),
    _enemy_def("enemy_standard_bearer", "Standard Bearer", WeatherState.CLEAR, 3, "ranged", frozenset({"human"}), stat="int", playstyle="ability", intent="utility"),
    _enemy_def("enemy_heavy_knight", "Heavy Knight", WeatherState.CLEAR, 4, "melee", frozenset({"human"}), stat="str", durability="tanky_hp", intent="utility"),
    _enemy_def("enemy_steam_engineer", "Steam Engineer", WeatherState.CLEAR, 4, "ranged", frozenset({"human", "machine"}), stat="int", durability="squishy", playstyle="ability", intent="damage"),
    _enemy_def("enemy_company_guard", "Company Guard", WeatherState.CLEAR, 4, "melee", frozenset({"human"}), durability="tanky_hp"),
    _enemy_def("enemy_battlemage", "Battlemage", WeatherState.CLEAR, 5, "ranged", frozenset({"human"}), stat="int", durability="squishy", playstyle="ability", intent="damage"),
    _enemy_def("enemy_gunslinger", "Gunslinger", WeatherState.CLEAR, 5, "ranged", frozenset({"human"}), stat="str", playstyle="auto", intent="damage"),
    _enemy_def("enemy_company_captain", "Company Captain", WeatherState.CLEAR, 5, "ranged", frozenset({"human"}), stat="int", playstyle="ability", intent="utility"),
    _enemy_def("enemy_steam_knight", "Steam Knight", WeatherState.CLEAR, 6, "melee", frozenset({"human", "machine"}), stat="str", playstyle="auto", intent="utility"),
    _enemy_def("enemy_riflemaster", "Riflemaster", WeatherState.CLEAR, 6, "ranged", frozenset({"human"}), stat="str", playstyle="auto", intent="damage"),
    _enemy_def("enemy_inquisitor", "Inquisitor", WeatherState.CLEAR, 6, "ranged", frozenset({"human"})),
    _enemy_def("enemy_hexblade_officer", "Hexblade Officer", WeatherState.CLEAR, 6, "melee", frozenset({"human"}), stat="int", playstyle="ability", intent="damage"),
    _enemy_def("enemy_lord_commander", "Lord Commander", WeatherState.CLEAR, 7, "melee", frozenset({"human"}), stat="str", playstyle="auto", intent="utility"),
    _enemy_def("enemy_iron_maiden", "Iron Maiden", WeatherState.CLEAR, 7, "melee", frozenset({"human", "machine"}), durability="tanky_hp"),
    _enemy_def("enemy_cannoneer", "Cannoneer", WeatherState.CLEAR, 8, "ranged", frozenset({"human", "machine"}), stat="str", playstyle="auto", intent="damage"),
    _enemy_def("enemy_spymaster", "Spymaster", WeatherState.CLEAR, 8, "melee", frozenset({"human"}), stat="int", durability="squishy", playstyle="ability", intent="damage"),
    _enemy_def("enemy_hierarch", "Hierarch", WeatherState.CLEAR, 8, "ranged", frozenset({"human"}), stat="int", playstyle="ability", intent="utility"),
    _enemy_def("enemy_arcanist", "Arcanist", WeatherState.CLEAR, 9, "ranged", frozenset({"human"}), stat="int", durability="squishy", playstyle="ability", intent="damage"),
    _enemy_def("enemy_archmagus_imperator", "Archmagus Imperator", WeatherState.CLEAR, 9, "ranged", frozenset({"human"})),
    _enemy_def("enemy_grand_marshal", "Grand Marshal", WeatherState.CLEAR, 10, "melee", frozenset({"human"}), stat="str", playstyle="auto", intent="damage"),
    _enemy_def("enemy_blight_lurker", "Blight Lurker", WeatherState.RAIN, 3, "melee", frozenset({"corrupted", "beast"}), stat="str", durability="tanky_hp", intent="utility"),
    _enemy_def("enemy_drowned_siren", "Drowned Siren", WeatherState.RAIN, 4, "ranged", frozenset({"corrupted", "spirit"}), stat="int", durability="squishy", playstyle="ability", intent="damage"),
    _enemy_def("enemy_brineblight_berserker", "Brineblight Berserker", WeatherState.RAIN, 5, "melee", frozenset({"corrupted", "beast"}), stat="str", playstyle="auto", intent="damage"),
    _enemy_def("enemy_dredge_hulk", "Dredge-Hulk", WeatherState.RAIN, 7, "melee", frozenset({"corrupted", "beast", "machine"}), durability="tanky_hp"),
    _enemy_def("enemy_maw_of_the_drowned", "Maw of the Drowned", WeatherState.RAIN, 9, "ranged", frozenset({"corrupted", "beast"})),
    _enemy_def("enemy_flood_tyrant", "Flood Tyrant", WeatherState.RAIN, 10, "ranged", frozenset({"corrupted", "beast"})),
    _enemy_def("enemy_iron_collared_hound", "Iron-Collared Hound", WeatherState.SNOW, 3, "melee", frozenset({"corrupted", "beast"}), stat="str", playstyle="auto", intent="damage"),
    _enemy_def("enemy_cold_iron_yeti", "Cold-Iron Yeti", WeatherState.SNOW, 4, "melee", frozenset({"corrupted", "beast", "machine"}), stat="str", durability="tanky_hp", intent="utility"),
    _enemy_def("enemy_avalanche_engine", "Avalanche Engine", WeatherState.SNOW, 5, "ranged", frozenset({"corrupted", "machine"}), stat="str", durability="squishy", playstyle="ability", intent="damage"),
    _enemy_def("enemy_glacier_goliath", "Glacier Goliath", WeatherState.SNOW, 7, "melee", frozenset({"corrupted", "machine"}), stat="str", durability="tanky_arm", intent="utility"),
    _enemy_def("enemy_riven_frost_wyrm", "Riven Frost-Wyrm", WeatherState.SNOW, 9, "ranged", frozenset({"corrupted", "beast"})),
    _enemy_def("enemy_frost_sovereign", "Frost Sovereign", WeatherState.SNOW, 10, "ranged", frozenset({"corrupted", "beast"})),
    _enemy_def("enemy_quarry_crawler", "Quarry Crawler", WeatherState.CLOUDY, 3, "melee", frozenset({"corrupted", "beast"}), stat="str", playstyle="auto", intent="utility"),
    _enemy_def("enemy_slag_sentinel", "Slag Sentinel", WeatherState.CLOUDY, 4, "melee", frozenset({"corrupted", "machine"}), stat="str", durability="tanky_arm", intent="utility"),
    _enemy_def("enemy_shaftmaw", "Shaftmaw", WeatherState.CLOUDY, 5, "melee", frozenset({"corrupted", "beast"}), stat="int", durability="squishy", playstyle="ability", intent="damage"),
    _enemy_def("enemy_reaver_of_the_reach", "Reaver of the Reach", WeatherState.CLOUDY, 7, "ranged", frozenset({"corrupted", "beast"})),
    _enemy_def("enemy_quarried_behemoth", "Quarried Behemoth", WeatherState.CLOUDY, 9, "melee", frozenset({"corrupted", "machine"}), durability="tanky_hp"),
    _enemy_def("enemy_stone_warden", "Stone Warden", WeatherState.CLOUDY, 10, "melee", frozenset({"corrupted", "machine"}), durability="tanky_hp"),
    _enemy_def("enemy_hollowed_wisp", "Hollowed Wisp", WeatherState.MIST, 3, "melee", frozenset({"corrupted", "spirit"}), stat="int", durability="squishy", playstyle="ability", intent="damage"),
    _enemy_def("enemy_drained_stalker", "Drained Stalker", WeatherState.MIST, 4, "ranged", frozenset({"corrupted", "beast"}), stat="int", playstyle="ability", intent="damage"),
    _enemy_def("enemy_caged_banshee", "Caged Banshee", WeatherState.MIST, 5, "ranged", frozenset({"corrupted", "spirit"}), stat="int", playstyle="ability", intent="utility"),
    _enemy_def("enemy_shroud_killer", "Shroud-Killer", WeatherState.MIST, 7, "melee", frozenset({"corrupted", "spirit"}), stat="str", durability="squishy", playstyle="auto", intent="damage"),
    _enemy_def("enemy_sundered_lord", "Sundered Lord", WeatherState.MIST, 9, "ranged", frozenset({"corrupted", "spirit"})),
    _enemy_def("enemy_veil_lord", "Veil Lord", WeatherState.MIST, 10, "ranged", frozenset({"corrupted", "spirit"})),
    _enemy_def("enemy_capture_rig_wolf", "Capture-Rig Wolf", WeatherState.THUNDER, 3, "melee", frozenset({"corrupted", "beast", "machine"}), stat="str", playstyle="auto", intent="damage"),
    _enemy_def("enemy_stormhawk", "Stormhawk", WeatherState.THUNDER, 4, "ranged", frozenset({"corrupted", "beast"}), stat="int", playstyle="ability", intent="damage"),
    _enemy_def("enemy_voltaic_diviner", "Voltaic Diviner", WeatherState.THUNDER, 5, "ranged", frozenset({"corrupted", "spirit"}), stat="int", durability="squishy", playstyle="ability", intent="damage"),
    _enemy_def("enemy_thunder_bull", "Thunder Bull", WeatherState.THUNDER, 7, "melee", frozenset({"corrupted", "beast", "machine"}), stat="str", playstyle="auto", intent="utility"),
    _enemy_def("enemy_caged_storm_drake", "Caged Storm-Drake", WeatherState.THUNDER, 9, "ranged", frozenset({"corrupted", "beast"})),
    _enemy_def("enemy_storm_tyrant", "Storm Tyrant", WeatherState.THUNDER, 10, "ranged", frozenset({"corrupted", "beast"})),
)


def _build_champion_roster(defs: tuple[ChampionDef, ...]) -> dict[str, Champion]:
    roster: dict[str, Champion] = {}
    for d in defs:
        assert re.fullmatch(r"champ_[a-z0-9_]+", d.id), f"Invalid champion id: {d.id}"
        assert d.id not in roster, f"Duplicate champion id: {d.id}"
        assert d.traits, f"{d.id}: traits must not be empty"
        assert set(d.traits) <= ALL_TRAIT_TAGS, f"{d.id}: invalid traits {sorted(set(d.traits) - ALL_TRAIT_TAGS)}"
        if d.tier == 10:
            assert "Primordial" in d.traits, f"{d.id}: tier-10 champion must have Primordial"
        roster[d.id] = _build_champion(d)
    return roster


def _build_enemy_roster(defs: tuple[EnemyDef, ...]) -> dict[str, Enemy]:
    roster: dict[str, Enemy] = {}
    for d in defs:
        assert re.fullmatch(r"enemy_[a-z0-9_]+", d.id), f"Invalid enemy id: {d.id}"
        assert d.id not in roster, f"Duplicate enemy id: {d.id}"
        assert d.tags, f"{d.id}: tags must not be empty"
        assert d.tags <= _ENEMY_ROSTER_TAGS, f"{d.id}: invalid tags {sorted(d.tags - _ENEMY_ROSTER_TAGS)}"
        roster[d.id] = _build_enemy(d)
    return roster


CHAMPION_ROSTER: dict[str, Champion] = _build_champion_roster(_CHAMPION_DEFS)
ENEMY_ROSTER: dict[str, Enemy] = _build_enemy_roster(_ENEMY_DEFS)
ENEMY_TAGS_MAP: dict[str, frozenset[str]] = {d.id: d.tags for d in _ENEMY_DEFS}
ENEMY_DEF_BY_ID: dict[str, EnemyDef] = {d.id: d for d in _ENEMY_DEFS}
CHAMPION_DEF_BY_ID: dict[str, ChampionDef] = {d.id: d for d in _CHAMPION_DEFS}


def get_champion(champion_id: str) -> Champion:
    return CHAMPION_ROSTER[champion_id]


def get_enemy(enemy_id: str) -> Enemy:
    return ENEMY_ROSTER[enemy_id]


def build_champion_at_level(champion_id: str, level: int) -> Champion:
    """Rebuild a roster champion at the given level (1-3) with level-scaled stats."""
    return _build_champion(CHAMPION_DEF_BY_ID[champion_id], level)


def build_enemy_at_level(enemy_id: str, level: int) -> Enemy:
    """Rebuild a roster enemy at the given level (1-3) with level-scaled stats."""
    return _build_enemy(ENEMY_DEF_BY_ID[enemy_id], level)


def champions_by_affinity(weather: WeatherState) -> list[Champion]:
    return [champion for champion in CHAMPION_ROSTER.values() if champion.affinity == weather]


def enemies_by_affinity(weather: WeatherState) -> list[Enemy]:
    return [enemy for enemy in ENEMY_ROSTER.values() if enemy.affinity == weather]


def _validate_rosters() -> None:
    assert len(CHAMPION_ROSTER) == 60, f"Expected 60 champions, found {len(CHAMPION_ROSTER)}"
    assert len(ENEMY_ROSTER) == 60, f"Expected 60 enemies, found {len(ENEMY_ROSTER)}"

    for weather in WeatherState:
        assert len(champions_by_affinity(weather)) == 10, (
            f"Expected 10 champions for {weather.value}, found {len(champions_by_affinity(weather))}"
        )

    assert len(enemies_by_affinity(WeatherState.CLEAR)) == 30, (
        f"Expected 30 clear enemies, found {len(enemies_by_affinity(WeatherState.CLEAR))}"
    )
    for weather in WeatherState:
        if weather != WeatherState.CLEAR:
            assert len(enemies_by_affinity(weather)) == 6, (
                f"Expected 6 enemies for {weather.value}, found {len(enemies_by_affinity(weather))}"
            )

    assert set(ENEMY_TAGS_MAP) == set(ENEMY_ROSTER), "ENEMY_TAGS_MAP keys must match ENEMY_ROSTER"
    for enemy_id, tags in ENEMY_TAGS_MAP.items():
        assert isinstance(tags, frozenset), f"{enemy_id}: tags must be a frozenset"
        assert tags, f"{enemy_id}: tags must not be empty"
        assert all(isinstance(tag, str) and tag for tag in tags), f"{enemy_id}: tags must be non-empty strings"
        assert tags <= _ENEMY_ROSTER_TAGS, f"{enemy_id}: invalid ENEMY_TAGS_MAP tags {sorted(tags - _ENEMY_ROSTER_TAGS)}"


_validate_rosters()
