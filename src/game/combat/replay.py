"""Deterministic combat replay / inspect-at-tick (T.37b).

Combat state for a view is **recomputed, never recorded** (V.55): because
`resolve_combat` is byte-identical for the same `(team, enemies, weather, seed,
run_mods)`, re-running the engine to a tick reproduces the exact live piece
state at that tick — HP, barriers, per-slot mana, effective stats (STR/AS ramp
included), statuses, position. `inspect_at_tick` does that and returns read-only
value structs; raw `Piece` and Flet types never escape `src/game/` (V.1).

This module adds **no** new combat path — it drives the same `engine.run` (via
its `stop_after_tick` hook) over the same `build_combat` wiring `resolve_combat`
uses, so it cannot drift from the resolved fight.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from src.game.models import Champion, Enemy, WeatherState

# Effective stats surfaced to the view — read through `piece.stat()` so every
# modifier (weather/item/augment/trait/in-combat ramp) is already folded in.
_STAT_KEYS: tuple[str, ...] = (
    "max_hp", "strength", "intelligence", "armor", "resistance",
    "attack_speed", "move_speed", "mana_regen", "threat", "attack_range",
    "crit_chance", "penetration", "penetration_pct",
)


@dataclass(frozen=True, slots=True)
class SlotView:
    """One ability slot's live mana (V.48)."""
    current_mana: int
    mana_cost: int
    max_mana: int
    priority: int


@dataclass(frozen=True, slots=True)
class StatusView:
    status_id: str
    stacks: int
    remaining_ticks: int


@dataclass(frozen=True, slots=True)
class PieceView:
    """Read-only snapshot of one piece's live state at an inspected tick."""
    id: str
    is_enemy: bool
    affinity: WeatherState
    alive: bool
    summon: bool
    q: int
    r: int
    hp: int
    max_hp: int
    barrier_total: int
    stats: Mapping[str, float]   # read-only (MappingProxyType) — honours frozen
    mana: tuple[SlotView, ...]
    statuses: tuple[StatusView, ...]


def _view(piece: Any) -> PieceView:
    return PieceView(
        id=piece.id,
        is_enemy=piece.is_enemy,
        affinity=piece.affinity,
        alive=piece.alive,
        summon=piece.summon,
        q=piece.position_q,
        r=piece.position_r,
        hp=int(piece.hp),
        max_hp=int(piece.max_hp),
        barrier_total=int(piece.barrier_total),
        stats=MappingProxyType({k: piece.stat(k) for k in _STAT_KEYS}),
        mana=tuple(
            SlotView(int(s.current_mana), s.mana_cost, s.max_mana, s.priority)
            for s in piece.actives
        ),
        statuses=tuple(
            StatusView(s.status_id, s.stacks, s.remaining_ticks)
            for s in piece.statuses
        ),
    )


def _clone_run_mods(run_mods: Any) -> Any:
    """Isolate the *mutable* surface (`augment_state` quest trackers) so an
    inspect re-run never mutates the caller's state (V.55). Shallow-copies the
    `RunModifiers` (keeps the lightweight `run` back-ref) but deep-copies
    `augment_state`; avoids deep-copying the whole `Run`."""
    if run_mods is None:
        return None
    clone = copy.copy(run_mods)
    clone.augments = list(run_mods.augments)
    clone.augment_state = copy.deepcopy(run_mods.augment_state)
    return clone


def inspect_at_tick(
    team: list[Champion],
    enemies: list[Enemy],
    weather: WeatherState,
    *,
    run_mods: Any = None,
    tick: int,
) -> list[PieceView]:
    """Re-run the deterministic engine to `tick` and read every piece's live
    state (pure; no recorder, stores nothing). `tick=0` → state right after
    combat start (initial board); `tick=N` → after ticks 1..N. Byte-identical to
    the same tick of the resolved fight (V.55/V.2)."""
    from src.game.combat.engine import run as run_combat
    from src.game.combat.resolve import build_combat

    ctx, _ = build_combat(
        team, enemies, weather, run_mods=_clone_run_mods(run_mods), with_recorder=False
    )
    run_combat(ctx, None, stop_after_tick=max(0, tick))
    return [_view(p) for p in ctx.all_pieces()]
