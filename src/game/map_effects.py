"""Map effect system (T21) — auto-battle-aware boss arena effects.

Each boss fight has one authored MapEffect that modifies the hex board
during combat. Effects are decoupled from bosses: only boss fights use
them in MVP, but the system is open for augments/passives later.

Design principles (see t21_challenge_boss_plan.md §4.2):
- All effects are meaningful from the *prep-phase* positioning decision,
  not real-time control (players don't control pieces during combat).
- Effects are visible during planning so players can make informed choices.
- Effects influence pathing/targeting/behaviour deterministically.

Architecture:
- BoardState (board.py) is the pure data layer.
- MapEffect subclasses subscribe to the event bus at combat start.
- CombatContext carries a BoardState; map effects write/read it via ctx.board_state.
- No imports from combat/ — ctx received as duck-typed parameter from event bus.

No Flet imports (V.1). No I/O. All randomness via ctx.rng (V.2 determinism).
"""

from __future__ import annotations

from random import Random
from typing import Any

from src.game.board import BoardState, CellModifier
from src.game.effects import (
    EventBus,
    Hook,
    Lifetime,
    Modifier,
    SourceTag,
)

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

ROUND_TICKS = 600        # 1 round = 600 ticks (matches loop.py)
SUNLIT_HPS = 60          # heal interval for sunlit tiles
SUNLIT_HEAL = 25.0       # HP healed per interval
SUNLIT_DMG_BUFF = 0.10   # +10% damage while on sunlit tile
HAZARD_INTERVAL = 60     # hazard damage fires every 60 ticks
HAZARD_DAMAGE = 30.0     # true damage per interval on hazard tile
LEY_ARMOR_BONUS = 20.0   # armor added to ley-holding team
LEY_REGEN_BONUS = 15.0   # HP regen bonus (per interval) on ley tiles — future use
SLOW_MAGNITUDE = 0.5     # move speed multiplier — placeholder for T24 movement system
                         # The 'slow' status is cosmetic until move_speed is consumed by pathing.
FOG_RANGE = 2            # max targetable distance in fog (hexes)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class MapEffect:
    """Base class for all map effects.

    Subclasses override on_combat_start, on_tick, on_round.
    Call register(bus) to wire into the event bus.
    """

    effect_id: str = "base"

    def __init__(self, board: BoardState, rng: Random) -> None:
        self.board = board
        self._rng = rng

    def register(self, bus: EventBus) -> None:
        """Subscribe hooks to the event bus."""
        bus.subscribe(Hook("on_combat_start", self._on_combat_start, priority=-10))
        bus.subscribe(Hook("on_tick", self._on_tick, priority=-10))

    def _on_combat_start(self, ctx: Any, event: Any) -> None:
        """Called once at combat start. Place initial board state here."""

    def _on_tick(self, ctx: Any, event: Any) -> None:
        """Called every tick. Process per-tick effects and round boundaries."""
        tick: int = event.tick
        if tick % ROUND_TICKS == 0:
            round_num = tick // ROUND_TICKS
            self._on_round(ctx, round_num)

    def _on_round(self, ctx: Any, round_num: int) -> None:
        """Called at the start of each complete round (every 600 ticks)."""


# ---------------------------------------------------------------------------
# 1. Sunlit Tiles (Holloway / Clear)
# ---------------------------------------------------------------------------


