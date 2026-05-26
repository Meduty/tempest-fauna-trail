"""Map Effects System (T21) — decoupled arena modifier framework.

Map effects are board-level combat modifiers that alter the hex grid during
combat. Currently used only by boss encounters, but the system is designed
to be reusable by augments, champion passives, or challenge encounters in
the future.

Design principles:
- Decoupled from bosses: MapEffect is a generic interface, boss-specific
  effects are authored as concrete subclasses.
- Auto-battle aware: effects influence pathing/targeting deterministically
  rather than requiring player micro-decisions during combat.
- Visible during planning: players see which effect is active before combat
  begins, allowing strategic team composition choices.
- No Flet imports (V.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from src.game.effects import SourceTag
from src.game.models import WeatherState

if TYPE_CHECKING:
    from src.game.combat.context import CombatContext
    from src.game.piece import Piece


# ---------------------------------------------------------------------------
# Cell Modifier — individual tile state
# ---------------------------------------------------------------------------


@dataclass
class CellModifier:
    """A modifier attached to a specific hex cell on the board.

    Multiple CellModifiers can stack on one cell. The BoardState tracks them.
    """
    cell: tuple[int, int]  # (q, r) axial hex coordinate
    kind: str  # "hazard" | "impassable" | "ley" | "fog" | "rift" | "collapse"
    owner: str  # source id, e.g. "boss:strand" or "map_effect:hazard_tiles"
    tick_damage: float = 0.0  # damage dealt per interval (not per tick)
    damage_interval: int = 60  # ticks between damage applications (60 ticks = 600ms at 10ms/tick)
    stat_buffs: dict[str, float] | None = None  # ley cell stat grants
    spawn_template: str | None = None  # rift spawns this enemy id
    active: bool = True


# ---------------------------------------------------------------------------
# Board State — cell modifier container
# ---------------------------------------------------------------------------


class BoardState:
    """Tracks all active cell modifiers on the combat board."""

    def __init__(self) -> None:
        self._cells: dict[tuple[int, int], list[CellModifier]] = {}

    def modifiers_at(self, q: int, r: int) -> list[CellModifier]:
        """Get all active modifiers at a cell."""
        return [m for m in self._cells.get((q, r), []) if m.active]

    def is_passable(self, q: int, r: int) -> bool:
        """Check if a cell is passable (no impassable/collapse modifiers)."""
        for m in self._cells.get((q, r), []):
            if m.active and m.kind in ("impassable", "collapse"):
                return False
        return True

    def has_kind(self, q: int, r: int, kind: str) -> bool:
        """Check if cell has an active modifier of given kind."""
        return any(m.kind == kind and m.active for m in self._cells.get((q, r), []))

    def add_modifier(self, mod: CellModifier) -> None:
        """Add a modifier to the board."""
        cell = mod.cell
        if cell not in self._cells:
            self._cells[cell] = []
        self._cells[cell].append(mod)

    def remove_modifiers(self, cell: tuple[int, int], kind: str) -> None:
        """Remove all modifiers of a kind from a cell."""
        if cell in self._cells:
            self._cells[cell] = [m for m in self._cells[cell] if m.kind != kind]

    def remove_by_owner(self, owner: str) -> None:
        """Remove all modifiers from a specific owner."""
        for cell in list(self._cells):
            self._cells[cell] = [m for m in self._cells[cell] if m.owner != owner]
            if not self._cells[cell]:
                del self._cells[cell]

    def all_modifiers(self) -> list[CellModifier]:
        """Get all modifiers on the board (active and inactive)."""
        result = []
        for mods in self._cells.values():
            result.extend(mods)
        return result

    def cells_with_kind(self, kind: str) -> list[tuple[int, int]]:
        """Get all cells that have an active modifier of the given kind."""
        result = []
        for cell, mods in self._cells.items():
            if any(m.kind == kind and m.active for m in mods):
                result.append(cell)
        return result


# ---------------------------------------------------------------------------
# MapEffect — abstract base for all arena effects
# ---------------------------------------------------------------------------


class MapEffect:
    """Base class for map effects.

    Subclasses implement on_round and/or on_tick to modify the board.
    Effects are registered on the CombatContext and processed by the tick loop.
    """

    effect_id: str = "base"
    display_name: str = "Map Effect"
    description: str = ""
    affinity: WeatherState = WeatherState.CLEAR

    def setup(self, board: BoardState, rng: Any) -> None:
        """Called once at combat start. Place initial modifiers."""
        pass

    def on_round(self, ctx: "CombatContext", board: BoardState, round_num: int) -> None:
        """Called at round boundaries (every ROUND_TICKS ticks)."""
        pass

    def on_tick(self, ctx: "CombatContext", board: BoardState, tick: int) -> None:
        """Called every tick. Use sparingly — prefer on_round for periodic effects."""
        pass

    def process_occupants(self, ctx: "CombatContext", board: BoardState) -> None:
        """Process effects on pieces occupying modified cells.

        Called each tick after piece movement. Handles hazard damage, ley buffs, etc.
        """
        pass


# ---------------------------------------------------------------------------
# Concrete Map Effects — one per boss affinity
# ---------------------------------------------------------------------------


class SpawnRiftsEffect(MapEffect):
    """Holloway (Clear) — Furnace vents spawn weak adds periodically.

    Auto-battle design: adds appear at fixed positions visible pre-combat.
    Players can plan team composition around handling extra bodies.
    Spawns 1 add every 2 rounds (every 1200 ticks) at a rift cell.
    """
    effect_id = "spawn_rifts"
    display_name = "Furnace Vents"
    description = "Scrap-vents periodically spawn weak reinforcements."
    affinity = WeatherState.CLEAR

    def __init__(self, rift_cells: list[tuple[int, int]] | None = None,
                 spawn_template: str = "enemy_conscript",
                 spawn_interval_rounds: int = 2):
        self._rift_cells = rift_cells or [(2, 1), (7, 1)]
        self._spawn_template = spawn_template
        self._spawn_interval = spawn_interval_rounds

    def setup(self, board: BoardState, rng: Any) -> None:
        for cell in self._rift_cells:
            board.add_modifier(CellModifier(
                cell=cell,
                kind="rift",
                owner="map_effect:spawn_rifts",
                spawn_template=self._spawn_template,
            ))

    def on_round(self, ctx: "CombatContext", board: BoardState, round_num: int) -> None:
        if round_num < 1:
            return
        if round_num % self._spawn_interval != 0:
            return
        # Spawn one add at a random rift cell
        rift_cells = board.cells_with_kind("rift")
        if not rift_cells:
            return
        cell = ctx.rng.choice(rift_cells)
        self._spawn_add(ctx, cell)

    def _spawn_add(self, ctx: "CombatContext", cell: tuple[int, int]) -> None:
        """Spawn a weak add at the given cell."""
        from src.game.encounter import _instantiate_enemy
        from src.game.content import _ENEMY_DEFS

        template = next((d for d in _ENEMY_DEFS if d.id == self._spawn_template), None)
        if template is None:
            return
        enemy = _instantiate_enemy(template, 1)
        from src.game.loadout import piece_from_enemy
        piece = piece_from_enemy(enemy)
        piece.is_enemy = True
        ctx.spawn(piece, cell[0], cell[1])


class FogEffect(MapEffect):
    """Vance (Mist) — pieces beyond range 2 are untargetable.

    Auto-battle design: fog forces close-range engagements. Backline ranged
    pieces must advance to contribute, which the AI handles via reduced
    effective attack range. Players see the fog pre-combat and can build
    melee-heavy teams to exploit the forced close quarters.
    """
    effect_id = "fog"
    display_name = "Sandstorm Fog"
    description = "Pieces beyond range 2 of each other cannot be targeted."
    affinity = WeatherState.MIST

    def __init__(self, max_target_range: int = 2):
        self.max_target_range = max_target_range

    def setup(self, board: BoardState, rng: Any) -> None:
        # Fog is a global effect — mark entire board with fog modifier
        # In practice this is checked by targeting helpers, not per-cell
        board.add_modifier(CellModifier(
            cell=(0, 0),
            kind="fog",
            owner="map_effect:fog",
        ))


class HazardTilesEffect(MapEffect):
    """Strand (Thunder) — capture-grid cells deal damage at intervals.

    Auto-battle design: hazard tiles are visible pre-combat at fixed positions.
    Tiles deal damage every 60 ticks (600ms) to occupants, not per-tick
    (too granular). Tiles shift positions every round, creating a dynamic
    battlefield that affects pathing — AI pieces prefer non-hazard paths.
    """
    effect_id = "hazard_tiles"
    display_name = "Capture Grid"
    description = "Electrified tiles deal periodic damage to occupants."
    affinity = WeatherState.THUNDER

    def __init__(self, num_tiles: int = 4, damage_per_interval: float = 15.0,
                 damage_interval: int = 60):
        self._num_tiles = num_tiles
        self._damage = damage_per_interval
        self._interval = damage_interval

    def setup(self, board: BoardState, rng: Any) -> None:
        self._place_hazards(board, rng)

    def _place_hazards(self, board: BoardState, rng: Any) -> None:
        """Place hazard tiles at random positions in the middle of the board."""
        from src.game.combat.context import BOARD_WIDTH, BOARD_HEIGHT
        candidates = [
            (q, r) for q in range(1, BOARD_WIDTH - 1)
            for r in range(1, BOARD_HEIGHT - 1)
        ]
        chosen = rng.sample(candidates, min(self._num_tiles, len(candidates)))
        for cell in chosen:
            board.add_modifier(CellModifier(
                cell=cell,
                kind="hazard",
                owner="map_effect:hazard_tiles",
                tick_damage=self._damage,
                damage_interval=self._interval,
            ))

    def on_round(self, ctx: "CombatContext", board: BoardState, round_num: int) -> None:
        """Shift hazard tiles to new positions each round."""
        if round_num < 1:
            return
        # Remove old hazards
        board.remove_by_owner("map_effect:hazard_tiles")
        # Place new ones
        self._place_hazards(board, ctx.rng)

    def process_occupants(self, ctx: "CombatContext", board: BoardState) -> None:
        """Deal damage to pieces on hazard tiles at intervals."""
        tick = ctx.current_tick
        if tick % self._interval != 0:
            return
        hazard_cells = board.cells_with_kind("hazard")
        for piece in ctx.living_pieces():
            if (piece.position_q, piece.position_r) in hazard_cells:
                ctx.deal_damage(piece, piece, self._damage, SourceTag.TRUE)


class LeyCellsEffect(MapEffect):
    """Vossberg (Cloudy) — contested tiles grant stat buffs.

    Auto-battle design: ley cells are visible pre-combat at fixed positions
    in the center of the board. Pieces standing on ley cells gain stat buffs.
    This influences the AI's pathing/targeting preferences and rewards
    positional control. Players can build tanky teams that hold ground.
    """
    effect_id = "ley_cells"
    display_name = "Scorched Thermals"
    description = "Ley cells grant stat buffs to occupying pieces."
    affinity = WeatherState.CLOUDY

    def __init__(self, num_cells: int = 3,
                 buff_stats: dict[str, float] | None = None):
        self._num_cells = num_cells
        self._buff_stats = buff_stats or {"strength": 20.0, "intelligence": 20.0}

    def setup(self, board: BoardState, rng: Any) -> None:
        from src.game.combat.context import BOARD_WIDTH, BOARD_HEIGHT
        # Place ley cells in the center of the board
        center_q = BOARD_WIDTH // 2
        center_r = BOARD_HEIGHT // 2
        candidates = [
            (center_q + dq, center_r + dr)
            for dq in range(-2, 3) for dr in range(-1, 2)
            if 0 <= center_q + dq < BOARD_WIDTH and 0 <= center_r + dr < BOARD_HEIGHT
        ]
        chosen = rng.sample(candidates, min(self._num_cells, len(candidates)))
        for cell in chosen:
            board.add_modifier(CellModifier(
                cell=cell,
                kind="ley",
                owner="map_effect:ley_cells",
                stat_buffs=dict(self._buff_stats),
            ))

    def process_occupants(self, ctx: "CombatContext", board: BoardState) -> None:
        """Grant buffs to pieces on ley cells.

        Note: buffs are applied as TIMED modifiers that expire next tick,
        effectively making them conditional on occupancy.
        """
        from src.game.effects import Modifier, Lifetime
        ley_cells = board.cells_with_kind("ley")
        for piece in ctx.living_pieces():
            if (piece.position_q, piece.position_r) in ley_cells:
                mods = board.modifiers_at(piece.position_q, piece.position_r)
                for m in mods:
                    if m.kind == "ley" and m.stat_buffs:
                        for stat, value in m.stat_buffs.items():
                            ctx.apply_modifier(piece, Modifier(
                                stat=stat,
                                op="add",
                                value=value,
                                lifetime=Lifetime.TIMED,
                                source_id="map_effect:ley_cells",
                                expires_at_tick=ctx.current_tick + 2,
                            ))


class FloodLanesEffect(MapEffect):
    """Crège (Rain) — one board column floods impassable, shifts per round.

    Auto-battle design: the flooded column is visible and shifts predictably
    (left to right). This forces the AI to repath around obstacles, splitting
    teams and creating tactical situations. Players can anticipate which
    lanes will be cut off.
    """
    effect_id = "flood_lanes"
    display_name = "Dredge-Wake"
    description = "A flooded column blocks movement, shifting each round."
    affinity = WeatherState.RAIN

    def __init__(self, start_column: int | None = None):
        self._start_column = start_column

    def setup(self, board: BoardState, rng: Any) -> None:
        from src.game.combat.context import BOARD_WIDTH
        if self._start_column is None:
            self._current_col = rng.randint(1, BOARD_WIDTH - 2)
        else:
            self._current_col = self._start_column
        self._apply_flood(board)

    def _apply_flood(self, board: BoardState) -> None:
        from src.game.combat.context import BOARD_HEIGHT
        board.remove_by_owner("map_effect:flood_lanes")
        for r in range(BOARD_HEIGHT):
            board.add_modifier(CellModifier(
                cell=(self._current_col, r),
                kind="impassable",
                owner="map_effect:flood_lanes",
            ))

    def on_round(self, ctx: "CombatContext", board: BoardState, round_num: int) -> None:
        """Shift flood column one position to the right (wrapping)."""
        if round_num < 1:
            return
        from src.game.combat.context import BOARD_WIDTH
        self._current_col = (self._current_col + 1) % BOARD_WIDTH
        # Avoid edges (col 0 and col BOARD_WIDTH-1)
        if self._current_col == 0:
            self._current_col = 1
        if self._current_col >= BOARD_WIDTH - 1:
            self._current_col = BOARD_WIDTH - 2
        self._apply_flood(board)


class CollapsingArenaEffect(MapEffect):
    """Iron Emperor (Snow) — edge rows disable over the fight.

    Auto-battle design: the arena shrinks predictably from the edges inward.
    This creates a sudden-death-at-timeout effect naturally (only activates
    when the fight runs long). Players see the shrinking boundary and can
    build burst teams to end fights before the arena becomes too small.
    Collapse accelerates in boss phase 2 (via on_phase_change integration).
    """
    effect_id = "collapsing_arena"
    display_name = "World-Engine Freeze"
    description = "The arena freezes from the edges inward over time."
    affinity = WeatherState.SNOW

    def __init__(self, collapse_interval_rounds: int = 2):
        self._interval = collapse_interval_rounds
        self._collapse_layer = 0
        self._accelerated = False

    def setup(self, board: BoardState, rng: Any) -> None:
        # No initial modifiers — arena starts open
        pass

    def on_round(self, ctx: "CombatContext", board: BoardState, round_num: int) -> None:
        """Collapse one layer of edge cells."""
        if round_num < 1:
            return
        interval = 1 if self._accelerated else self._interval
        if round_num % interval != 0:
            return
        self._collapse_layer += 1
        self._apply_collapse(board)

    def _apply_collapse(self, board: BoardState) -> None:
        """Mark edge rows/columns as impassable up to current collapse layer."""
        from src.game.combat.context import BOARD_WIDTH, BOARD_HEIGHT
        board.remove_by_owner("map_effect:collapsing_arena")
        layer = self._collapse_layer
        for q in range(BOARD_WIDTH):
            for r in range(BOARD_HEIGHT):
                if (q < layer or q >= BOARD_WIDTH - layer or
                        r < layer or r >= BOARD_HEIGHT - layer):
                    board.add_modifier(CellModifier(
                        cell=(q, r),
                        kind="collapse",
                        owner="map_effect:collapsing_arena",
                    ))

    def accelerate(self) -> None:
        """Called when boss enters phase 2 — doubles collapse speed."""
        self._accelerated = True


# ---------------------------------------------------------------------------
# Effect Registry — lookup by effect_id
# ---------------------------------------------------------------------------

MAP_EFFECT_REGISTRY: dict[str, type[MapEffect]] = {
    "spawn_rifts": SpawnRiftsEffect,
    "fog": FogEffect,
    "hazard_tiles": HazardTilesEffect,
    "ley_cells": LeyCellsEffect,
    "flood_lanes": FloodLanesEffect,
    "collapsing_arena": CollapsingArenaEffect,
}
