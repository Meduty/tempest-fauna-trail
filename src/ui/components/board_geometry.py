"""Shared hex-board pixel geometry (T.23a).

The combat view (`ui/views/combat.py`) and the Prep view (`ui/views/prep.py`)
both render the 10×7 offset-hex board. They **must** agree on the pixel layout —
a second hand-rolled coordinate system would let the two boards drift. This is
the single source: constants + `cell_xy(q, r)`. Pure Flet-free math (no `flet`
import) so it stays trivially testable and reusable.
"""

from __future__ import annotations

from src.game.combat import BOARD_HEIGHT, BOARD_WIDTH

# Pixel layout of the offset-hex grid (odd columns stagger down half a row).
# ROW_H leaves vertical room under each token for the resource stack the combat
# view draws there — HP bar + up to 2 mana bars (multicasters, B.63) + a status
# pip row — without the stack overlapping the token of the tile below. Prep only
# places tokens on this grid (no bars), so the extra row height is just breathing
# room there.
MARGIN_X = 40
MARGIN_Y = 34
COL_W = 46
ROW_H = 64

# Full board pixel extent — used to size the Canvas / Stack.
BOARD_W = MARGIN_X * 2 + (BOARD_WIDTH - 1) * COL_W
BOARD_H = MARGIN_Y * 2 + (BOARD_HEIGHT - 1) * ROW_H + ROW_H // 2


def cell_xy(q: int, r: int) -> tuple[float, float]:
    """Offset-hex (q, r) → pixel centre. Odd columns stagger down half a row."""
    x = MARGIN_X + q * COL_W
    y = MARGIN_Y + r * ROW_H + (ROW_H // 2 if q % 2 else 0)
    return float(x), float(y)