class SunlitTilesEffect(MapEffect):
    """Holloway's arena — direct sunlight bathes designated cells.

    A piece standing on a sunlit tile receives:
    - Heal-over-time (every SUNLIT_HPS ticks)
    - Flat damage buff (as a TIMED Modifier refreshed every 2 ticks)

    Both teams can benefit. Control decided by Prep placement.
    Buff drops immediately on vacating (TIMED modifier expires in 2 ticks).
    """

    effect_id = "sunlit_tiles"
    TILE_COUNT = 3

    def _on_combat_start(self, ctx: Any, event: Any) -> None:
        board = self.board
        width = getattr(ctx, "_board_width", 10)
        height = getattr(ctx, "_board_height", 7)

        # Place tiles in the centre rows, spread across the board
        candidates = [
            (q, r)
            for q in range(1, width - 1)
            for r in range(1, height - 1)
        ]
        self._rng.shuffle(candidates)
        chosen = candidates[: self.TILE_COUNT]

        for cell in chosen:
            mod = CellModifier(
                cell=cell,
                kind="sunlit",
                owner="boss:holloway",
                heal_per_interval=SUNLIT_HEAL,
                heal_interval=SUNLIT_HPS,
                damage_buff_pct=SUNLIT_DMG_BUFF,
            )
            board.add_modifier(mod)
            board.sunlit_cells.append(cell)

    def _on_tick(self, ctx: Any, event: Any) -> None:
        tick: int = event.tick
        board = self.board

        for piece in list(ctx.living_pieces()):
            pos = (piece.position_q, piece.position_r)
            for mod in board.modifiers_at(*pos):
                if mod.kind != "sunlit":
                    continue

                # Heal on interval
                if tick % mod.heal_interval == 0:
                    ctx.heal(piece, piece, mod.heal_per_interval)

                # Damage buff: short-lived TIMED Modifier refreshed each tick.
                # Buffs STR (physical damage proxy). Stage 1 / Clear is the
                # tutorial boss — physical-only is intentional simplicity.
                # Ability damage (INT) is unaffected; a future pass could add
                # a paired INT modifier for full-damage coverage.
                # Expires 2 ticks after the piece vacates the tile.
                if mod.damage_buff_pct > 0:
                    buff = Modifier(
                        stat="strength",        # physical damage proxy (see note above)
                        op="mul",
                        value=1.0 + mod.damage_buff_pct,
                        lifetime=Lifetime.TIMED,
                        source_id="map:sunlit",
                        expires_at_tick=tick + 2,
                    )
                    # Only apply if not already buffed (avoid stacking)
                    if not any(
                        m.source_id == "map:sunlit"
                        for m in piece.modifiers
                        if m.lifetime == Lifetime.TIMED
                    ):
                        ctx.apply_modifier(piece, buff)

        # Round boundary — not needed for this effect
        if tick % ROUND_TICKS == 0:
            pass


# ---------------------------------------------------------------------------
# 2. Fog (Vance / Mist)
# ---------------------------------------------------------------------------


class FogEffect(MapEffect):
    """Vance's arena — a permanent dust-storm limits targeting range.

    Pieces beyond FOG_RANGE hexes of each other are untargetable.
    Forces all pieces to close distance; ranged pieces effectively become
    melee-range. Prep decision: front-load ranged pieces vs. go melee.

    Targeting helpers read ctx.board_state.fog_range.
    """

    effect_id = "fog"

    def _on_combat_start(self, ctx: Any, _event: Any) -> None:
        self.board.fog_range = FOG_RANGE


# ---------------------------------------------------------------------------
# 3. Hazard Tiles (Strand / Thunder)
# ---------------------------------------------------------------------------


class HazardTilesEffect(MapEffect):
    """Strand's arena — live capture-grid cells deal interval true damage.

    4–6 designated cells deal HAZARD_DAMAGE every HAZARD_INTERVAL ticks.
    Tiles shift every round so the safe zones move.
    Initial positions visible in Prep.
    """

    effect_id = "hazard_tiles"
    TILE_COUNT_MIN = 4
    TILE_COUNT_MAX = 6

    def _on_combat_start(self, ctx: Any, event: Any) -> None:
        count = self._rng.randint(self.TILE_COUNT_MIN, self.TILE_COUNT_MAX)
        self._place_hazards(ctx, count)

    def _place_hazards(self, ctx: Any, count: int) -> None:
        board = self.board
        width = getattr(ctx, "_board_width", 10)
        height = getattr(ctx, "_board_height", 7)

        board.clear_modifiers("hazard")
        board.hazard_cells.clear()

        candidates = [
            (q, r)
            for q in range(width)
            for r in range(height)
        ]
        self._rng.shuffle(candidates)

        for cell in candidates[:count]:
            mod = CellModifier(
                cell=cell,
                kind="hazard",
                owner="boss:strand",
                damage_interval=HAZARD_INTERVAL,
                damage_amount=HAZARD_DAMAGE,
            )
            board.add_modifier(mod)
            board.hazard_cells.append(cell)

    def _on_tick(self, ctx: Any, event: Any) -> None:
        tick: int = event.tick
        board = self.board

        for piece in list(ctx.living_pieces()):
            pos = (piece.position_q, piece.position_r)
            for mod in board.modifiers_at(*pos):
                if mod.kind != "hazard":
                    continue
                if tick % mod.damage_interval == 0:
                    ctx.deal_damage(None, piece, mod.damage_amount, SourceTag.TRUE)

        if tick % ROUND_TICKS == 0:
            round_num = tick // ROUND_TICKS
            self._on_round(ctx, round_num)

    def _on_round(self, ctx: Any, round_num: int) -> None:
        """Shift hazard tiles each round."""
        count = len(self.board.hazard_cells)
        if count == 0:
            count = self.TILE_COUNT_MIN
        self._place_hazards(ctx, count)


# ---------------------------------------------------------------------------
# 4. Defensive Ley Cells (Vossberg / Cloudy)
# ---------------------------------------------------------------------------


