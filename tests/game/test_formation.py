"""Tests for enemy formation planner (T24).

Verifies:
  - Determinism: same squad → same formation
  - Role correctness: frontline col < backline col (closer to player)
  - Center-out packing
  - Flank placement at edge rows
  - Boss placement at authored position with displacement
  - Valid layouts for various squad sizes
  - No duplicate positions, no off-board coordinates
  - Overflow handling
"""

from __future__ import annotations

import pytest

from src.game.content import EnemyDef, ENEMY_DEF_BY_ID, _ENEMY_DEFS
from src.game.formation import (
    BOARD_HEIGHT,
    COL_BACK,
    COL_FRONT,
    COL_MID,
    PlacementRole,
    classify_role,
    plan_enemy_formation,
    _center_out_rows,
)
from src.game.models import CombatPieceState, WeatherState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_piece(piece_id: str, tier: int = 3) -> CombatPieceState:
    """Create a minimal CombatPieceState for testing."""
    return CombatPieceState(
        piece_id=piece_id,
        is_enemy=True,
        affinity=WeatherState.CLEAR,
        tier=tier,
        level=1,
        max_hp=100,
        hp=100,
        strength=50,
        intelligence=50,
        attack_speed=100,
        move_speed=90,
        mana_regen=10,
        threat=60,
        armor=25,
        resistance=25,
        attack_range=2,
        ability_cost=36_000,
    )


def _make_enemy_def(
    id: str,
    range_: str = "melee",
    durability: str = "standard",
    primary_stat: str = "str",
) -> EnemyDef:
    """Create a minimal EnemyDef for testing."""
    return EnemyDef(
        id=id,
        name=id,
        affinity=WeatherState.CLEAR,
        tier=3,
        primary_stat=primary_stat,
        range_=range_,
        durability=durability,
        playstyle="auto",
        tags=frozenset({"human"}),
        active_ability="",
        passive_ability="",
    )


def _plan_by_index(
    pieces: list[CombatPieceState],
    enemy_defs_by_id: dict[str, EnemyDef],
    *,
    boss_position: tuple[int, int] | None = None,
    board_height: int = BOARD_HEIGHT,
) -> dict[int, tuple[int, int]]:
    for index, piece in enumerate(pieces):
        piece.speed_tiebreaker = index
    return plan_enemy_formation(
        pieces,
        enemy_defs_by_id,
        boss_position=boss_position,
        board_height=board_height,
    )


def _plan_by_unique_piece_id(
    pieces: list[CombatPieceState],
    enemy_defs_by_id: dict[str, EnemyDef],
    *,
    boss_position: tuple[int, int] | None = None,
    board_height: int = BOARD_HEIGHT,
) -> dict[str, tuple[int, int]]:
    """Plan formation and map positions by piece_id (unique ids only)."""
    assert len({piece.piece_id for piece in pieces}) == len(pieces)
    placement_by_index = _plan_by_index(
        pieces,
        enemy_defs_by_id,
        boss_position=boss_position,
        board_height=board_height,
    )
    placement_by_piece_id: dict[str, tuple[int, int]] = {}
    for piece in pieces:
        pos = placement_by_index.get(piece.speed_tiebreaker)
        assert pos is not None
        placement_by_piece_id[piece.piece_id] = pos
    return placement_by_piece_id


# ---------------------------------------------------------------------------
# Role classification tests
# ---------------------------------------------------------------------------


class TestClassifyRole:
    def test_tanky_hp_is_frontline(self):
        d = _make_enemy_def("tank", durability="tanky_hp")
        assert classify_role(d) == PlacementRole.FRONTLINE

    def test_tanky_arm_is_frontline(self):
        d = _make_enemy_def("tank", durability="tanky_arm")
        assert classify_role(d) == PlacementRole.FRONTLINE

    def test_melee_squishy_is_flank(self):
        d = _make_enemy_def("assassin", range_="melee", durability="squishy")
        assert classify_role(d) == PlacementRole.FLANK

    def test_melee_standard_is_midline(self):
        d = _make_enemy_def("warrior", range_="melee", durability="standard")
        assert classify_role(d) == PlacementRole.MIDLINE

    def test_ranged_standard_is_backline(self):
        d = _make_enemy_def("mage", range_="ranged", durability="standard")
        assert classify_role(d) == PlacementRole.BACKLINE

    def test_ranged_squishy_is_backline(self):
        d = _make_enemy_def("mage", range_="ranged", durability="squishy")
        assert classify_role(d) == PlacementRole.BACKLINE

    def test_hybrid_tank_dmg_is_frontline(self):
        """Hybrid-Tank/DMG: tanky durability → FRONTLINE."""
        d = _make_enemy_def("hybrid", range_="melee", durability="tanky_hp", primary_stat="hybrid")
        assert classify_role(d) == PlacementRole.FRONTLINE


