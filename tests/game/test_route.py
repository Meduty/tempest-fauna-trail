"""Tests for src/game/route.py (T4)."""
from __future__ import annotations

import math

import pytest

from src.game.models import NodeState, NodeType, RunStatus, WeatherState, Run
from src.game.route import (
    CITIES,
    ROUTE_NODE_COUNT,
    STAGES,
    CityDef,
    StageDef,
    build_route,
    get_city,
    stage_of,
)


# ---------------------------------------------------------------------------
# 7.1 Shape
# ---------------------------------------------------------------------------


class TestShape:
    def test_node_count(self):
        nodes = build_route()
        assert len(nodes) == 50
        assert ROUTE_NODE_COUNT == 50

    def test_indexes_contiguous_from_one(self):
        nodes = build_route()
        indexes = [n.index for n in nodes]
        assert indexes == list(range(1, 51))

    def test_node_ids_unique_and_formatted(self):
        nodes = build_route()
        ids = [n.id for n in nodes]
        assert len(set(ids)) == 50
        for node in nodes:
            assert node.id == f"node_{node.index:02d}"


# ---------------------------------------------------------------------------
# 7.2 Stage structure
# ---------------------------------------------------------------------------


class TestStageStructure:
    def test_stage1_node_type_sequence(self):
        nodes = build_route()
        stage1_nodes = nodes[:10]
        expected = [
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
        ]
        assert [n.node_type for n in stage1_nodes] == expected

    def test_stages_2_to_6_node_type_sequence(self):
        nodes = build_route()
        default_seq = [
            NodeType.FIGHT,
            NodeType.AUGMENT,
            NodeType.FIGHT,
            NodeType.SUPPLY,
            NodeType.FIGHT,
            NodeType.CHALLENGE,
            NodeType.REWARD,
            NodeType.BOSS_FIGHT,
        ]
        for stage_idx in range(2, 7):
            offset = 10 + (stage_idx - 2) * 8
            stage_nodes = nodes[offset: offset + 8]
            assert [n.node_type for n in stage_nodes] == default_seq, (
                f"Stage {stage_idx} sequence mismatch"
            )

    def test_every_stage_ends_with_boss(self):
        nodes = build_route()
        # Last node of each stage
        boss_indexes = [10, 18, 26, 34, 42, 50]
        for idx in boss_indexes:
            node = nodes[idx - 1]
            assert node.node_type == NodeType.BOSS_FIGHT, (
                f"Node {idx} should be BOSS_FIGHT"
            )

    def test_exactly_six_challenge_nodes(self):
        nodes = build_route()
        challenges = [n for n in nodes if n.node_type == NodeType.CHALLENGE]
        assert len(challenges) == 6

    def test_node1_is_lisbon(self):
        nodes = build_route()
        assert nodes[0].city == "Lisbon"
        assert nodes[0].index == 1

    def test_node10_is_vienna_boss(self):
        nodes = build_route()
        assert nodes[9].city == "Vienna"
        assert nodes[9].node_type == NodeType.BOSS_FIGHT

    def test_node50_is_new_york_boss(self):
        nodes = build_route()
        assert nodes[49].city == "New York"
        assert nodes[49].node_type == NodeType.BOSS_FIGHT
        assert nodes[49].index == 50

    def test_stage_affinities_match_spec(self):
        expected = {
            1: WeatherState.CLEAR,
            2: WeatherState.MIST,
            3: WeatherState.THUNDER,
            4: WeatherState.CLOUDY,
            5: WeatherState.RAIN,
            6: WeatherState.SNOW,
        }
        for stage in STAGES:
            assert stage.affinity == expected[stage.index], (
                f"Stage {stage.index} affinity mismatch"
            )

    def test_all_six_weather_states_used_as_affinities(self):
        affinities = {stage.affinity for stage in STAGES}
        assert affinities == set(WeatherState)


# ---------------------------------------------------------------------------
# 7.3 City data
# ---------------------------------------------------------------------------


class TestCityData:
    def test_cities_catalog_has_50_entries(self):
        assert len(CITIES) == 50

    def test_city_fields_non_empty(self):
        for city_id, city in CITIES.items():
            assert city.name, f"{city_id}: name is empty"
            assert city.country, f"{city_id}: country is empty"
            assert city.continent, f"{city_id}: continent is empty"

    def test_city_coordinates_valid_range(self):
        for city_id, city in CITIES.items():
            assert -90.0 <= city.latitude <= 90.0, f"{city_id}: lat out of range"
            assert -180.0 <= city.longitude <= 180.0, f"{city_id}: lon out of range"
            assert math.isfinite(city.latitude), f"{city_id}: lat not finite"
            assert math.isfinite(city.longitude), f"{city_id}: lon not finite"

    def test_every_node_city_resolves_to_citydef(self):
        nodes = build_route()
        city_names = {c.name for c in CITIES.values()}
        for node in nodes:
            assert node.city in city_names, f"Node {node.index} city {node.city!r} not in CITIES"

    def test_each_city_used_exactly_once(self):
        nodes = build_route()
        city_names = [n.city for n in nodes]
        assert len(city_names) == len(set(city_names)), "Duplicate city names in route"

    def test_all_nodes_start_upcoming(self):
        nodes = build_route()
        for node in nodes:
            assert node.state == NodeState.UPCOMING


# ---------------------------------------------------------------------------
# 7.4 Encounter ids
# ---------------------------------------------------------------------------


