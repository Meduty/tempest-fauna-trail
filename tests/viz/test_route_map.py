"""Tests for viz/route_map.py — the pure route-node spec builder (T.11).

Asserts structure/counts/coords, not pixels (CLAUDE.md: test logic, not Flet).
"""
from __future__ import annotations

from src.game.models import NodeState, NodeType, WeatherState
from src.game.run_init import champion_offer, new_run
from src.viz.route_map import (
    MARGIN_X,
    NODE_SPACING,
    RouteNodeSpec,
    route_node_specs,
)


def _fresh_run():
    seed = 12345
    return new_run(seed, champion_offer(seed)[0])


def test_spec_per_node_in_index_order() -> None:
    run = _fresh_run()
    specs = route_node_specs(run, lambda n: n.weather)
    assert len(specs) == len(run.route)
    assert [s.index for s in specs] == sorted(n.index for n in run.route)


def test_coords_are_evenly_spaced() -> None:
    run = _fresh_run()
    specs = route_node_specs(run, lambda n: n.weather)
    assert specs[0].x == MARGIN_X
    for col, s in enumerate(specs):
        assert s.x == MARGIN_X + col * NODE_SPACING
        assert s.y == specs[0].y  # single horizontal lane


def test_current_node_selected_by_default() -> None:
    run = _fresh_run()
    specs = route_node_specs(run, lambda n: n.weather)
    selected = [s.index for s in specs if s.is_selected]
    assert selected == [run.current_node_index]


def test_explicit_selection_overrides_current() -> None:
    run = _fresh_run()
    specs = route_node_specs(run, lambda n: n.weather, selected_index=5)
    assert [s.index for s in specs if s.is_selected] == [5]


def test_state_tints_track_node_state() -> None:
    run = _fresh_run()
    # Node 1 is CURRENT at run start; the rest UPCOMING.
    specs = route_node_specs(run, lambda n: n.weather)
    by_index = {s.index: s for s in specs}
    assert by_index[run.current_node_index].state is NodeState.CURRENT
    assert all(
        s.state is NodeState.UPCOMING
        for s in specs if s.index != run.current_node_index
    )


def test_boss_nodes_flagged() -> None:
    run = _fresh_run()
    specs = route_node_specs(run, lambda n: n.weather)
    boss_indices = {n.index for n in run.route if n.node_type is NodeType.BOSS_FIGHT}
    assert boss_indices, "route should contain at least one boss node"
    assert {s.index for s in specs if s.is_boss} == boss_indices


def test_weather_lookup_is_applied() -> None:
    run = _fresh_run()
    # Force every node to render THUNDER regardless of its default.
    specs = route_node_specs(run, lambda n: WeatherState.THUNDER)
    assert all(s.weather is WeatherState.THUNDER for s in specs)
    assert all(s.weather_known for s in specs)


def test_unknown_weather_is_none_not_default() -> None:
    """UNKNOWN (unfetched) nodes carry weather=None — never the city default."""
    run = _fresh_run()
    specs = route_node_specs(run, lambda n: None)  # cache UNKNOWN for all
    assert all(s.weather is None for s in specs)
    assert all(not s.weather_known for s in specs)
    # Crucially, the spec did NOT fall back to the node's own default weather.
    by_index = {s.index: s for s in specs}
    for node in run.route:
        assert by_index[node.index].weather is not node.weather or node.weather is None


def test_mixed_known_and_unknown() -> None:
    run = _fresh_run()
    # Even node indexes known (CLEAR), odd unknown.
    specs = route_node_specs(
        run, lambda n: WeatherState.CLEAR if n.index % 2 == 0 else None
    )
    by_index = {s.index: s for s in specs}
    for node in run.route:
        if node.index % 2 == 0:
            assert by_index[node.index].weather_known
        else:
            assert not by_index[node.index].weather_known


def test_spec_is_frozen() -> None:
    run = _fresh_run()
    spec = route_node_specs(run, lambda n: n.weather)[0]
    assert isinstance(spec, RouteNodeSpec)
    try:
        spec.x = 0  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("RouteNodeSpec should be immutable")
