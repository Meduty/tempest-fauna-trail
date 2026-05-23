"""Targeting helpers (T20) — effect_systems_design.md §6.3.

Content must not reach into board state directly. All targeting goes
through these functions. When a designer needs a new pattern, add it
here and reuse — never inline into abilities.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.game.piece import Piece


def primary_target(actor: Any, ctx: Any) -> Any | None:
    """The actor's current target (or closest enemy if no current target)."""
    from src.game.combat.context import CombatContext
    enemies = list(ctx.enemies_of(actor))
    if not enemies:
        return None
    # Prefer current target if alive
    if actor.target_id:
        for e in enemies:
            if e.id == actor.target_id:
                return e
    # Fallback: closest enemy
    return _closest_enemy(actor, enemies)


def lowest_hp_enemy(actor: Any, ctx: Any) -> Any | None:
    """Enemy with the lowest current HP."""
    enemies = list(ctx.enemies_of(actor))
    if not enemies:
        return None
    return min(enemies, key=lambda e: (e.hp, e.id))


def highest_ap_enemy(actor: Any, ctx: Any) -> Any | None:
    """Enemy with the highest ability power (intelligence)."""
    enemies = list(ctx.enemies_of(actor))
    if not enemies:
        return None
    return max(enemies, key=lambda e: (e.stat("intelligence"), e.id))


def random_enemy(actor: Any, ctx: Any) -> Any | None:
    """Random enemy (using ctx.rng for determinism)."""
    enemies = list(ctx.enemies_of(actor))
    if not enemies:
        return None
    idx = ctx.rng.randint(0, len(enemies) - 1)
    return enemies[idx]


def lowest_hp_ally(actor: Any, ctx: Any) -> Any | None:
    """Ally with the lowest current HP (including self)."""
    allies = list(ctx.allies_of(actor))
    if not allies:
        return None
    return min(allies, key=lambda a: (a.hp, a.id))


def neighbors_of(piece: Any, ctx: Any) -> list:
    """All pieces adjacent (hex distance 1) to the given piece."""
    from src.game.combat import hex_distance
    result = []
    for p in ctx.all_pieces():
        if p is piece or not p.alive:
            continue
        if hex_distance(piece.position_q, piece.position_r, p.position_q, p.position_r) <= 1:
            result.append(p)
    return result


def enemies_in_radius(center_q: int, center_r: int, radius: int, of: Any, ctx: Any) -> list:
    """All enemies of 'of' within hex radius of center position."""
    from src.game.combat import hex_distance
    result = []
    for e in ctx.enemies_of(of):
        if hex_distance(center_q, center_r, e.position_q, e.position_r) <= radius:
            result.append(e)
    return result


def allies_in_radius(center_q: int, center_r: int, radius: int, of: Any, ctx: Any) -> list:
    """All allies of 'of' within hex radius of center position."""
    from src.game.combat import hex_distance
    result = []
    for a in ctx.allies_of(of):
        if hex_distance(center_q, center_r, a.position_q, a.position_r) <= radius:
            result.append(a)
    return result


def furthest_enemy(actor: Any, ctx: Any) -> Any | None:
    """Enemy furthest from the actor."""
    from src.game.combat import hex_distance
    enemies = list(ctx.enemies_of(actor))
    if not enemies:
        return None
    return max(enemies, key=lambda e: (
        hex_distance(actor.position_q, actor.position_r, e.position_q, e.position_r), e.id
    ))


def line_targets(actor: Any, direction: tuple[int, int], length: int, ctx: Any) -> list:
    """All pieces along a line from actor in the given direction."""
    from src.game.combat import hex_distance
    result = []
    q, r = actor.position_q, actor.position_r
    dq, dr = direction
    for _ in range(length):
        q += dq
        r += dr
        for p in ctx.all_pieces():
            if not p.alive:
                continue
            if p.position_q == q and p.position_r == r:
                result.append(p)
    return result


def resolve_targets(selector: str, actor: Any, ctx: Any) -> list:
    """Resolve a target selector string to a list of targets."""
    if not selector:
        return []
    if selector == "primary":
        t = primary_target(actor, ctx)
        return [t] if t else []
    elif selector == "lowest_hp_enemy":
        t = lowest_hp_enemy(actor, ctx)
        return [t] if t else []
    elif selector == "highest_ap_enemy":
        t = highest_ap_enemy(actor, ctx)
        return [t] if t else []
    elif selector == "random_enemy":
        t = random_enemy(actor, ctx)
        return [t] if t else []
    elif selector == "lowest_hp_ally":
        t = lowest_hp_ally(actor, ctx)
        return [t] if t else []
    elif selector == "furthest_enemy":
        t = furthest_enemy(actor, ctx)
        return [t] if t else []
    return []


def _closest_enemy(actor: Any, enemies: list) -> Any | None:
    """Find the closest enemy by hex distance."""
    from src.game.combat import hex_distance
    if not enemies:
        return None
    return min(enemies, key=lambda e: (
        hex_distance(actor.position_q, actor.position_r, e.position_q, e.position_r), e.id
    ))
