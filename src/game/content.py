from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.game.models import Champion, Enemy, WeatherState
from src.game.scaling import stat_multiplier

_BASE_STATS: dict[str, Any] = {
    "max_hp": 600,
    "strength": 50,
    "intelligence": 50,
    "armor": 25,
    "resistance": 25,
    "attack_speed": 100,
    "mana_regen": 10,
    "move_speed": 90,
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
    },
    "standard": {
        "max_hp": 1.0,
        "armor": 1.0,
        "resistance": 1.0,
        "strength": 1.0,
        "intelligence": 1.0,
    },
    "tanky_hp": {
        "max_hp": 1.8,
        "armor": 0.8,
        "resistance": 0.8,
        "strength": 0.55,
        "intelligence": 0.55,
    },
    "tanky_arm": {
        "max_hp": 0.9,
        "armor": 2.0,
        "resistance": 2.0,
        "strength": 0.55,
        "intelligence": 0.55,
    },
}

_PLAYSTYLE: dict[str, dict[str, float]] = {
    "auto": {"attack_speed": 1.3, "mana_regen": 0.6},
    "hybrid": {"attack_speed": 1.0, "mana_regen": 1.0},
    "ability": {"attack_speed": 0.75, "mana_regen": 1.5},
}

_SPEED: dict[str, dict[str, float]] = {
    "speedy": {"attack_speed": 1.2, "resistance": 1.2, "primary_stat": 0.9},
    "neutral": {"attack_speed": 1.0, "resistance": 1.0, "primary_stat": 1.0},
    "heavy": {"attack_speed": 0.85, "resistance": 0.85, "primary_stat": 1.12},
}

_ROLE_FROM_AXES: dict[str, dict[str, str]] = {
    "str": {"melee": "warrior", "ranged": "marksman"},
    "int": {"melee": "assassin", "ranged": "mage"},
    "hybrid": {"melee": "bruiser", "ranged": "hybrid"},
}


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
    primary_stat: str
    range_: str
    durability: str
    playstyle: str
    traits: list[str]
    active_ability: str
    passive_ability: str
    speed: str = "neutral"
    ability_cost: int = 36_000
    move_speed: int = 90
    threat: int = 60
    stat_overrides: dict[str, int] = field(default_factory=dict)


@dataclass
class EnemyDef:
    id: str
    name: str
    affinity: WeatherState
    tier: int
    primary_stat: str
    range_: str
    durability: str
    playstyle: str
    tags: frozenset[str]
    active_ability: str
    passive_ability: str
    speed: str = "neutral"
    ability_cost: int = 36_000
    move_speed: int = 90
    threat: int = 60
    stat_overrides: dict[str, int] = field(default_factory=dict)


def compose_stats(
    primary_stat: str,
    range_: str,
    durability: str,
    playstyle: str,
    tier: int,
    *,
    speed: str = "neutral",
    ability_cost: int = 36_000,
) -> dict[str, Any]:
    if primary_stat not in _PRIMARY_STAT:
        raise ValueError(f"Unknown primary_stat axis value: {primary_stat!r}")
    if range_ not in _RANGE:
        raise ValueError(f"Unknown range axis value: {range_!r}")
    if durability not in _DURABILITY:
        raise ValueError(f"Unknown durability axis value: {durability!r}")
    if playstyle not in _PLAYSTYLE:
        raise ValueError(f"Unknown playstyle axis value: {playstyle!r}")
    if speed not in _SPEED:
        raise ValueError(f"Unknown speed axis value: {speed!r}")

    stats = dict(_BASE_STATS)
    for axis_weights in (
        _PRIMARY_STAT[primary_stat],
        _RANGE[range_],
        _DURABILITY[durability],
        _PLAYSTYLE[playstyle],
    ):
        for k, v in axis_weights.items():
            if k != "attack_range":
                stats[k] = stats[k] * v

    # Range sets a discrete board-space value instead of scaling a base range.
    stats["attack_range"] = _RANGE[range_]["attack_range"]
    speed_weights = _SPEED[speed]
    if playstyle == "ability":
        stats["resistance"] = stats["resistance"] * speed_weights["resistance"]
    else:
        stats["attack_speed"] = stats["attack_speed"] * speed_weights["attack_speed"]

    if primary_stat == "str":
        stats["strength"] = stats["strength"] * speed_weights["primary_stat"]
    elif primary_stat == "int":
        stats["intelligence"] = stats["intelligence"] * speed_weights["primary_stat"]
    else:
        stats["strength"] = stats["strength"] * speed_weights["primary_stat"]
        stats["intelligence"] = stats["intelligence"] * speed_weights["primary_stat"]
    stats["ability_cost"] = ability_cost

    s = stat_multiplier(tier, 1)
    for k in ("max_hp", "strength", "intelligence", "armor", "resistance"):
        stats[k] = round(stats[k] * s)

    return stats