class TestClassifyRealRoster:
    """Verify classification of actual roster entries."""

    def test_heavy_knight_is_frontline(self):
        d = ENEMY_DEF_BY_ID["enemy_heavy_knight"]
        assert classify_role(d) == PlacementRole.FRONTLINE

    def test_conscript_is_midline(self):
        d = ENEMY_DEF_BY_ID["enemy_conscript"]
        assert classify_role(d) == PlacementRole.MIDLINE

    def test_spymaster_is_flank(self):
        d = ENEMY_DEF_BY_ID["enemy_spymaster"]
        assert classify_role(d) == PlacementRole.FLANK

    def test_battlemage_is_backline(self):
        d = ENEMY_DEF_BY_ID["enemy_battlemage"]
        assert classify_role(d) == PlacementRole.BACKLINE

    def test_hollowed_wisp_is_flank(self):
        d = ENEMY_DEF_BY_ID["enemy_hollowed_wisp"]
        assert classify_role(d) == PlacementRole.FLANK

    def test_shroud_killer_is_flank(self):
        d = ENEMY_DEF_BY_ID["enemy_shroud_killer"]
        assert classify_role(d) == PlacementRole.FLANK

    def test_dredge_hulk_is_frontline(self):
        d = ENEMY_DEF_BY_ID["enemy_dredge_hulk"]
        assert classify_role(d) == PlacementRole.FRONTLINE

    def test_picket_is_backline(self):
        d = ENEMY_DEF_BY_ID["enemy_picket"]
        assert classify_role(d) == PlacementRole.BACKLINE


# ---------------------------------------------------------------------------
# Center-out row tests
# ---------------------------------------------------------------------------


class TestCenterOutRows:
    def test_single(self):
        center = BOARD_HEIGHT // 2
        assert _center_out_rows(1, BOARD_HEIGHT) == [center]

    def test_two(self):
        center = BOARD_HEIGHT // 2
        assert _center_out_rows(2, BOARD_HEIGHT) == [center, center - 1]

    def test_three(self):
        center = BOARD_HEIGHT // 2
        assert _center_out_rows(3, BOARD_HEIGHT) == [center, center - 1, center + 1]

    def test_full_board(self):
        rows = _center_out_rows(BOARD_HEIGHT, BOARD_HEIGHT)
        assert len(rows) == BOARD_HEIGHT
        assert rows[0] == BOARD_HEIGHT // 2  # center first
        assert set(rows) == set(range(BOARD_HEIGHT))


# ---------------------------------------------------------------------------
# Formation planner tests
# ---------------------------------------------------------------------------


class TestFormationDeterminism:
    def test_same_squad_same_formation(self):
        """Identical squads produce identical formations."""
        pieces = [
            _make_piece("enemy_conscript"),
            _make_piece("enemy_heavy_knight"),
            _make_piece("enemy_battlemage"),
        ]
        f1 = _plan_by_unique_piece_id(pieces, ENEMY_DEF_BY_ID)
        f2 = _plan_by_unique_piece_id(pieces, ENEMY_DEF_BY_ID)
        assert f1 == f2

    def test_order_independent(self):
        """Input order doesn't affect formation (sorted internally)."""
        pieces_a = [
            _make_piece("enemy_conscript"),
            _make_piece("enemy_heavy_knight"),
        ]
        pieces_b = [
            _make_piece("enemy_heavy_knight"),
            _make_piece("enemy_conscript"),
        ]
        f_a = _plan_by_unique_piece_id(pieces_a, ENEMY_DEF_BY_ID)
        f_b = _plan_by_unique_piece_id(pieces_b, ENEMY_DEF_BY_ID)
        assert f_a == f_b


