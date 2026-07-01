"""Affinity-Clash heatmap — `clash_matrix_specs` pure data + builder (V.2/V.63).

Asserts structure (shape / multipliers / tone / category), never pixels (mirrors
`test_route_map.py` / `test_run_summary.py`). The headline guard: every cell's
`mult` equals `weather_effects.damage_modifier` — the heatmap reads the live rule,
it never re-types the numbers (source-of-truth, mirrors V.38).
"""

from __future__ import annotations

import flet as ft

from src.game.models import WeatherState
from src.game.weather_effects import RingRelation, damage_modifier, ring_relation
from src.ui.theme import DANGER, SUCCESS, TEXT_MUTED
from src.viz.affinity_clash_heatmap import (
    AXIS_ORDER,
    ClashCellSpec,
    build_affinity_clash_heatmap,
    clash_matrix_specs,
)


def test_matrix_is_square_over_axis_order():
    grid = clash_matrix_specs()
    assert len(grid) == len(AXIS_ORDER)
    assert all(len(row) == len(AXIS_ORDER) for row in grid)
    # Rows = attacker, cols = defender, in AXIS_ORDER.
    for r, attacker in enumerate(AXIS_ORDER):
        for c, defender in enumerate(AXIS_ORDER):
            cell = grid[r][c]
            assert cell.attacker == attacker
            assert cell.defender == defender


def test_cell_mult_matches_damage_modifier():
    """Source-of-truth: the heatmap can't drift from the combat multiplier."""
    for row in clash_matrix_specs():
        for cell in row:
            assert cell.mult == damage_modifier(cell.attacker, cell.defender)
            assert cell.relation == ring_relation(cell.attacker, cell.defender)


def test_diagonal_is_self_and_neutral_value():
    grid = {(c.attacker, c.defender): c for row in clash_matrix_specs() for c in row}
    for aff in AXIS_ORDER:
        cell = grid[(aff, aff)]
        assert cell.mult == 1.0
        assert cell.category == "neutral"


def test_clear_row_and_column_are_inert():
    grid = {(c.attacker, c.defender): c for row in clash_matrix_specs() for c in row}
    for aff in AXIS_ORDER:
        assert grid[(WeatherState.CLEAR, aff)].mult == 1.0
        assert grid[(aff, WeatherState.CLEAR)].mult == 1.0
        assert grid[(WeatherState.CLEAR, aff)].relation == RingRelation.NEUTRAL


def test_tone_tracks_favor_neutral_clash():
    for row in clash_matrix_specs():
        for cell in row:
            if cell.category == "favor":
                assert cell.mult > 1.0 and cell.tone == SUCCESS
            elif cell.category == "clash":
                assert cell.mult < 1.0 and cell.tone == DANGER
            else:
                assert cell.mult == 1.0 and cell.tone == TEXT_MUTED


def test_known_matchup_values():
    grid = {(c.attacker, c.defender): c for row in clash_matrix_specs() for c in row}
    # MIST is the primary predator of THUNDER (per CYCLE_ORDER) → 1.30.
    assert grid[(WeatherState.MIST, WeatherState.THUNDER)].mult == 1.30
    assert grid[(WeatherState.MIST, WeatherState.THUNDER)].category == "favor"
    # ...and primary prey of CLOUDY → 0.70.
    assert grid[(WeatherState.MIST, WeatherState.CLOUDY)].mult == 0.70
    assert grid[(WeatherState.MIST, WeatherState.CLOUDY)].category == "clash"


def test_specs_deterministic_and_typed():
    assert clash_matrix_specs() == clash_matrix_specs()
    assert isinstance(clash_matrix_specs()[0][0], ClashCellSpec)


def test_builder_returns_control_without_highlight():
    assert isinstance(build_affinity_clash_heatmap(), ft.Control)


def test_builder_accepts_team_highlight():
    ctrl = build_affinity_clash_heatmap(
        highlight={WeatherState.RAIN, WeatherState.SNOW}
    )
    assert isinstance(ctrl, ft.Control)