class TestEncounterIds:
    def test_fight_nodes_have_standard_pool(self):
        nodes = build_route()
        for node in nodes:
            if node.node_type == NodeType.FIGHT:
                assert node.enemy_pool_id is not None
                assert node.enemy_pool_id.endswith("_standard")

    def test_reward_nodes_have_standard_pool_and_reward_basic(self):
        nodes = build_route()
        for node in nodes:
            if node.node_type == NodeType.REWARD:
                assert node.enemy_pool_id is not None
                assert node.enemy_pool_id.endswith("_standard")
                assert node.reward_table_id == "reward_basic"

    def test_challenge_nodes_have_elite_pool(self):
        nodes = build_route()
        for node in nodes:
            if node.node_type == NodeType.CHALLENGE:
                assert node.enemy_pool_id is not None
                assert node.enemy_pool_id.endswith("_elite")

    def test_boss_nodes_have_boss_pool(self):
        nodes = build_route()
        for node in nodes:
            if node.node_type == NodeType.BOSS_FIGHT:
                assert node.enemy_pool_id is not None
                assert node.enemy_pool_id.endswith("_boss")

    def test_augment_nodes_have_augment_basic(self):
        nodes = build_route()
        for node in nodes:
            if node.node_type == NodeType.AUGMENT:
                assert node.augment_pool_id == "augment_basic"
                assert node.enemy_pool_id is None

    def test_supply_nodes_have_no_encounter_ids(self):
        nodes = build_route()
        for node in nodes:
            if node.node_type == NodeType.SUPPLY:
                assert node.enemy_pool_id is None
                assert node.reward_table_id is None
                assert node.augment_pool_id is None

    def test_pool_ids_match_continent_pattern(self):
        """pool_{continent_snake}_{class} format for encounter nodes."""
        nodes = build_route()
        offset = 0
        for stage in STAGES:
            continent_snake = stage.name.lower().replace(" ", "_")
            for i, node in enumerate(nodes[offset: offset + len(stage.node_cities)]):
                if node.enemy_pool_id is not None:
                    assert node.enemy_pool_id.startswith(f"pool_{continent_snake}_"), (
                        f"Node {node.index} pool id {node.enemy_pool_id!r} "
                        f"doesn't match continent {stage.name!r}"
                    )
            offset += len(stage.node_cities)


# ---------------------------------------------------------------------------
# 7.5 Determinism and isolation
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_two_calls_produce_equal_dicts(self):
        r1 = build_route()
        r2 = build_route()
        assert [n.to_dict() for n in r1] == [n.to_dict() for n in r2]

    def test_mutation_does_not_affect_next_call(self):
        r1 = build_route()
        r1[0].state = NodeState.CURRENT
        r2 = build_route()
        assert r2[0].state == NodeState.UPCOMING


# ---------------------------------------------------------------------------
# 7.6 Run integration
# ---------------------------------------------------------------------------


class TestRunIntegration:
    def test_build_route_accepted_by_run(self):
        nodes = build_route()
        nodes[0].state = NodeState.CURRENT
        run = Run(
            run_id="test_run",
            schema_version=1,
            seed=42,
            status=RunStatus.IN_PROGRESS,
            roster=[],
            bench=[],
            route=nodes,
            current_node_index=1,
        )
        assert run.route[0].state == NodeState.CURRENT


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


class TestLookupHelpers:
    def test_get_city_known(self):
        city = get_city("city_tokyo")
        assert city.name == "Tokyo"
        assert city.country == "Japan"

    def test_get_city_unknown_raises_key_error(self):
        with pytest.raises(KeyError):
            get_city("city_atlantis")

    def test_stage_of_node1(self):
        assert stage_of(1).name == "Europe"

    def test_stage_of_node10(self):
        assert stage_of(10).name == "Europe"

    def test_stage_of_node11(self):
        assert stage_of(11).name == "Africa"

    def test_stage_of_node50(self):
        assert stage_of(50).name == "North America"

    def test_stage_of_out_of_range(self):
        with pytest.raises(ValueError):
            stage_of(0)
        with pytest.raises(ValueError):
            stage_of(51)

    def test_stage_of_all_nodes_consistent(self):
        """stage_of(node.index).name matches the stage that produced the node."""
        offset = 0
        for stage in STAGES:
            for i in range(len(stage.node_cities)):
                node_index = offset + i + 1
                assert stage_of(node_index).index == stage.index
            offset += len(stage.node_cities)


# ---------------------------------------------------------------------------
# city_id_for_node / ROUTE_CITY_IDS (T.11)
# ---------------------------------------------------------------------------

def test_route_city_ids_count_and_uniqueness() -> None:
    from src.game.route import ROUTE_CITY_IDS
    assert len(ROUTE_CITY_IDS) == ROUTE_NODE_COUNT
    assert len(set(ROUTE_CITY_IDS)) == ROUTE_NODE_COUNT  # each city once


def test_city_id_for_node_matches_build_route_order() -> None:
    from src.game.route import city_id_for_node
    route = build_route()
    for node in route:
        cid = city_id_for_node(node.index)
        assert CITIES[cid].name == node.city  # id backs the node's city name


def test_city_id_for_node_rejects_out_of_range() -> None:
    from src.game.route import city_id_for_node
    with pytest.raises(ValueError):
        city_id_for_node(0)
    with pytest.raises(ValueError):
        city_id_for_node(ROUTE_NODE_COUNT + 1)
