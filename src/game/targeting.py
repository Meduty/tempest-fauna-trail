"""Targeting helpers (T20) — effect_systems_design.md §6.3.

Content must not reach into board state directly. All targeting goes
through these functions. When a designer needs a new pattern, add it
here and reuse — never inline into abilities.
"""

from __future__ import annotations

from typing import Any

from src.game.status import StatusGate


def _note_footprint(ctx: Any, kind: str, center_q: int, center_r: int, **geo: Any) -> None:
    """Forward this helper's geometry to `ctx.note_footprint` for the combat view
    (T.12c, V.61). Observer-only: `note_footprint` records only while a cast is in
    flight, and the call no-ops on contexts that don't implement it (test stubs).
    Never changes the helper's returned targets."""
    note = getattr(ctx, "note_footprint", None)
    if note is not None:
        note(kind, center_q, center_r, **geo)


def _filter_hexproof(actor: Any, enemies: list) -> list:
    """Drop hexproof enemies from single-target acquisition (V.40).

    A hexproof piece (`StatusGate.HEXPROOF`) cannot be the *target* of a
    single-target ability or auto-attack; AoE/untargeted effects still hit it
    (they iterate `ctx.enemies_of` directly, not these helpers). An actor with
    `pierces_hexproof` (Spirit @8) ignores the exclusion.
    """
    if getattr(actor, "pierces_hexproof", False):
        return enemies
    return [e for e in enemies if not e.is_gated(StatusGate.HEXPROOF)]


def _candidates(actor: Any, ctx: Any) -> list:
    """Living enemies eligible for single-target acquisition: fog- + hexproof-filtered."""
    return _filter_hexproof(actor, _filter_fog(actor, list(ctx.enemies_of(actor)), ctx))


def _filter_fog(actor: Any, enemies: list, ctx: Any) -> list:
    """Filter enemies that are unreachable due to fog (BoardState.fog_range).

    Reads ctx.board_state (public property on CombatContext).
    If no fog is active, returns the list unchanged.
    """
    board_state = getattr(ctx, "board_state", None)
    if board_state is None or board_state.fog_range is None:
        return enemies
    return [
        e for e in enemies
        if board_state.is_in_fog_range(
            actor.position_q, actor.position_r,
            e.position_q, e.position_r,
        )
    ]


def primary_target(actor: Any, ctx: Any) -> Any | None:
    """The actor's current target (or closest enemy if no current target).

    Respects fog_range from BoardState — targets beyond fog range are excluded —
    and hexproof (V.40) — hexproof enemies are not acquirable as a single target.
    """
    enemies = _candidates(actor, ctx)
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
    """Enemy with the lowest current HP. Respects fog_range + hexproof (V.40)."""
    enemies = _candidates(actor, ctx)
    if not enemies:
        return None
    return min(enemies, key=lambda e: (e.hp, e.id))


def highest_ap_enemy(actor: Any, ctx: Any) -> Any | None:
    """Enemy with the highest ability power (intelligence). Respects fog_range + hexproof (V.40)."""
    enemies = _candidates(actor, ctx)
    if not enemies:
        return None
    return max(enemies, key=lambda e: (e.stat("intelligence"), e.id))


def random_enemy(actor: Any, ctx: Any) -> Any | None:
    """Random enemy (using ctx.rng for determinism). Respects fog_range + hexproof (V.40)."""
    enemies = _candidates(actor, ctx)
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
    _note_footprint(ctx, "circle", piece.position_q, piece.position_r, radius=1)
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
    _note_footprint(ctx, "circle", center_q, center_r, radius=radius)
    result = []
    for e in ctx.enemies_of(of):
        if hex_distance(center_q, center_r, e.position_q, e.position_r) <= radius:
            result.append(e)
    return result


def allies_in_radius(center_q: int, center_r: int, radius: int, of: Any, ctx: Any) -> list:
    """All allies of 'of' within hex radius of center position."""
    from src.game.combat import hex_distance
    _note_footprint(ctx, "circle", center_q, center_r, radius=radius)
    result = []
    for a in ctx.allies_of(of):
        if hex_distance(center_q, center_r, a.position_q, a.position_r) <= radius:
            result.append(a)
    return result


def furthest_enemy(actor: Any, ctx: Any) -> Any | None:
    """Enemy furthest from the actor. Respects hexproof (V.40)."""
    from src.game.combat import hex_distance
    enemies = _filter_hexproof(actor, list(ctx.enemies_of(actor)))
    if not enemies:
        return None
    return max(enemies, key=lambda e: (
        hex_distance(actor.position_q, actor.position_r, e.position_q, e.position_r), e.id
    ))


def line_targets(actor: Any, direction: tuple[int, int], length: int, ctx: Any) -> list:
    """All pieces along a line from actor in the given direction."""
    _note_footprint(ctx, "line", actor.position_q, actor.position_r,
                    direction=direction, length=length)
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