class TestFormationRoleCorrectness:
    def test_frontline_closer_than_backline(self):
        """Frontline average column < backline average column."""
        pieces = [
            _make_piece("enemy_heavy_knight"),   # frontline (tanky_hp)
            _make_piece("enemy_battlemage"),       # backline (ranged, squishy)
        ]
        formation = _plan_by_unique_piece_id(pieces, ENEMY_DEF_BY_ID)
        tank_col = formation["enemy_heavy_knight"][0]
        mage_col = formation["enemy_battlemage"][0]
        assert tank_col < mage_col

    def test_midline_between_front_and_back(self):
        """Midline pieces at column 8 (between 7 and 9)."""
        pieces = [
            _make_piece("enemy_heavy_knight"),   # frontline
            _make_piece("enemy_conscript"),       # midline (melee, standard)
            _make_piece("enemy_battlemage"),       # backline
        ]
        formation = _plan_by_unique_piece_id(pieces, ENEMY_DEF_BY_ID)
        assert formation["enemy_heavy_knight"][0] == COL_FRONT
        assert formation["enemy_conscript"][0] == COL_MID
        assert formation["enemy_battlemage"][0] == COL_BACK


class TestFlankPlacement:
    def test_flankers_at_edge_rows(self):
        """Assassins placed at edge rows (0 or BOARD_HEIGHT - 1)."""
        pieces = [
            _make_piece("enemy_spymaster"),     # flank (melee, squishy)
            _make_piece("enemy_heavy_knight"),  # frontline (padding)
        ]
        formation = _plan_by_unique_piece_id(pieces, ENEMY_DEF_BY_ID)
        _, row = formation["enemy_spymaster"]
        assert row in (0, BOARD_HEIGHT - 1)

    def test_flankers_in_mid_or_back_columns(self):
        """Assassins placed in columns 8–9 (mid-to-back, not frontline)."""
        pieces = [
            _make_piece("enemy_spymaster"),
            _make_piece("enemy_hollowed_wisp"),
        ]
        formation = _plan_by_unique_piece_id(pieces, ENEMY_DEF_BY_ID)
        for pid in ("enemy_spymaster", "enemy_hollowed_wisp"):
            col, _ = formation[pid]
            assert col in (COL_MID, COL_BACK)

    def test_multiple_flankers(self):
        """Multiple assassins fill distinct edge positions."""
        pieces = [
            _make_piece("enemy_spymaster"),
            _make_piece("enemy_hollowed_wisp"),
        ]
        formation = _plan_by_unique_piece_id(pieces, ENEMY_DEF_BY_ID)
        pos1 = formation["enemy_spymaster"]
        pos2 = formation["enemy_hollowed_wisp"]
        assert pos1 != pos2


class TestBossPlacement:
    def test_boss_at_authored_position(self):
        """Boss placed at its authored spawn position."""
        boss = _make_piece("boss_holloway", tier=10)
        tank = _make_piece("enemy_heavy_knight")
        formation = _plan_by_unique_piece_id(
            [boss, tank],
            ENEMY_DEF_BY_ID,
            boss_position=(7, 3),
        )
        assert formation["boss_holloway"] == (7, 3)

    def test_boss_displaces_occupant(self):
        """Boss takes authored position; displaced piece goes elsewhere."""
        boss = _make_piece("boss_vance", tier=10)
        # Tank would normally go to (7, 3) — center of frontline
        tank = _make_piece("enemy_heavy_knight")
        formation = _plan_by_unique_piece_id(
            [boss, tank],
            ENEMY_DEF_BY_ID,
            boss_position=(7, 3),
        )
        assert formation["boss_vance"] == (7, 3)
        # Tank displaced to another cell
        assert formation["enemy_heavy_knight"] != (7, 3)
        # Still on board
        col, row = formation["enemy_heavy_knight"]
        assert COL_FRONT <= col <= COL_BACK
        assert 0 <= row < BOARD_HEIGHT

    def test_ranged_boss_at_backline(self):
        """Ranged boss at backline center."""
        boss = _make_piece("boss_vance", tier=10)
        formation = _plan_by_unique_piece_id(
            [boss],
            ENEMY_DEF_BY_ID,
            boss_position=(9, 3),
        )
        assert formation["boss_vance"] == (9, 3)

    def test_boss_default_position(self):
        """Boss without explicit position defaults to center-back (9, 3)."""
        boss = _make_piece("boss_test", tier=10)
        formation = _plan_by_unique_piece_id(
            [boss],
            ENEMY_DEF_BY_ID,
            boss_position=None,
        )
        assert formation["boss_test"] == (9, 3)