class DefensiveLeyEffect(MapEffect):
    """Vossberg's arena — contested scorched-ground cells buff the holding team.

    2–3 ley cells on the board. A cell is held by whichever team has a
    piece standing on it; ownership transfers by stepping onto it.

    Holding team receives a team-wide defensive buff:
    - +LEY_ARMOR_BONUS armor

    Buff applies as long as the cell is held; drops immediately on vacating.
    Prep placement determines early control.
    """

    effect_id = "defensive_ley"
    CELL_COUNT = 3

    def _on_combat_start(self, ctx: Any, event: Any) -> None:
        board = self.board
        width = getattr(ctx, "_board_width", 10)
        height = getattr(ctx, "_board_height", 7)

        # Place ley cells spread across the mid-board
        candidates = [
            (q, r)
            for q in range(2, width - 2)
            for r in range(1, height - 1)
        ]
        self._rng.shuffle(candidates)

        for cell in candidates[: self.CELL_COUNT]:
            mod = CellModifier(
                cell=cell,
                kind="ley",
                owner="boss:vossberg",
                holding_team=None,
            )
            board.add_modifier(mod)
            board.ley_cells.append(cell)

        # Track applied ley buffs: map from team ("player"/"enemy") → hook_id
        self._ley_buffs: dict[str, list[str]] = {"player": [], "enemy": []}

    def _on_tick(self, ctx: Any, event: Any) -> None:
        board = self.board

        for pos in board.ley_cells:
            mods = board.modifiers_at(*pos)
            ley_mod = next((m for m in mods if m.kind == "ley"), None)
            if ley_mod is None:
                continue

            # Determine which team (if any) occupies this cell
            occupying_team: str | None = None
            for piece in ctx.living_pieces():
                if piece.position_q == pos[0] and piece.position_r == pos[1]:
                    occupying_team = "enemy" if piece.is_enemy else "player"
                    break  # First occupant wins

            if occupying_team != ley_mod.holding_team:
                # Ownership changed — remove old buff, apply new.
                # Each cell uses a unique source_id so cells are independent:
                # losing cell A does not strip cell B's buff from the same team.
                self._remove_ley_buff(ctx, ley_mod.holding_team, pos)
                ley_mod.holding_team = occupying_team
                if occupying_team is not None:
                    self._apply_ley_buff(ctx, occupying_team, pos)

    @staticmethod
    def _cell_source(pos: tuple[int, int]) -> str:
        """Per-cell source id so each cell's buff is tracked independently."""
        return f"map:ley:{pos[0]},{pos[1]}"

    def _apply_ley_buff(self, ctx: Any, team: str, pos: tuple[int, int]) -> None:
        """Apply defensive armor buff to all living members of team for this cell.

        Uses a per-cell source_id so multiple held cells stack additively
        (design intent) while re-application of the same cell is deduped
        (prevents double-stacking on ownership swings).
        """
        is_enemy_team = (team == "enemy")
        source = self._cell_source(pos)
        for piece in ctx.living_pieces():
            if piece.is_enemy != is_enemy_team:
                continue
            # Dedup: only apply if this cell's buff is not already present
            if not any(m.source_id == source for m in piece.modifiers):
                buff = Modifier(
                    stat="armor",
                    op="add",
                    value=LEY_ARMOR_BONUS,
                    lifetime=Lifetime.COMBAT,
                    source_id=source,
                )
                ctx.apply_modifier(piece, buff)

    def _remove_ley_buff(self, ctx: Any, team: str | None, pos: tuple[int, int]) -> None:
        """Remove this cell's ley armor buff from all living members of team.

        Only removes the modifier for this specific cell (by source_id),
        leaving buffs from other held ley cells intact.
        """
        if team is None:
            return
        is_enemy_team = (team == "enemy")
        source = self._cell_source(pos)
        for piece in ctx.living_pieces():
            if piece.is_enemy == is_enemy_team:
                piece.modifiers = [
                    m for m in piece.modifiers
                    if m.source_id != source
                ]


# ---------------------------------------------------------------------------
# 5. Flood Lanes (Crège / Rain)
# ---------------------------------------------------------------------------