def _assert_budget(d: Any, base: dict[str, Any]) -> None:
    scalable = ("max_hp", "strength", "intelligence", "armor", "resistance")
    budget = sum(base[k] for k in scalable)
    drift = sum(d.stat_overrides.get(k, 0) for k in scalable)
    if budget > 0:
        drift_ratio = drift / budget
        assert abs(drift_ratio) <= 0.15, (
            f"{d.id}: stat_overrides drift {drift_ratio:.1%} exceeds ±15% budget"
        )


def _apply_stat_overrides(base: dict[str, Any], overrides: dict[str, int]) -> dict[str, Any]:
    return {k: base[k] + overrides.get(k, 0) for k in base}


def _build_champion(d: ChampionDef) -> Champion:
    base = compose_stats(
        d.primary_stat,
        d.range_,
        d.durability,
        d.playstyle,
        d.tier,
        speed=d.speed,
        ability_cost=d.ability_cost,
    )
    _assert_budget(d, base)
    stats = _apply_stat_overrides(base, d.stat_overrides)
    return Champion(
        id=d.id,
        name=d.name,
        affinity=d.affinity,
        role=_ROLE_FROM_AXES[d.primary_stat][d.range_],
        tier=d.tier,
        level=1,
        max_hp=max(1, stats["max_hp"]),
        strength=max(0, stats["strength"]),
        intelligence=max(0, stats["intelligence"]),
        armor=max(0, stats["armor"]),
        resistance=max(0, stats["resistance"]),
        attack_speed=round(stats["attack_speed"]),
        mana_regen=round(stats["mana_regen"]),
        move_speed=d.move_speed,
        threat=d.threat,
        attack_range=stats["attack_range"],
        ability_cost=d.ability_cost,
        traits=d.traits,
        active_ability=d.active_ability,
        passive_ability=d.passive_ability,
    )


def _build_enemy(d: EnemyDef) -> Enemy:
    base = compose_stats(
        d.primary_stat,
        d.range_,
        d.durability,
        d.playstyle,
        d.tier,
        speed=d.speed,
        ability_cost=d.ability_cost,
    )
    _assert_budget(d, base)
    stats = _apply_stat_overrides(base, d.stat_overrides)
    return Enemy(
        id=d.id,
        name=d.name,
        affinity=d.affinity,
        role=_ROLE_FROM_AXES[d.primary_stat][d.range_],
        tier=d.tier,
        level=1,
        max_hp=max(1, stats["max_hp"]),
        strength=max(0, stats["strength"]),
        intelligence=max(0, stats["intelligence"]),
        armor=max(0, stats["armor"]),
        resistance=max(0, stats["resistance"]),
        attack_speed=round(stats["attack_speed"]),
        mana_regen=round(stats["mana_regen"]),
        move_speed=d.move_speed,
        threat=d.threat,
        attack_range=stats["attack_range"],
        ability_cost=d.ability_cost,
        active_ability=d.active_ability,
        passive_ability=d.passive_ability,
    )


def _champion_def(
    id: str,
    name: str,
    affinity: WeatherState,
    tier: int,
    primary_stat: str,
    range_: str,
    durability: str,
    playstyle: str,
    traits: list[str],
    *,
    speed: str = "neutral",
    ability_cost: int = 36_000,
    move_speed: int = 90,
    threat: int = 60,
    stat_overrides: dict[str, int] | None = None,
) -> ChampionDef:
    return ChampionDef(
        id=id,
        name=name,
        affinity=affinity,
        tier=tier,
        primary_stat=primary_stat,
        range_=range_,
        durability=durability,
        playstyle=playstyle,
        speed=speed,
        traits=traits,
        active_ability=f"{id}.active",
        passive_ability=f"{id}.passive",
        ability_cost=ability_cost,
        move_speed=move_speed,
        threat=threat,
        stat_overrides=stat_overrides or {},
    )


