"""Combat tick loop (T20).

run() is the new entry point — takes a compiled loadout and runs the combat.
resolve_combat() in the old combat.py delegates to this when abilities are present.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from src.game.combat.context import CombatContext, hex_distance, HEX_DIRECTIONS, BOARD_WIDTH, BOARD_HEIGHT
from src.game.effects import EventBus, Lifetime, SourceTag
from src.game.events import CombatStartEvent, TickEvent
from src.game.piece import Piece, ActiveSlot
from src.game.status import STATUS_DEFS, StatusGate, StatusInstance


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TICK_MS = 10
ROUND_TICKS = 600
ENERGY_THRESHOLD = 60_000
MAX_TICKS = 12_000

# Sudden death: kicks in at MAX_TICKS, escalating DOT per tick
SUDDEN_DEATH_TICK_START = MAX_TICKS
# Hard cap — sudden-death DOT will resolve combat well before this
HARD_CAP_TICKS = MAX_TICKS + 2_000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _on_board(q: int, r: int) -> bool:
    return 0 <= q < BOARD_WIDTH and 0 <= r < BOARD_HEIGHT


def _both_sides_alive(pieces: list[Piece]) -> bool:
    team = any(p.alive and not p.is_enemy for p in pieces)
    enemy = any(p.alive and p.is_enemy for p in pieces)
    return team and enemy


def _effective_stat(piece: Piece, stat: str) -> float:
    """Get effective stat for meter advancement."""
    return piece.stat(stat)


# ---------------------------------------------------------------------------
# Status processing
# ---------------------------------------------------------------------------


def process_statuses(ctx: CombatContext, pieces: list[Piece]) -> None:
    """Process status effects each tick: expire, DOT, decay."""
    for piece in pieces:
        if not piece.alive:
            continue
        expired = []
        for i, status in enumerate(piece.statuses):
            status.remaining_ticks -= 1
            if status.remaining_ticks <= 0:
                expired.append(i)
                continue
            # DOT processing
            status_def = STATUS_DEFS.get(status.status_id)
            if status_def and status_def.dot_per_tick > 0:
                dot_amount = status_def.dot_per_tick
                if status_def.dot_scales_with_stacks:
                    dot_amount *= status.stacks
                attacker = piece
                if status.source_id:
                    for p in ctx.all_pieces():
                        if p.id == status.source_id and p.alive:
                            attacker = p
                            break
                if status_def.dot_true_damage:
                    ctx.deal_damage(attacker, piece, dot_amount, SourceTag.TRUE)
                else:
                    ctx.deal_damage(attacker, piece, dot_amount, SourceTag.DOT, damage_type="magical")
                # Decay stacks after DOT (e.g. POISON loses one stack per tick)
                if status_def.decay_stacks_per_tick and status.stacks > 0:
                    status.stacks -= 1
                    if status.stacks == 0:
                        expired.append(i)

        # Remove expired statuses (in reverse order to maintain indices)
        for i in reversed(expired):
            status_inst = piece.statuses[i]
            piece.statuses.pop(i)
            from src.game.events import StatusEvent
            event = StatusEvent(target=piece, status_id=status_inst.status_id)
            ctx.bus.fire("on_status_expired", event, ctx=ctx)


# ---------------------------------------------------------------------------
# Modifier expiry
# ---------------------------------------------------------------------------


def expire_modifiers(ctx: CombatContext, pieces: list[Piece]) -> None:
    """Remove TIMED modifiers that have expired."""
    tick = ctx.current_tick
    for piece in pieces:
        piece.modifiers = [
            m for m in piece.modifiers
            if not (m.lifetime == Lifetime.TIMED and m.expires_at_tick is not None and tick >= m.expires_at_tick)
        ]


# ---------------------------------------------------------------------------
# Cast resolution
# ---------------------------------------------------------------------------


def process_casts(ctx: CombatContext, piece: Piece) -> None:
    """Check if any ability slots are ready to cast. Multi-slot support."""
    from src.game.registries import ABILITY_REGISTRY

    if piece.is_gated(StatusGate.BLOCKS_CAST):
        return
    if not piece.alive:
        return

    # Iterate slots by descending priority
    sorted_indices = sorted(
        range(len(piece.actives)),
        key=lambda i: -piece.actives[i].priority,
    )
    for slot_idx in sorted_indices:
        slot = piece.actives[slot_idx]
        if slot.current_mana < slot.cost:
            continue
        # Skip unregistered abilities without spending mana
        if slot.ability_id not in ABILITY_REGISTRY:
            continue
        # Spend mana and cast
        slot.current_mana = 0.0
        ctx.cast_ability(piece, slot_idx=slot_idx)
        # If piece got silenced or killed by the cast/hooks, stop
        if piece.is_gated(StatusGate.BLOCKS_CAST) or not piece.alive:
            return


# ---------------------------------------------------------------------------
# Board-state processing (map effects output)
# ---------------------------------------------------------------------------


def _process_board_state(ctx: CombatContext, pieces: list[Piece]) -> None:
    """Apply board-state effects to living pieces each tick.

    Map effects write to ctx.board_state; this function reads it and applies
    mechanical consequences (slow status from slow_cells etc.).
    The map effects themselves subscribe to on_tick hooks — this function
    handles the combat-engine side (status application from board state).
    """
    board = ctx.board_state
    if not board.slow_cells:
        return
    for piece in pieces:
        if not piece.alive:
            continue
        pos = (piece.position_q, piece.position_r)
        if board.is_slow(*pos):
            # Short duration; re-applied each tick while piece stays on slow tile
            ctx.apply_status(piece, "slow", duration_ticks=3)


# ---------------------------------------------------------------------------
# Main tick loop
# ---------------------------------------------------------------------------


def run(ctx: CombatContext) -> str:
    """Run the combat loop. Returns winner: 'team', 'enemy', or 'draw'."""
    pieces = ctx.all_pieces()

    # Fire on_combat_start
    ctx.bus.fire("on_combat_start", CombatStartEvent(), ctx=ctx)

    if not _both_sides_alive(pieces):
        # Immediate resolution
        team_alive = any(p.alive and not p.is_enemy for p in pieces)
        return "team" if team_alive else "enemy"

    for tick in range(1, HARD_CAP_TICKS + 1):
        ctx.current_tick = tick

        if ctx.combat_ended:
            break

        # Fire on_tick
        ctx.bus.fire("on_tick", TickEvent(tick=tick), ctx=ctx)

        # Sudden death: apply escalating DOT to all living pieces once MAX_TICKS is passed
        if tick >= SUDDEN_DEATH_TICK_START:
            for piece in pieces:
                if piece.alive:
                    # Short duration ensures the status stays active between ticks
                    # (re-applied each tick; STACK behaviour accumulates stacks)
                    ctx.apply_status(piece, "sudden_death", 3)

        # Process map effects (board-cell modifiers: slow tiles etc.)
        _process_board_state(ctx, pieces)

        # Process statuses (expire, DOT)
        process_statuses(ctx, pieces)

        # Expire timed modifiers
        expire_modifiers(ctx, pieces)

        if not _both_sides_alive(pieces):
            break

        # Advance meters for living pieces
        for piece in pieces:
            if not piece.alive:
                continue
            # Gates: stun blocks all meter advancement
            if piece.is_gated(StatusGate.BLOCKS_ACTION):
                continue

            # Mana regen — goes to all slots
            mana_regen = _effective_stat(piece, "mana_regen")
            if mana_regen > 0:
                ctx.gain_mana(piece, mana_regen)

        # Cast resolution for all pieces
        for piece in pieces:
            if not piece.alive:
                continue
            process_casts(ctx, piece)
            if not _both_sides_alive(pieces):
                break

        if not _both_sides_alive(pieces):
            break

    # Determine winner
    if ctx.combat_ended:
        return ctx.winner or "draw"

    team_alive = any(p.alive and not p.is_enemy for p in pieces)
    enemy_alive = any(p.alive and p.is_enemy for p in pieces)

    if team_alive and not enemy_alive:
        return "team"
    elif enemy_alive and not team_alive:
        return "enemy"
    else:
        return "draw"
