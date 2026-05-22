"""City route definition for Tempest Fauna Trail.

Exposes the fixed 50-node world tour across 6 continent stages.
No Flet imports — pure game logic (V.1).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .models import Node, NodeState, NodeType, WeatherState

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CityDef:
    id: str
    name: str
    country: str
    continent: str
    latitude: float
    longitude: float
    default_weather: WeatherState


@dataclass(frozen=True)
class StageDef:
    index: int                        # 1..6
    name: str                         # continent name
    affinity: WeatherState            # authored stage affinity (bosses/challenges)
    node_cities: tuple[str, ...]      # one city id per node, in node order
    node_types: tuple[NodeType, ...]  # encounter sequence, parallel to node_cities
    difficulty: int                   # 1..6, monotonically increasing


# ---------------------------------------------------------------------------
# City catalog (50 entries, keyed by city id)
# ---------------------------------------------------------------------------

CITIES: dict[str, CityDef] = {
    # --- Stage 1: Europe ---
    "city_lisbon": CityDef(
        "city_lisbon", "Lisbon", "Portugal", "Europe", 38.72, -9.14, WeatherState.CLEAR
    ),
    "city_madrid": CityDef(
        "city_madrid", "Madrid", "Spain", "Europe", 40.42, -3.70, WeatherState.CLEAR
    ),
    "city_paris": CityDef(
        "city_paris", "Paris", "France", "Europe", 48.86, 2.35, WeatherState.CLOUDY
    ),
    "city_london": CityDef(
        "city_london", "London", "United Kingdom", "Europe", 51.51, -0.13, WeatherState.CLOUDY
    ),
    "city_brussels": CityDef(
        "city_brussels", "Brussels", "Belgium", "Europe", 50.85, 4.35, WeatherState.RAIN
    ),
    "city_amsterdam": CityDef(
        "city_amsterdam", "Amsterdam", "Netherlands", "Europe", 52.37, 4.90, WeatherState.RAIN
    ),
    "city_berlin": CityDef(
        "city_berlin", "Berlin", "Germany", "Europe", 52.52, 13.40, WeatherState.CLOUDY
    ),
    "city_prague": CityDef(
        "city_prague", "Prague", "Czechia", "Europe", 50.08, 14.44, WeatherState.CLOUDY
    ),
    "city_rome": CityDef(
        "city_rome", "Rome", "Italy", "Europe", 41.90, 12.50, WeatherState.CLEAR
    ),
    "city_vienna": CityDef(
        "city_vienna", "Vienna", "Austria", "Europe", 48.21, 16.37, WeatherState.CLOUDY
    ),
    # --- Stage 2: Africa ---
    "city_casablanca": CityDef(
        "city_casablanca", "Casablanca", "Morocco", "Africa", 33.59, -7.62, WeatherState.CLEAR
    ),
    "city_marrakesh": CityDef(
        "city_marrakesh", "Marrakesh", "Morocco", "Africa", 31.63, -7.99, WeatherState.CLEAR
    ),
    "city_dakar": CityDef(
        "city_dakar", "Dakar", "Senegal", "Africa", 14.72, -17.47, WeatherState.CLEAR
    ),
    "city_lagos": CityDef(
        "city_lagos", "Lagos", "Nigeria", "Africa", 6.46, 3.39, WeatherState.RAIN
    ),
    "city_accra": CityDef(
        "city_accra", "Accra", "Ghana", "Africa", 5.56, -0.20, WeatherState.RAIN
    ),
    "city_addis_ababa": CityDef(
        "city_addis_ababa", "Addis Ababa", "Ethiopia", "Africa", 9.03, 38.74, WeatherState.RAIN
    ),
    "city_nairobi": CityDef(
        "city_nairobi", "Nairobi", "Kenya", "Africa", -1.29, 36.82, WeatherState.CLOUDY
    ),
    "city_cairo": CityDef(
        "city_cairo", "Cairo", "Egypt", "Africa", 30.04, 31.24, WeatherState.CLEAR
    ),
    # --- Stage 3: Asia ---
    "city_mumbai": CityDef(
        "city_mumbai", "Mumbai", "India", "Asia", 19.08, 72.88, WeatherState.RAIN
    ),
    "city_delhi": CityDef(
        "city_delhi", "Delhi", "India", "Asia", 28.61, 77.21, WeatherState.MIST
    ),
    "city_bangkok": CityDef(
        "city_bangkok", "Bangkok", "Thailand", "Asia", 13.76, 100.50, WeatherState.THUNDER
    ),
    "city_singapore": CityDef(
        "city_singapore", "Singapore", "Singapore", "Asia", 1.29, 103.85, WeatherState.THUNDER
    ),
    "city_jakarta": CityDef(
        "city_jakarta", "Jakarta", "Indonesia", "Asia", -6.18, 106.83, WeatherState.RAIN
    ),
    "city_hong_kong": CityDef(
        "city_hong_kong", "Hong Kong", "China", "Asia", 22.28, 114.16, WeatherState.THUNDER
    ),
    "city_seoul": CityDef(
        "city_seoul", "Seoul", "South Korea", "Asia", 37.57, 126.98, WeatherState.SNOW
    ),
    "city_tokyo": CityDef(
        "city_tokyo", "Tokyo", "Japan", "Asia", 35.68, 139.76, WeatherState.THUNDER
    ),
    # --- Stage 4: Oceania ---
    "city_perth": CityDef(
        "city_perth", "Perth", "Australia", "Oceania", -31.95, 115.86, WeatherState.CLEAR
    ),
    "city_adelaide": CityDef(
        "city_adelaide", "Adelaide", "Australia", "Oceania", -34.93, 138.60, WeatherState.CLEAR
    ),
    "city_melbourne": CityDef(
        "city_melbourne", "Melbourne", "Australia", "Oceania", -37.81, 144.96, WeatherState.CLOUDY
    ),
    "city_brisbane": CityDef(
        "city_brisbane", "Brisbane", "Australia", "Oceania", -27.47, 153.03, WeatherState.RAIN
    ),
    "city_port_moresby": CityDef(
        "city_port_moresby", "Port Moresby", "Papua New Guinea", "Oceania", -9.44, 147.18, WeatherState.RAIN
    ),
    "city_auckland": CityDef(
        "city_auckland", "Auckland", "New Zealand", "Oceania", -36.85, 174.76, WeatherState.RAIN
    ),
    "city_wellington": CityDef(
        "city_wellington", "Wellington", "New Zealand", "Oceania", -41.29, 174.78, WeatherState.CLOUDY
    ),
    "city_sydney": CityDef(
        "city_sydney", "Sydney", "Australia", "Oceania", -33.87, 151.21, WeatherState.CLOUDY
    ),
    # --- Stage 5: South America ---
    "city_bogota": CityDef(
        "city_bogota", "Bogotá", "Colombia", "South America", 4.71, -74.07, WeatherState.RAIN
    ),
    "city_quito": CityDef(
        "city_quito", "Quito", "Ecuador", "South America", -0.22, -78.51, WeatherState.RAIN
    ),
    "city_lima": CityDef(
        "city_lima", "Lima", "Peru", "South America", -12.05, -77.04, WeatherState.MIST
    ),
    "city_santiago": CityDef(
        "city_santiago", "Santiago", "Chile", "South America", -33.45, -70.67, WeatherState.CLEAR
    ),
    "city_buenos_aires": CityDef(
        "city_buenos_aires", "Buenos Aires", "Argentina", "South America", -34.60, -58.38, WeatherState.CLOUDY
    ),
    "city_montevideo": CityDef(
        "city_montevideo", "Montevideo", "Uruguay", "South America", -34.90, -56.16, WeatherState.RAIN
    ),
    "city_sao_paulo": CityDef(
        "city_sao_paulo", "São Paulo", "Brazil", "South America", -23.55, -46.63, WeatherState.RAIN
    ),
    "city_rio_de_janeiro": CityDef(
        "city_rio_de_janeiro", "Rio de Janeiro", "Brazil", "South America", -22.91, -43.21, WeatherState.RAIN
    ),
    # --- Stage 6: North America ---
    "city_mexico_city": CityDef(
        "city_mexico_city", "Mexico City", "Mexico", "North America", 19.43, -99.13, WeatherState.CLOUDY
    ),
    "city_houston": CityDef(
        "city_houston", "Houston", "United States", "North America", 29.76, -95.37, WeatherState.THUNDER
    ),
    "city_miami": CityDef(
        "city_miami", "Miami", "United States", "North America", 25.76, -80.19, WeatherState.THUNDER
    ),
    "city_los_angeles": CityDef(
        "city_los_angeles", "Los Angeles", "United States", "North America", 34.05, -118.24, WeatherState.CLEAR
    ),
    "city_chicago": CityDef(
        "city_chicago", "Chicago", "United States", "North America", 41.88, -87.63, WeatherState.SNOW
    ),
    "city_toronto": CityDef(
        "city_toronto", "Toronto", "Canada", "North America", 43.65, -79.38, WeatherState.SNOW
    ),
    "city_boston": CityDef(
        "city_boston", "Boston", "United States", "North America", 42.36, -71.06, WeatherState.SNOW
    ),
    "city_new_york": CityDef(
        "city_new_york", "New York", "United States", "North America", 40.71, -74.01, WeatherState.SNOW
    ),
}

# ---------------------------------------------------------------------------
# Stage definitions
# ---------------------------------------------------------------------------

# Stage 1 sequence: Reward, Reward, Augment, Combat, Combat, Supply, Combat, Challenge, Reward, Boss
_STAGE1_TYPES: tuple[NodeType, ...] = (
    NodeType.REWARD,
    NodeType.REWARD,
    NodeType.AUGMENT,
    NodeType.FIGHT,
    NodeType.FIGHT,
    NodeType.SUPPLY,
    NodeType.FIGHT,
    NodeType.CHALLENGE,
    NodeType.REWARD,
    NodeType.BOSS_FIGHT,
)

# Stages 2-6 sequence: Combat, Augment, Combat, Supply, Combat, Challenge, Reward, Boss
_STAGE_DEFAULT_TYPES: tuple[NodeType, ...] = (
    NodeType.FIGHT,
    NodeType.AUGMENT,
    NodeType.FIGHT,
    NodeType.SUPPLY,
    NodeType.FIGHT,
    NodeType.CHALLENGE,
    NodeType.REWARD,
    NodeType.BOSS_FIGHT,
)

STAGES: tuple[StageDef, ...] = (
    StageDef(
        index=1,
        name="Europe",
        affinity=WeatherState.CLEAR,
        node_cities=(
            "city_lisbon", "city_madrid", "city_paris", "city_london",
            "city_brussels", "city_amsterdam", "city_berlin", "city_prague",
            "city_rome", "city_vienna",
        ),
        node_types=_STAGE1_TYPES,
        difficulty=1,
    ),
    StageDef(
        index=2,
        name="Africa",
        affinity=WeatherState.MIST,
        node_cities=(
            "city_casablanca", "city_marrakesh", "city_dakar", "city_lagos",
            "city_accra", "city_addis_ababa", "city_nairobi", "city_cairo",
        ),
        node_types=_STAGE_DEFAULT_TYPES,
        difficulty=2,
    ),
    StageDef(
        index=3,
        name="Asia",
        affinity=WeatherState.THUNDER,
        node_cities=(
            "city_mumbai", "city_delhi", "city_bangkok", "city_singapore",
            "city_jakarta", "city_hong_kong", "city_seoul", "city_tokyo",
        ),
        node_types=_STAGE_DEFAULT_TYPES,
        difficulty=3,
    ),
    StageDef(
        index=4,
        name="Oceania",
        affinity=WeatherState.CLOUDY,
        node_cities=(
            "city_perth", "city_adelaide", "city_melbourne", "city_brisbane",
            "city_port_moresby", "city_auckland", "city_wellington", "city_sydney",
        ),
        node_types=_STAGE_DEFAULT_TYPES,
        difficulty=4,
    ),
    StageDef(
        index=5,
        name="South America",
        affinity=WeatherState.RAIN,
        node_cities=(
            "city_bogota", "city_quito", "city_lima", "city_santiago",
            "city_buenos_aires", "city_montevideo", "city_sao_paulo", "city_rio_de_janeiro",
        ),
        node_types=_STAGE_DEFAULT_TYPES,
        difficulty=5,
    ),
    StageDef(
        index=6,
        name="North America",
        affinity=WeatherState.SNOW,
        node_cities=(
            "city_mexico_city", "city_houston", "city_miami", "city_los_angeles",
            "city_chicago", "city_toronto", "city_boston", "city_new_york",
        ),
        node_types=_STAGE_DEFAULT_TYPES,
        difficulty=6,
    ),
)

ROUTE_NODE_COUNT: Final[int] = sum(len(s.node_cities) for s in STAGES)  # 50


# ---------------------------------------------------------------------------
# Enemy pool id helpers
# ---------------------------------------------------------------------------

def _pool_id(continent: str, pool_class: str) -> str:
    """Return pool_{continent_snake}_{class}."""
    return f"pool_{continent.lower().replace(' ', '_')}_{pool_class}"


def _encounter_ids(
    node_type: NodeType, continent: str
) -> tuple[str | None, str | None, str | None]:
    """Return (enemy_pool_id, reward_table_id, augment_pool_id) for a node type."""
    match node_type:
        case NodeType.FIGHT:
            return _pool_id(continent, "standard"), None, None
        case NodeType.REWARD:
            return _pool_id(continent, "standard"), "reward_basic", None
        case NodeType.AUGMENT:
            return None, None, "augment_basic"
        case NodeType.SUPPLY:
            return None, None, None
        case NodeType.CHALLENGE:
            return _pool_id(continent, "elite"), None, None
        case NodeType.BOSS_FIGHT:
            return _pool_id(continent, "boss"), None, None
        case _:
            return None, None, None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_route() -> list[Node]:
    """Return a fresh list of 50 UPCOMING nodes in route order."""
    nodes: list[Node] = []
    index = 1
    for stage in STAGES:
        for city_id, node_type in zip(stage.node_cities, stage.node_types):
            city_def = CITIES[city_id]
            enemy_pool_id, reward_table_id, augment_pool_id = _encounter_ids(
                node_type, stage.name
            )
            nodes.append(
                Node(
                    id=f"node_{index:02d}",
                    index=index,
                    city=city_def.name,
                    weather=city_def.default_weather,
                    node_type=node_type,
                    state=NodeState.UPCOMING,
                    enemy_pool_id=enemy_pool_id,
                    reward_table_id=reward_table_id,
                    augment_pool_id=augment_pool_id,
                )
            )
            index += 1
    return nodes


def get_city(city_id: str) -> CityDef:
    """Look up a city by id; raises KeyError with a clear message on miss."""
    try:
        return CITIES[city_id]
    except KeyError:
        raise KeyError(f"Unknown city id: {city_id!r}. Valid ids: {sorted(CITIES)}")


def stage_of(node_index: int) -> StageDef:
    """Return the StageDef that contains the given 1-based node index."""
    offset = 0
    for stage in STAGES:
        stage_len = len(stage.node_cities)
        if offset < node_index <= offset + stage_len:
            return stage
        offset += stage_len
    raise ValueError(
        f"node_index {node_index!r} is out of range [1, {ROUTE_NODE_COUNT}]."
    )


# ---------------------------------------------------------------------------
# Module-load self-consistency assertions
# ---------------------------------------------------------------------------

def _assert_invariants() -> None:
    # All city ids in stages must exist in CITIES
    all_stage_city_ids: list[str] = []
    for stage in STAGES:
        assert len(stage.node_cities) == len(stage.node_types), (
            f"Stage {stage.index}: node_cities/node_types length mismatch"
        )
        for city_id in stage.node_cities:
            assert city_id in CITIES, f"Stage {stage.index}: unknown city id {city_id!r}"
            all_stage_city_ids.append(city_id)

    # Every city used exactly once
    assert len(all_stage_city_ids) == len(set(all_stage_city_ids)), (
        "Duplicate city ids detected across stages"
    )

    # Total count matches constant
    route = build_route()
    assert len(route) == ROUTE_NODE_COUNT, (
        f"Expected {ROUTE_NODE_COUNT} nodes, got {len(route)}"
    )


_assert_invariants()