def _enemy_def(
    id: str,
    name: str,
    affinity: WeatherState,
    tier: int,
    primary_stat: str,
    range_: str,
    durability: str,
    playstyle: str,
    tags: frozenset[str],
    *,
    speed: str = "neutral",
    ability_cost: int = 36_000,
    move_speed: int = 90,
    threat: int = 60,
    stat_overrides: dict[str, int] | None = None,
) -> EnemyDef:
    return EnemyDef(
        id=id,
        name=name,
        affinity=affinity,
        tier=tier,
        primary_stat=primary_stat,
        range_=range_,
        durability=durability,
        playstyle=playstyle,
        speed=speed,
        tags=tags,
        active_ability=f"{id}.active",
        passive_ability=f"{id}.passive",
        ability_cost=ability_cost,
        move_speed=move_speed,
        threat=threat,
        stat_overrides=stat_overrides or {},
    )


_CHAMPION_DEFS: tuple[ChampionDef, ...] = (
    _champion_def("champ_dawnwisp", "Dawnwisp", WeatherState.CLEAR, 1, "int", "ranged", "standard", "ability", ["Spirit", "Mender"]),
    _champion_def("champ_veldt_pronghorn", "Veldt Pronghorn", WeatherState.CLEAR, 2, "str", "melee", "standard", "auto", ["Beast", "Skirmisher"]),
    _champion_def("champ_ember_salamander", "Ember Salamander", WeatherState.CLEAR, 3, "int", "ranged", "squishy", "ability", ["Scaled", "Mystic"]),
    _champion_def("champ_goldcrest_lark", "Goldcrest Lark", WeatherState.CLEAR, 4, "int", "ranged", "standard", "ability", ["Skyborn", "Warden"]),
    _champion_def("champ_aegis_tortoise", "Aegis Tortoise", WeatherState.CLEAR, 5, "str", "melee", "tanky_arm", "hybrid", ["Scaled", "Guardian"], speed="heavy"),
    _champion_def("champ_sunmane_lion", "Sunmane Lion", WeatherState.CLEAR, 6, "str", "melee", "standard", "auto", ["Beast", "Bruiser"]),
    _champion_def("champ_goldhide_rhino", "Goldhide Rhino", WeatherState.CLEAR, 7, "hybrid", "melee", "tanky_hp", "hybrid", ["Beast", "Bruiser", "Mender"], speed="heavy"),
    _champion_def("champ_mirage_caracal", "Mirage Caracal", WeatherState.CLEAR, 8, "int", "melee", "squishy", "ability", ["Beast", "Stalker"], speed="speedy"),
    _champion_def("champ_sunspear_falcon", "Sunspear Falcon", WeatherState.CLEAR, 9, "str", "ranged", "standard", "auto", ["Skyborn", "Hunter"]),
    _champion_def("champ_aurion", "Aurion, the First Dawn", WeatherState.CLEAR, 10, "hybrid", "ranged", "standard", "hybrid", ["Spirit", "Primordial", "Channeler"]),
    _champion_def("champ_springfrog", "Springfrog", WeatherState.RAIN, 1, "int", "ranged", "standard", "ability", ["Tidekin", "Mender"]),
    _champion_def("champ_reedbank_otter", "Reedbank Otter", WeatherState.RAIN, 2, "str", "melee", "standard", "auto", ["Tidekin", "Skirmisher"], speed="speedy"),
    _champion_def("champ_torrent_heron", "Torrent Heron", WeatherState.RAIN, 3, "str", "ranged", "squishy", "ability", ["Skyborn", "Mystic"]),
    _champion_def("champ_grovekeeper_tapir", "Grovekeeper Tapir", WeatherState.RAIN, 4, "hybrid", "melee", "tanky_hp", "hybrid", ["Beast", "Bruiser", "Mender"]),
    _champion_def("champ_coral_colossus", "Coral Colossus", WeatherState.RAIN, 5, "str", "melee", "tanky_hp", "hybrid", ["Tidekin", "Guardian", "Mender"], speed="heavy"),
    _champion_def("champ_marsh_thrush", "Marsh Thrush", WeatherState.RAIN, 6, "int", "ranged", "standard", "ability", ["Skyborn", "Warden"]),
    _champion_def("champ_mirewarden_toad", "Mirewarden Toad", WeatherState.RAIN, 7, "int", "melee", "tanky_hp", "ability", ["Tidekin", "Guardian"]),
    _champion_def("champ_glade_heron", "Glade Heron", WeatherState.RAIN, 8, "int", "ranged", "standard", "ability", ["Skyborn", "Hunter", "Trickster"]),
    _champion_def("champ_riptide_caiman", "Riptide Caiman", WeatherState.RAIN, 9, "str", "melee", "squishy", "auto", ["Scaled", "Stalker"], speed="speedy"),
    _champion_def("champ_nerei", "Nerei, the Floodmother", WeatherState.RAIN, 10, "hybrid", "ranged", "standard", "hybrid", ["Spirit", "Primordial", "Channeler"]),
    _champion_def("champ_snowpelt_cub", "Snowpelt Cub", WeatherState.SNOW, 1, "str", "melee", "tanky_hp", "hybrid", ["Beast", "Guardian"], speed="heavy"),
    _champion_def("champ_wintermoth", "Wintermoth", WeatherState.SNOW, 2, "int", "ranged", "standard", "ability", ["Swarm", "Warden"]),
    _champion_def("champ_permafrost_walrus", "Permafrost Walrus", WeatherState.SNOW, 3, "str", "ranged", "squishy", "ability", ["Tidekin", "Mystic"]),
    _champion_def("champ_hoarfrost_owl", "Hoarfrost Owl", WeatherState.SNOW, 4, "int", "ranged", "standard", "ability", ["Skyborn", "Warden"]),
    _champion_def("champ_frostplate_tortoise", "Frostplate Tortoise", WeatherState.SNOW, 5, "str", "melee", "tanky_arm", "hybrid", ["Scaled", "Guardian"]),
    _champion_def("champ_iceclaw_lynx", "Iceclaw Lynx", WeatherState.SNOW, 6, "int", "melee", "standard", "ability", ["Beast", "Skirmisher", "Trickster"], speed="speedy"),
    _champion_def("champ_glacierback_mammoth", "Glacierback Mammoth", WeatherState.SNOW, 7, "hybrid", "melee", "tanky_hp", "hybrid", ["Beast", "Bruiser"], speed="heavy"),
    _champion_def("champ_frostfang_wolverine", "Frostfang Wolverine", WeatherState.SNOW, 8, "str", "melee", "squishy", "auto", ["Beast", "Stalker"]),
    _champion_def("champ_frostquill_porcupine", "Frostquill Porcupine", WeatherState.SNOW, 9, "str", "ranged", "standard", "auto", ["Beast", "Hunter", "Trickster"]),
    _champion_def("champ_borealis", "Borealis, the Pale Aurora", WeatherState.SNOW, 10, "hybrid", "ranged", "standard", "hybrid", ["Spirit", "Primordial", "Mystic"]),
    _champion_def("champ_pebbleback_pangolin", "Pebbleback Pangolin", WeatherState.CLOUDY, 1, "str", "melee", "tanky_hp", "hybrid", ["Scaled", "Guardian"]),
    _champion_def("champ_dusk_bat", "Dusk Bat", WeatherState.CLOUDY, 2, "int", "ranged", "standard", "ability", ["Beast", "Trickster"], speed="speedy"),
    _champion_def("champ_boulderhide_skink", "Boulderhide Skink", WeatherState.CLOUDY, 3, "str", "ranged", "squishy", "ability", ["Scaled", "Mystic"]),
    _champion_def("champ_geode_beetle", "Geode Beetle", WeatherState.CLOUDY, 4, "int", "ranged", "standard", "ability", ["Swarm", "Warden"]),
    _champion_def("champ_duskstep_marten", "Duskstep Marten", WeatherState.CLOUDY, 5, "int", "melee", "standard", "ability", ["Beast", "Skirmisher", "Stalker"]),
    _champion_def("champ_granite_gorilla", "Granite Gorilla", WeatherState.CLOUDY, 6, "int", "melee", "tanky_hp", "ability", ["Beast", "Guardian"], speed="heavy"),
    _champion_def("champ_eclipse_jaguar", "Eclipse Jaguar", WeatherState.CLOUDY, 7, "hybrid", "ranged", "standard", "hybrid", ["Beast", "Stalker", "Channeler"]),
    _champion_def("champ_nightglass_mantis", "Nightglass Mantis", WeatherState.CLOUDY, 8, "int", "melee", "squishy", "ability", ["Swarm", "Stalker"], speed="speedy"),
    _champion_def("champ_cliffeyrie_eagle", "Cliffeyrie Eagle", WeatherState.CLOUDY, 9, "str", "ranged", "standard", "auto", ["Skyborn", "Hunter"]),
    _champion_def("champ_umbra", "Umbra, the Mountain's Shadow", WeatherState.CLOUDY, 10, "hybrid", "ranged", "standard", "hybrid", ["Spirit", "Primordial", "Stalker"]),
    _champion_def("champ_lostlight_wisp", "Lostlight Wisp", WeatherState.MIST, 1, "int", "ranged", "standard", "ability", ["Spirit", "Mender"]),
    _champion_def("champ_will_o_fawn", "Will-o-Fawn", WeatherState.MIST, 2, "int", "ranged", "squishy", "ability", ["Spirit", "Mystic"], speed="speedy"),
    _champion_def("champ_phantom_lynx", "Phantom Lynx", WeatherState.MIST, 3, "int", "melee", "squishy", "ability", ["Spirit", "Stalker"]),
    _champion_def("champ_hollow_elk", "Hollow Elk", WeatherState.MIST, 4, "int", "melee", "tanky_hp", "ability", ["Spirit", "Guardian", "Channeler"], speed="heavy"),
    _champion_def("champ_fogveil_moth", "Fogveil Moth", WeatherState.MIST, 5, "int", "ranged", "standard", "ability", ["Swarm", "Trickster"]),
    _champion_def("champ_wraithorn_stag", "Wraithorn Stag", WeatherState.MIST, 6, "str", "melee", "standard", "auto", ["Spirit", "Bruiser"]),
    _champion_def("champ_marshghast_boar", "Marshghast Boar", WeatherState.MIST, 7, "hybrid", "melee", "tanky_hp", "hybrid", ["Spirit", "Bruiser", "Stalker"]),
    _champion_def("champ_veilfang_wolf", "Veilfang Wolf", WeatherState.MIST, 8, "int", "melee", "standard", "ability", ["Spirit", "Skirmisher"], speed="speedy"),
    _champion_def("champ_spectral_heron", "Spectral Heron", WeatherState.MIST, 9, "int", "ranged", "standard", "ability", ["Spirit", "Hunter"]),
    _champion_def("champ_mournhollow", "Mournhollow, the Pale Stag", WeatherState.MIST, 10, "hybrid", "ranged", "standard", "hybrid", ["Spirit", "Primordial", "Channeler"]),
    _champion_def("champ_sparkfly", "Sparkfly", WeatherState.THUNDER, 1, "int", "ranged", "standard", "ability", ["Swarm", "Trickster"]),
    _champion_def("champ_thunderhoof_colt", "Thunderhoof Colt", WeatherState.THUNDER, 2, "str", "melee", "standard", "auto", ["Beast", "Skirmisher"], speed="speedy"),
    _champion_def("champ_voltscale_mamba", "Voltscale Mamba", WeatherState.THUNDER, 3, "str", "melee", "squishy", "auto", ["Scaled", "Stalker"]),
    _champion_def("champ_coppercrest_stork", "Coppercrest Stork", WeatherState.THUNDER, 4, "int", "ranged", "standard", "ability", ["Skyborn", "Warden"]),
    _champion_def("champ_thunderhide_bison", "Thunderhide Bison", WeatherState.THUNDER, 5, "str", "melee", "tanky_arm", "hybrid", ["Beast", "Guardian"], speed="heavy"),
    _champion_def("champ_tempest_eel", "Tempest Eel", WeatherState.THUNDER, 6, "int", "ranged", "squishy", "ability", ["Tidekin", "Mystic"]),
    _champion_def("champ_voltmane_jackal", "Voltmane Jackal", WeatherState.THUNDER, 7, "hybrid", "ranged", "standard", "hybrid", ["Beast", "Skirmisher", "Channeler"]),
    _champion_def("champ_thunderclap_gorilla", "Thunderclap Gorilla", WeatherState.THUNDER, 8, "str", "melee", "standard", "auto", ["Beast", "Bruiser"]),
    _champion_def("champ_storm_eagle", "Storm Eagle", WeatherState.THUNDER, 9, "int", "ranged", "standard", "ability", ["Skyborn", "Hunter", "Channeler"], speed="speedy"),
    _champion_def("champ_aerion", "Aerion, the Skybreaker", WeatherState.THUNDER, 10, "hybrid", "ranged", "standard", "hybrid", ["Spirit", "Primordial", "Hunter"]),
)


