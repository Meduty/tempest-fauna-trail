"""Board state — cell modifier data layer (T21).

BoardState tracks spatial modifiers applied to hex-grid cells during combat.
This is a pure data layer — no game-specific logic lives here.

Used by:
  - combat/context.py  (carries a BoardState instance on CombatContext)
  - map_effects.py     (writes cell modifiers)
  - targeting.py       (reads fog_range)
  - combat/engine.py   (reads slow_cells for status application)

No Flet imports (V.1). No I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# CellModifier
# ---------------------------------------------------------------------------


@dataclass
class CellModifier:
    """A modifier applied to a specific hex cell.

    Each boss map effect creates one or more CellModifiers to track the
    state of its affected cells.
    """

    cell: tuple[int, int]           # (q, r) axial hex coordinate
    kind: str                        # "sunlit" | "hazard" | "ley" | "slow"
                                     # (flood lanes use BoardState.impassable_columns, not CellModifier)
    owner: str                       # source id, e.g. "boss:holloway"
    active: bool = True

    # Sunlit-tile fields
    heal_per_interval: float = 0.0   # HP healed every heal_interval ticks
    heal_interval: int = 60          # how often heal fires (ticks)
    damage_buff_pct: float = 0.0     # fractional damage multiplier (e.g. 0.10 = +10%)

    # Hazard-tile fields
    damage_interval: int = 60        # how often damage fires (ticks)
    damage_amount: float = 0.0       # true damage dealt per interval

    # Ley-cell fields
    holding_team: str | None = None  # "player" | "enemy" | None (uncontested)


# ---------------------------------------------------------------------------
# BoardState
# ---------------------------------------------------------------------------


class BoardState:
    """Live board-cell modifier state during combat.

    Mutated by map effects; read by combat systems.
    All coordinate keys use axial (q, r) hex notation.
    """

    def __init__(self) -> None:
        # Mapping from cell → list of active CellModifiers
        self.cell_modifiers: dict[tuple[int, int], list[CellModifier]] = {}

        # Set of column indices (q) that are currently impassable (flood lanes)
        self.impassable_columns: set[int] = set()

        # Fog range limit: None = no fog; int = max targetable hex distance
        self.fog_range: int | None = None

        # Set of cells that apply a slow status to occupants
        self.slow_cells: set[tuple[int, int]] = set()

        # Positions of ley cells (for UI rendering and ownership checks)
        self.ley_cells: list[tuple[int, int]] = []

        # Positions of sunlit tiles (for UI rendering)
        self.sunlit_cells: list[tuple[int, int]] = []

        # Positions of hazard tiles (for UI rendering)
        self.hazard_cells: list[tuple[int, int]] = []

    # --- Writers ---

    def add_modifier(self, mod: CellModifier) -> None:
        """Add a CellModifier to its cell's list."""
        key = mod.cell
        if key not in self.cell_modifiers:
            self.cell_modifiers[key] = []
        self.cell_modifiers[key].append(mod)

    def remove_modifiers(self, cell: tuple[int, int], kind: str) -> None:
        """Remove all modifiers of the given kind from a cell."""
        mods = self.cell_modifiers.get(cell)
        if mods:
            self.cell_modifiers[cell] = [m for m in mods if m.kind != kind]
            if not self.cell_modifiers[cell]:
                del self.cell_modifiers[cell]

    def clear_modifiers(self, kind: str) -> None:
        """Remove all modifiers of the given kind across the whole board."""
        for cell in list(self.cell_modifiers):
            self.remove_modifiers(cell, kind)

    # --- Readers ---

    def modifiers_at(self, q: int, r: int) -> list[CellModifier]:
        """Return all active CellModifiers at the given cell."""
        return [m for m in self.cell_modifiers.get((q, r), []) if m.active]

    def is_passable(self, q: int, r: int) -> bool:
        """Return True if a piece can occupy or move through this cell."""
        return q not in self.impassable_columns

    def is_slow(self, q: int, r: int) -> bool:
        """Return True if this cell applies a slow to occupants."""
        return (q, r) in self.slow_cells

    def is_in_fog_range(self, q1: int, r1: int, q2: int, r2: int) -> bool:
        """Return True if piece at (q2, r2) is targetable from (q1, r1) under fog.

        If fog_range is None, all pieces are targetable.
        """
        if self.fog_range is None:
            return True
        # Axial hex distance
        dist = (abs(q1 - q2) + abs(r1 - r2) + abs(q1 + r1 - q2 - r2)) // 2
        return dist <= self.fog_range