class FloodLanesEffect(MapEffect):
    """Crège's arena — one board column floods and becomes impassable.

    The flood column shifts one position each round, constantly reshaping
    lanes. Pieces path around the flood; formation decisions matter.
    """

    effect_id = "flood_lanes"

    def _on_combat_start(self, ctx: Any, event: Any) -> None:
        width = getattr(ctx, "_board_width", 10)
        # Start flood in one of the middle columns
        mid = width // 2
        self._flood_q = mid
        self._width = width
        self._direction = 1  # Shift right initially
        self.board.impassable_columns.add(self._flood_q)

    def _on_round(self, ctx: Any, round_num: int) -> None:
        """Shift the flood column each round.

        The flood travels columns 1..(width-2) — inner columns only.
        Edge columns (0 and width-1) are permanently passable so pieces
        always have at least one clear lane on each flank.
        """
        self.board.impassable_columns.discard(self._flood_q)

        # Bounce before reaching the outermost columns (keep edges open)
        next_q = self._flood_q + self._direction
        if next_q <= 0 or next_q >= self._width - 1:
            self._direction *= -1
            next_q = self._flood_q + self._direction

        self._flood_q = next_q
        self.board.impassable_columns.add(self._flood_q)


# ---------------------------------------------------------------------------
# 6. Slow Tiles (Iron Emperor / Snow)
# ---------------------------------------------------------------------------


class SlowTilesEffect(MapEffect):
    """Iron Emperor's arena — frozen tiles spread inward from the edges.

    The arena does not shrink; instead, edge cells become coated in ice
    that slows movement. The slow zone expands each round, compressing the
    effective fast zone. In Phase 2 (The Wound Spreads), expansion accelerates.

    Slow tiles apply the 'slow' status to occupants each tick.
    """

    effect_id = "slow_tiles"

    def __init__(self, board: BoardState, rng: Random) -> None:
        super().__init__(board, rng)
        self._phase2 = False
        self._slow_depth = 0   # How many rows in from each edge are frozen

    def _on_combat_start(self, ctx: Any, event: Any) -> None:
        self._width = getattr(ctx, "_board_width", 10)
        self._height = getattr(ctx, "_board_height", 7)
        # Register phase-2 detection hook
        ctx.bus.subscribe(Hook(
            "on_phase_change",
            self._on_phase_change,
            priority=0,
        ))

    def _on_phase_change(self, ctx: Any, event: Any) -> None:
        """Detect when Iron Emperor enters phase 2."""
        if getattr(event, "new_phase", 0) == 2:
            self._phase2 = True

    def _on_tick(self, ctx: Any, event: Any) -> None:
        tick: int = event.tick
        board = self.board

        # Apply 'slow' status to any piece standing on a slow cell
        for piece in list(ctx.living_pieces()):
            pos = (piece.position_q, piece.position_r)
            if board.is_slow(*pos):
                ctx.apply_status(piece, "slow", duration_ticks=3)

        # Round boundary
        if tick % ROUND_TICKS == 0:
            round_num = tick // ROUND_TICKS
            self._on_round(ctx, round_num)

    def _on_round(self, ctx: Any, round_num: int) -> None:
        """Expand slow tiles inward from edges each round.

        Phase 1: expands every even round (first expansion at round 2, ~20 s).
                 This delay gives players a few rounds before the freeze matters.
        Phase 2: expands every round (The Wound Spreads passive doubles the rate).

        NOTE: slow status currently has no mechanical gate (move_speed is not yet
        consumed by pathing). The slow tiles are visually telegraphed and will
        become mechanical when T24 (enemy formation / movement) is implemented.
        SLOW_MAGNITUDE (0.5) is the intended multiplier for that system.
        """
        # Phase 2 expands faster (every round instead of every 2 rounds)
        if self._phase2 or round_num % 2 == 0:
            self._slow_depth += 1
            self._rebuild_slow_cells()

    def _rebuild_slow_cells(self) -> None:
        """Recompute which cells are slow based on current depth."""
        board = self.board
        board.slow_cells.clear()

        depth = self._slow_depth
        for q in range(self._width):
            for r in range(self._height):
                # Edges: top rows, bottom rows, left columns, right columns
                is_edge = (
                    r < depth or
                    r >= self._height - depth or
                    q < depth or
                    q >= self._width - depth
                )
                if is_edge:
                    board.slow_cells.add((q, r))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

MAP_EFFECT_CLASSES: dict[str, type[MapEffect]] = {
    "sunlit_tiles": SunlitTilesEffect,
    "fog": FogEffect,
    "hazard_tiles": HazardTilesEffect,
    "defensive_ley": DefensiveLeyEffect,
    "flood_lanes": FloodLanesEffect,
    "slow_tiles": SlowTilesEffect,
}


def build_map_effect(effect_id: str, board: BoardState, seed: int) -> MapEffect:
    """Instantiate a MapEffect by id with a seeded RNG."""
    cls = MAP_EFFECT_CLASSES.get(effect_id)
    if cls is None:
        raise ValueError(f"Unknown map effect id: {effect_id!r}")
    rng = Random(seed)
    return cls(board, rng)