_ENEMY_DEFS: tuple[EnemyDef, ...] = (
    _enemy_def("enemy_conscript", "Conscript", WeatherState.CLEAR, 1, "str", "melee", "standard", "auto", frozenset({"human"})),
    _enemy_def("enemy_levyman", "Levyman", WeatherState.CLEAR, 1, "str", "melee", "tanky_hp", "hybrid", frozenset({"human"})),
    _enemy_def("enemy_picket", "Picket", WeatherState.CLEAR, 1, "str", "ranged", "standard", "auto", frozenset({"human"})),
    _enemy_def("enemy_stretcher_hand", "Stretcher-Hand", WeatherState.CLEAR, 1, "int", "ranged", "standard", "ability", frozenset({"human"})),
    _enemy_def("enemy_signal_drummer", "Signal Drummer", WeatherState.CLEAR, 1, "int", "ranged", "standard", "ability", frozenset({"human"})),
    _enemy_def("enemy_pikeman", "Pikeman", WeatherState.CLEAR, 2, "str", "melee", "tanky_arm", "hybrid", frozenset({"human"})),
    _enemy_def("enemy_crossbow_levy", "Crossbow Levy", WeatherState.CLEAR, 2, "str", "ranged", "standard", "auto", frozenset({"human"})),
    _enemy_def("enemy_field_medic", "Field Medic", WeatherState.CLEAR, 2, "int", "ranged", "standard", "ability", frozenset({"human"})),
    _enemy_def("enemy_powder_sapper", "Powder Sapper", WeatherState.CLEAR, 2, "str", "ranged", "squishy", "ability", frozenset({"human"})),
    _enemy_def("enemy_sergeant_at_arms", "Sergeant-at-Arms", WeatherState.CLEAR, 3, "hybrid", "melee", "tanky_hp", "hybrid", frozenset({"human"})),
    _enemy_def("enemy_field_chaplain", "Field Chaplain", WeatherState.CLEAR, 3, "int", "ranged", "standard", "ability", frozenset({"human"})),
    _enemy_def("enemy_standard_bearer", "Standard Bearer", WeatherState.CLEAR, 3, "int", "ranged", "standard", "ability", frozenset({"human"})),
    _enemy_def("enemy_heavy_knight", "Heavy Knight", WeatherState.CLEAR, 4, "str", "melee", "tanky_hp", "hybrid", frozenset({"human"})),
    _enemy_def("enemy_steam_engineer", "Steam Engineer", WeatherState.CLEAR, 4, "int", "ranged", "squishy", "ability", frozenset({"human", "machine"})),
    _enemy_def("enemy_company_guard", "Company Guard", WeatherState.CLEAR, 4, "hybrid", "melee", "tanky_hp", "hybrid", frozenset({"human"})),
    _enemy_def("enemy_battlemage", "Battlemage", WeatherState.CLEAR, 5, "int", "ranged", "squishy", "ability", frozenset({"human"})),
    _enemy_def("enemy_gunslinger", "Gunslinger", WeatherState.CLEAR, 5, "str", "ranged", "standard", "auto", frozenset({"human"})),
    _enemy_def("enemy_company_captain", "Company Captain", WeatherState.CLEAR, 5, "int", "ranged", "standard", "ability", frozenset({"human"})),
    _enemy_def("enemy_steam_knight", "Steam Knight", WeatherState.CLEAR, 6, "str", "melee", "standard", "auto", frozenset({"human", "machine"})),
    _enemy_def("enemy_riflemaster", "Riflemaster", WeatherState.CLEAR, 6, "str", "ranged", "standard", "auto", frozenset({"human"})),
    _enemy_def("enemy_inquisitor", "Inquisitor", WeatherState.CLEAR, 6, "hybrid", "ranged", "standard", "hybrid", frozenset({"human"})),
    _enemy_def("enemy_hexblade_officer", "Hexblade Officer", WeatherState.CLEAR, 6, "int", "melee", "standard", "ability", frozenset({"human"})),
    _enemy_def("enemy_lord_commander", "Lord Commander", WeatherState.CLEAR, 7, "str", "melee", "standard", "auto", frozenset({"human"})),
    _enemy_def("enemy_iron_maiden", "Iron Maiden", WeatherState.CLEAR, 7, "hybrid", "melee", "tanky_hp", "hybrid", frozenset({"human", "machine"})),
    _enemy_def("enemy_cannoneer", "Cannoneer", WeatherState.CLEAR, 8, "str", "ranged", "standard", "auto", frozenset({"human", "machine"})),
    _enemy_def("enemy_spymaster", "Spymaster", WeatherState.CLEAR, 8, "int", "melee", "squishy", "ability", frozenset({"human"})),
    _enemy_def("enemy_hierarch", "Hierarch", WeatherState.CLEAR, 8, "int", "ranged", "standard", "ability", frozenset({"human"})),
    _enemy_def("enemy_arcanist", "Arcanist", WeatherState.CLEAR, 9, "int", "ranged", "squishy", "ability", frozenset({"human"})),
    _enemy_def("enemy_archmagus_imperator", "Archmagus Imperator", WeatherState.CLEAR, 9, "hybrid", "ranged", "standard", "hybrid", frozenset({"human"})),
    _enemy_def("enemy_grand_marshal", "Grand Marshal", WeatherState.CLEAR, 10, "str", "melee", "standard", "auto", frozenset({"human"})),
    _enemy_def("enemy_blight_lurker", "Blight Lurker", WeatherState.RAIN, 3, "str", "melee", "tanky_hp", "hybrid", frozenset({"corrupted", "beast"})),
    _enemy_def("enemy_drowned_siren", "Drowned Siren", WeatherState.RAIN, 4, "int", "ranged", "squishy", "ability", frozenset({"corrupted", "spirit"})),
    _enemy_def("enemy_brineblight_berserker", "Brineblight Berserker", WeatherState.RAIN, 5, "str", "melee", "standard", "auto", frozenset({"corrupted", "beast"})),
    _enemy_def("enemy_dredge_hulk", "Dredge-Hulk", WeatherState.RAIN, 7, "hybrid", "melee", "tanky_hp", "hybrid", frozenset({"corrupted", "beast", "machine"})),
    _enemy_def("enemy_maw_of_the_drowned", "Maw of the Drowned", WeatherState.RAIN, 9, "hybrid", "ranged", "standard", "hybrid", frozenset({"corrupted", "beast"})),
    _enemy_def("enemy_flood_tyrant", "Flood Tyrant", WeatherState.RAIN, 10, "hybrid", "ranged", "standard", "hybrid", frozenset({"corrupted", "beast"})),
    _enemy_def("enemy_iron_collared_hound", "Iron-Collared Hound", WeatherState.SNOW, 3, "str", "melee", "standard", "auto", frozenset({"corrupted", "beast"})),
    _enemy_def("enemy_cold_iron_yeti", "Cold-Iron Yeti", WeatherState.SNOW, 4, "str", "melee", "tanky_hp", "hybrid", frozenset({"corrupted", "beast", "machine"})),
    _enemy_def("enemy_avalanche_engine", "Avalanche Engine", WeatherState.SNOW, 5, "str", "ranged", "squishy", "ability", frozenset({"corrupted", "machine"})),
    _enemy_def("enemy_glacier_goliath", "Glacier Goliath", WeatherState.SNOW, 7, "str", "melee", "tanky_arm", "hybrid", frozenset({"corrupted", "machine"})),
    _enemy_def("enemy_riven_frost_wyrm", "Riven Frost-Wyrm", WeatherState.SNOW, 9, "hybrid", "ranged", "standard", "hybrid", frozenset({"corrupted", "beast"})),
    _enemy_def("enemy_frost_sovereign", "Frost Sovereign", WeatherState.SNOW, 10, "hybrid", "ranged", "standard", "hybrid", frozenset({"corrupted", "beast"})),
    _enemy_def("enemy_quarry_crawler", "Quarry Crawler", WeatherState.CLOUDY, 3, "str", "melee", "standard", "auto", frozenset({"corrupted", "beast"})),
    _enemy_def("enemy_slag_sentinel", "Slag Sentinel", WeatherState.CLOUDY, 4, "str", "melee", "tanky_arm", "hybrid", frozenset({"corrupted", "machine"})),
    _enemy_def("enemy_shaftmaw", "Shaftmaw", WeatherState.CLOUDY, 5, "int", "melee", "squishy", "ability", frozenset({"corrupted", "beast"})),
    _enemy_def("enemy_reaver_of_the_reach", "Reaver of the Reach", WeatherState.CLOUDY, 7, "hybrid", "ranged", "standard", "hybrid", frozenset({"corrupted", "beast"})),
    _enemy_def("enemy_quarried_behemoth", "Quarried Behemoth", WeatherState.CLOUDY, 9, "hybrid", "melee", "tanky_hp", "hybrid", frozenset({"corrupted", "machine"})),
    _enemy_def("enemy_stone_warden", "Stone Warden", WeatherState.CLOUDY, 10, "hybrid", "melee", "tanky_hp", "hybrid", frozenset({"corrupted", "machine"})),
    _enemy_def("enemy_hollowed_wisp", "Hollowed Wisp", WeatherState.MIST, 3, "int", "melee", "squishy", "ability", frozenset({"corrupted", "spirit"})),
    _enemy_def("enemy_drained_stalker", "Drained Stalker", WeatherState.MIST, 4, "int", "ranged", "standard", "ability", frozenset({"corrupted", "beast"})),
    _enemy_def("enemy_caged_banshee", "Caged Banshee", WeatherState.MIST, 5, "int", "ranged", "standard", "ability", frozenset({"corrupted", "spirit"})),
    _enemy_def("enemy_shroud_killer", "Shroud-Killer", WeatherState.MIST, 7, "str", "melee", "squishy", "auto", frozenset({"corrupted", "spirit"})),
    _enemy_def("enemy_sundered_lord", "Sundered Lord", WeatherState.MIST, 9, "hybrid", "ranged", "standard", "hybrid", frozenset({"corrupted", "spirit"})),
    _enemy_def("enemy_veil_lord", "Veil Lord", WeatherState.MIST, 10, "hybrid", "ranged", "standard", "hybrid", frozenset({"corrupted", "spirit"})),
    _enemy_def("enemy_capture_rig_wolf", "Capture-Rig Wolf", WeatherState.THUNDER, 3, "str", "melee", "standard", "auto", frozenset({"corrupted", "beast", "machine"})),
    _enemy_def("enemy_stormhawk", "Stormhawk", WeatherState.THUNDER, 4, "int", "ranged", "standard", "ability", frozenset({"corrupted", "beast"})),
    _enemy_def("enemy_voltaic_diviner", "Voltaic Diviner", WeatherState.THUNDER, 5, "int", "ranged", "squishy", "ability", frozenset({"corrupted", "spirit"})),
    _enemy_def("enemy_thunder_bull", "Thunder Bull", WeatherState.THUNDER, 7, "str", "melee", "standard", "auto", frozenset({"corrupted", "beast", "machine"})),
    _enemy_def("enemy_caged_storm_drake", "Caged Storm-Drake", WeatherState.THUNDER, 9, "hybrid", "ranged", "standard", "hybrid", frozenset({"corrupted", "beast"})),
    _enemy_def("enemy_storm_tyrant", "Storm Tyrant", WeatherState.THUNDER, 10, "hybrid", "ranged", "standard", "hybrid", frozenset({"corrupted", "beast"})),
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


def get_champion(champion_id: str) -> Champion:
    return CHAMPION_ROSTER[champion_id]


def get_enemy(enemy_id: str) -> Enemy:
    return ENEMY_ROSTER[enemy_id]


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
