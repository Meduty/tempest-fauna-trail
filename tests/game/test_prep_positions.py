"""T.23a — `validate_team_positions` (V.68) + Auto-Place byte-identity (V.62/V.2).

The Prep view confines the player's hand-placement to the allied deployment zone
(columns 0..2) and validates it team-only before combat; Auto-Place must reproduce
the engine's default formation exactly.
"""

from __future__ import annotations

import pytest

from src.game.combat.engine import BOARD_HEIGHT
from src.game.combat.resolve import build_combat
from src.game.content import CHAMPION_ROSTER, ENEMY_ROSTER
from src.game.loadout import ALLIED_ZONE_MAX_Q, validate_team_positions
from src.game.models import WeatherState


def _team(n: int):
    return list(CHAMPION_ROSTER.values())[:n]


def _enemies(n: int):
    return list(ENEMY_ROSTER.values())[:n]


# --- validate_team_positions (V.68) ----------------------------------------

def test_valid_layout_passes():
    team = _team(3)
    positions = {team[0].id: (0, 0), team[1].id: (1, 2), team[2].id: (2, 6)}
    validate_team_positions(team, positions)  # no raise


def test_empty_positions_passes():
    validate_team_positions(_team(3), {})  # Auto-Place ⇒ default formation


def test_off_zone_column_raises():
    team = _team(2)
    # q == ALLIED_ZONE_MAX_Q is the first cell *outside* the allied zone.
    with pytest.raises(ValueError, match="deployment zone"):
        validate_team_positions(team, {team[0].id: (ALLIED_ZONE_MAX_Q, 0)})


def test_off_board_row_raises():
    team = _team(1)
    with pytest.raises(ValueError, match="off-board"):
        validate_team_positions(team, {team[0].id: (0, BOARD_HEIGHT)})


def test_duplicate_cell_raises():
    team = _team(2)
    with pytest.raises(ValueError, match="both placed on cell"):
        validate_team_positions(team, {team[0].id: (0, 0), team[1].id: (0, 0)})


def test_unknown_champion_id_raises():
    team = _team(2)
    with pytest.raises(ValueError, match="no champion on the team"):
        validate_team_positions(team, {"definitely_not_a_champion": (0, 0)})


def test_enemy_zone_rejected():
    """A cell in the enemy half (columns 7..9) is outside the allied zone."""
    team = _team(1)
    with pytest.raises(ValueError, match="deployment zone"):
        validate_team_positions(team, {team[0].id: (8, 3)})


# --- Auto-Place byte-identity (V.62/V.2) -----------------------------------

def _team_cells(ctx) -> dict[str, tuple[int, int]]:
    return {p.id: (p.position_q, p.position_r)
            for p in ctx.all_pieces() if not p.is_enemy}


def test_auto_place_matches_default_formation():
    """The Prep Auto-Place packing (champion i → (i//7, i%7)) must reproduce the
    engine's default `assign_spawns` formation exactly — so passing those explicit
    positions is byte-identical to positions=None (V.62)."""
    team = _team(8)  # 8 > BOARD_HEIGHT ⇒ spills into column 1, exercises packing
    enemies = _enemies(3)

    ctx_default, _ = build_combat(team, enemies, WeatherState.CLEAR, positions=None)
    default_cells = _team_cells(ctx_default)

    auto_place = {champ.id: (i // BOARD_HEIGHT, i % BOARD_HEIGHT)
                  for i, champ in enumerate(team)}
    # Sanity: Auto-Place stays inside the allied zone + passes validation.
    validate_team_positions(team, auto_place)

    ctx_explicit, _ = build_combat(team, enemies, WeatherState.CLEAR, positions=auto_place)
    assert _team_cells(ctx_explicit) == default_cells


def test_custom_layout_lands_at_given_cells():
    """A validated custom layout places each team piece at exactly its cell (V.62)."""
    team = _team(3)
    enemies = _enemies(3)
    layout = {team[0].id: (2, 0), team[1].id: (1, 3), team[2].id: (0, 6)}
    validate_team_positions(team, layout)
    ctx, _ = build_combat(team, enemies, WeatherState.CLEAR, positions=layout)
    cells = _team_cells(ctx)
    for cid, cell in layout.items():
        assert cells[cid] == cell