class TestSquadSizes:
    """Validate formations across different squad sizes."""

    @pytest.mark.parametrize("size", [1, 2, 3, 5, 8, 11])
    def test_valid_layout(self, size: int):
        """All squad sizes produce valid layouts with no duplicates or off-board."""
        # Build a varied squad
        roster_ids = [d.id for d in _ENEMY_DEFS if d.tier != 10]
        selected = roster_ids[:size]
        pieces = [_make_piece(pid) for pid in selected]

        formation = _plan_by_unique_piece_id(pieces, ENEMY_DEF_BY_ID)

        # All pieces placed
        assert len(formation) == size
        # No duplicate positions
        positions = list(formation.values())
        assert len(set(positions)) == size
        # All on board in enemy zone
        for col, row in positions:
            assert COL_FRONT <= col <= COL_BACK
            assert 0 <= row < BOARD_HEIGHT


class TestDuplicatePieceIds:
    def test_duplicate_ids_all_instances_are_placed_without_collisions(self):
        pieces = [
            _make_piece("enemy_conscript"),
            _make_piece("enemy_conscript"),
            _make_piece("enemy_heavy_knight"),
        ]
        formation = _plan_by_index(pieces, ENEMY_DEF_BY_ID)
        positions = [formation[piece.speed_tiebreaker] for piece in pieces]

        assert len(positions) == len(pieces)
        assert len(set(positions)) == len(pieces)


class TestOverflow:
    def test_frontline_overflow_to_midline(self):
        """More than 7 frontline pieces overflow to column 8."""
        # Create 8 tanky enemies
        defs = {}
        pieces = []
        for i in range(8):
            pid = f"test_tank_{i}"
            defs[pid] = _make_enemy_def(pid, durability="tanky_hp")
            pieces.append(_make_piece(pid))

        formation = _plan_by_unique_piece_id(pieces, defs)

        cols = [formation[f"test_tank_{i}"][0] for i in range(8)]
        # 7 should be in col 7, 1 overflows to col 8
        assert cols.count(COL_FRONT) == 7
        assert cols.count(COL_MID) == 1

    def test_no_duplicate_positions_with_overflow(self):
        """Overflow doesn't produce duplicate positions."""
        defs = {}
        pieces = []
        for i in range(10):
            pid = f"test_tank_{i}"
            defs[pid] = _make_enemy_def(pid, durability="tanky_hp")
            pieces.append(_make_piece(pid))

        formation = _plan_by_unique_piece_id(pieces, defs)
        positions = list(formation.values())
        assert len(set(positions)) == 10


class TestNoOffBoard:
    def test_all_positions_valid(self):
        """Formation never places pieces outside the board."""
        # Use full real roster (minus tier 10)
        real_pieces = [_make_piece(d.id) for d in _ENEMY_DEFS if d.tier != 10][:15]
        formation = _plan_by_unique_piece_id(real_pieces, ENEMY_DEF_BY_ID)

        for pid, (col, row) in formation.items():
            assert 0 <= col < 10, f"{pid} off-board: col={col}"
            assert 0 <= row < BOARD_HEIGHT, f"{pid} off-board: row={row}"
            assert col >= COL_FRONT, f"{pid} in player zone: col={col}"


class TestFallbackForUnknownEnemies:
    def test_unknown_id_defaults_to_midline(self):
        """Enemies with unknown IDs are placed (fallback to midline)."""
        pieces = [_make_piece("unknown_enemy_xyz")]
        formation = _plan_by_unique_piece_id(pieces, ENEMY_DEF_BY_ID)
        assert "unknown_enemy_xyz" in formation
        col, row = formation["unknown_enemy_xyz"]
        assert col == COL_MID  # defaults to midline

    def test_empty_squad(self):
        """Empty squad returns empty formation."""
        assert _plan_by_unique_piece_id([], ENEMY_DEF_BY_ID) == {}
