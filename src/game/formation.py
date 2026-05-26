"""Enemy Formation Policy (T24).

Deterministic, role-aware formation planner. Takes a generated enemy squad
and assigns each piece to a hex coordinate on the right side of the board
(columns 7–9) based on archetype classification.

Formation goals:
  - Tanks form a shield wall at column 7 (closest to player)
  - Warriors and bruisers hold midline at column 8
  - Assassins flank at mid-to-backline edges (columns 8–9, edge rows)
  - Mages, marksmen, and supports hold backline at column 9
  - Bosses get per-boss authored positions

Pure function — no RNG, no Flet imports, no I/O (V.1, V.2).
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game.content import EnemyDef
    from src.game.models import CombatPieceState

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BOARD_WIDTH = 10
BOARD_HEIGHT = 7

# Enemy deployment columns (right side of board)
COL_FRONT = 7   # Foremost enemy column — closest to player
COL_MID = 8     # Middle enemy column
COL_BACK = 9    # Rearmost enemy column

CENTER_ROW = BOARD_HEIGHT // 2  # row 3 on a 7-row board

# Edge rows for flank placement
FLANK_ROWS = (0, BOARD_HEIGHT - 1)  # rows 0 and 6


# ---------------------------------------------------------------------------
# Placement roles
# ---------------------------------------------------------------------------


class PlacementRole(Enum):
    """Placement archetype determining column assignment."""
    FRONTLINE = "frontline"   # Tanks — absorb damage at the front
    MIDLINE = "midline"       # Warriors, bruisers — deal and take hits
    FLANK = "flank"           # Assassins — mid/back edge rows
    BACKLINE = "backline"     # Mages, marksmen, supports — stay behind


# ---------------------------------------------------------------------------
# Role classification
# ---------------------------------------------------------------------------


def classify_role(enemy_def: "EnemyDef") -> PlacementRole:
    """Classify an enemy definition into a placement role.

    Rules:
      - Tanky durability (tanky_hp, tanky_arm) → FRONTLINE
      - Melee + squishy (assassins) → FLANK (mid-to-back edges)
      - Melee + standard (warriors, bruisers) → MIDLINE
      - Ranged (mages, marksmen, supports) → BACKLINE
    """
    durability = enemy_def.durability
    range_ = enemy_def.range_

    # Tanks go front — they have the stats to absorb damage
    if durability in ("tanky_hp", "tanky_arm"):
        return PlacementRole.FRONTLINE

    # Melee squishy = assassin → flank (mid-to-back edges, not frontline)
    if range_ == "melee" and durability == "squishy":
        return PlacementRole.FLANK

    # Melee standard = warrior/bruiser → midline (behind tanks)
    if range_ == "melee":
        return PlacementRole.MIDLINE

    # Ranged = backline (mages, marksmen, supports)
    return PlacementRole.BACKLINE


# ---------------------------------------------------------------------------
# Row assignment helpers
# ---------------------------------------------------------------------------


def _center_out_rows(count: int, board_height: int = BOARD_HEIGHT) -> list[int]:
    """Return `count` row indices, center-out from the middle row.

    If count exceeds board_height, returns all rows (clamped).
    """
    count = min(count, board_height)
    center = board_height // 2
    rows: list[int] = [center]
    offset = 1
    while len(rows) < count:
        if center - offset >= 0:
            rows.append(center - offset)
        if len(rows) < count and center + offset < board_height:
            rows.append(center + offset)
        offset += 1
    return rows[:count]


def _nearest_free(
    target_col: int,
    target_row: int,
    occupied: set[tuple[int, int]],
    board_height: int = BOARD_HEIGHT,
) -> tuple[int, int] | None:
    """Find the nearest free cell to (target_col, target_row) within enemy columns.

    Searches in expanding rings: same column first, then adjacent columns.
    Returns None if no free cell exists (should not happen with 21 slots).
    """
    # Search columns in order of proximity to target
    col_order = sorted([COL_FRONT, COL_MID, COL_BACK], key=lambda c: abs(c - target_col))

    for col in col_order:
        # Search rows center-out from target_row
        for offset in range(board_height):
            for row in (target_row - offset, target_row + offset):
                if 0 <= row < board_height and (col, row) not in occupied:
                    return (col, row)
    return None


# ---------------------------------------------------------------------------
# Placement functions
# ---------------------------------------------------------------------------


def _place_band(
    pieces: list["CombatPieceState"],
    col: int,
    occupied: set[tuple[int, int]],
    placements: dict[str, tuple[int, int]],
    board_height: int = BOARD_HEIGHT,
    overflow_cols: tuple[int, ...] = (),
) -> None:
    """Place pieces in a column, center-out. Overflow to adjacent columns."""
    rows = _center_out_rows(board_height, board_height)

    for piece in pieces:
        placed = False
        # Try primary column first
        for row in rows:
            if (col, row) not in occupied:
                placements[piece.piece_id] = (col, row)
                occupied.add((col, row))
                placed = True
                break

        if not placed:
            # Overflow to adjacent columns
            for ov_col in overflow_cols:
                for row in rows:
                    if (ov_col, row) not in occupied:
                        placements[piece.piece_id] = (ov_col, row)
                        occupied.add((ov_col, row))
                        placed = True
                        break
                if placed:
                    break

        if not placed:
            # Last resort: any free cell in enemy zone
            pos = _nearest_free(col, CENTER_ROW, occupied, board_height)
            if pos is not None:
                placements[piece.piece_id] = pos
                occupied.add(pos)


def _place_flankers(
    flankers: list["CombatPieceState"],
    occupied: set[tuple[int, int]],
    placements: dict[str, tuple[int, int]],
    board_height: int = BOARD_HEIGHT,
) -> None:
    """Place assassins/flankers at mid-to-back edge rows.

    Flankers want to be at edge rows (0 and 6) in columns 8–9 (mid to back),
    allowing them to slip around the frontline and threaten the enemy backline.
    """
    # Preferred positions: alternate between column 8 and 9, at edge rows
    flank_positions = [
        (COL_MID, FLANK_ROWS[0]),      # col 8, row 0
        (COL_MID, FLANK_ROWS[1]),      # col 8, row 6
        (COL_BACK, FLANK_ROWS[0]),     # col 9, row 0
        (COL_BACK, FLANK_ROWS[1]),     # col 9, row 6
    ]

    for i, piece in enumerate(flankers):
        placed = False

        if i < len(flank_positions):
            col, row = flank_positions[i]
            if (col, row) not in occupied:
                placements[piece.piece_id] = (col, row)
                occupied.add((col, row))
                placed = True

        if not placed:
            # Find nearest free edge-adjacent cell
            for col, row in flank_positions:
                if (col, row) not in occupied:
                    placements[piece.piece_id] = (col, row)
                    occupied.add((col, row))
                    placed = True
                    break

        if not placed:
            # Fallback: any free cell near edges
            pos = _nearest_free(COL_MID, FLANK_ROWS[i % 2], occupied, board_height)
            if pos is not None:
                placements[piece.piece_id] = pos
                occupied.add(pos)


def _place_boss(
    boss: "CombatPieceState",
    boss_position: tuple[int, int],
    occupied: set[tuple[int, int]],
    placements: dict[str, tuple[int, int]],
    board_height: int = BOARD_HEIGHT,
) -> None:
    """Place boss at its authored position, displacing any occupant."""
    # Reserve the boss position first
    displaced_pid: str | None = None
    for pid, pos in list(placements.items()):
        if pos == boss_position:
            displaced_pid = pid
            occupied.discard(boss_position)
            del placements[pid]
            break

    # Place boss
    placements[boss.piece_id] = boss_position
    occupied.add(boss_position)

    # Relocate displaced piece
    if displaced_pid is not None:
        new_pos = _nearest_free(boss_position[0], boss_position[1], occupied, board_height)
        if new_pos is not None:
            placements[displaced_pid] = new_pos
            occupied.add(new_pos)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def plan_enemy_formation(
    enemies: list["CombatPieceState"],
    enemy_defs_by_id: dict[str, "EnemyDef"],
    *,
    boss_position: tuple[int, int] | None = None,
    board_height: int = BOARD_HEIGHT,
) -> dict[str, tuple[int, int]]:
    """Deterministic role-aware enemy formation planner.

    Args:
        enemies: Combat pieces to place (all is_enemy=True).
        enemy_defs_by_id: Lookup dict mapping enemy definition id to EnemyDef.
            For regular enemies, piece_id matches the EnemyDef.id.
            For bosses, piece_id matches the BossDef.id.
        boss_position: If a boss is present, its authored (col, row) position.
            None means no boss override.
        board_height: Board height (default 7).

    Returns:
        Dict mapping piece_id → (col, row) for each enemy.
    """
    if not enemies:
        return {}

    # 1. Identify boss (tier 10) and classify roles
    boss_piece: "CombatPieceState | None" = None
    buckets: dict[PlacementRole, list["CombatPieceState"]] = {
        role: [] for role in PlacementRole
    }

    # Sort for determinism (same squad = same formation)
    sorted_enemies = sorted(enemies, key=lambda e: e.piece_id)

    for enemy in sorted_enemies:
        # Boss detection: tier 10 pieces
        if enemy.tier == 10:
            boss_piece = enemy
            continue

        enemy_def = enemy_defs_by_id.get(enemy.piece_id)
        if enemy_def is None:
            # Fallback: if no def found, treat as midline
            buckets[PlacementRole.MIDLINE].append(enemy)
            continue

        role = classify_role(enemy_def)
        buckets[role].append(enemy)

    occupied: set[tuple[int, int]] = set()
    placements: dict[str, tuple[int, int]] = {}

    # 2. Place frontline (column 7, center-out)
    _place_band(
        buckets[PlacementRole.FRONTLINE],
        col=COL_FRONT,
        occupied=occupied,
        placements=placements,
        board_height=board_height,
        overflow_cols=(COL_MID,),
    )

    # 3. Place flankers (edge rows of columns 8–9)
    _place_flankers(
        buckets[PlacementRole.FLANK],
        occupied,
        placements,
        board_height,
    )

    # 4. Place midline (column 8, center-out)
    _place_band(
        buckets[PlacementRole.MIDLINE],
        col=COL_MID,
        occupied=occupied,
        placements=placements,
        board_height=board_height,
        overflow_cols=(COL_FRONT, COL_BACK),
    )

    # 5. Place backline (column 9, center-out)
    _place_band(
        buckets[PlacementRole.BACKLINE],
        col=COL_BACK,
        occupied=occupied,
        placements=placements,
        board_height=board_height,
        overflow_cols=(COL_MID,),
    )

    # 6. Place boss at authored position (displaces occupants)
    if boss_piece is not None and boss_position is not None:
        _place_boss(boss_piece, boss_position, occupied, placements, board_height)
    elif boss_piece is not None:
        # Default boss position: center-back
        _place_boss(boss_piece, (COL_BACK, CENTER_ROW), occupied, placements, board_height)

    return placements
