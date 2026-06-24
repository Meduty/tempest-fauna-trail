"""Deterministic combat replay / inspect-at-tick (T.37b) + forward stepper (T.37c).

Combat state for a view is **recomputed, never recorded** (V.55): because
`resolve_combat` is byte-identical for the same `(team, enemies, weather, seed,
run_mods)`, re-running the engine to a tick reproduces the exact live piece
state at that tick — HP, barriers, per-slot mana, effective stats (STR/AS ramp
included), statuses, position. This is **complete** — including registered-
ability burst the recorded event stream omits (B.28), so it is the combat view's
resource-truth source (V.56/V.57), not the stream's partial `hp_after` fields.

Two read shapes, **one** driver — the single `engine._step_combat` generator
loop (V.29), built over the same `build_combat` wiring `resolve_combat` uses, so
neither can drift from the resolved fight:

- `CombatReplay` — holds one live instance, steps it **forward** (`step_to`) for
  sequential playback (O(total ticks)); reads live `PieceView`s between ticks.
- `inspect_at_tick` — random/backward access; a thin re-run-from-0 wrapper over
  `CombatReplay`.

Raw `Piece` and Flet types never escape `src/game/` (V.1)."""

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


class CombatReplay:
    """A live, **forward-stepping** replay of one deterministic fight (T.37c).

    Holds a single engine instance and drives the **one** `_step_combat`
    generator (V.29) forward via `step_to`, reading live `PieceView`s between
    ticks. This is the combat view's resource-truth source (V.56/V.57): unlike
    the recorded event stream — which omits `hp_after` on registered-ability
    burst (B.28) — the live pieces carry **every** state change exactly.

    Sequential playback drives **one** instance forward (`step_to` over the
    fight's event-bearing ticks) ⇒ O(total ticks). Random/backward access uses
    `inspect_at_tick` (re-run from 0). Forward-only: `step_to` to an earlier tick
    raises.

    Pure + UI-free: `run_mods` is deep-cloned (V.55 — zero caller side effects);
    only read-only `PieceView`s escape, never raw `Piece`/Flet (V.1/V.14).
    """

    def __init__(
        self,
        team: list[Champion],
        enemies: list[Enemy],
        weather: WeatherState,
        *,
        run_mods: Any = None,
        map_effect_id: str = "",
        seed: int = 42,
        positions: dict[str, tuple[int, int]] | None = None,
    ) -> None:
        from src.game.combat.engine import _step_combat
        from src.game.combat.resolve import build_combat

        ctx, _ = build_combat(
            team, enemies, weather, run_mods=_clone_run_mods(run_mods),
            seed=seed, with_recorder=False, positions=positions,
        )
        # Boss replay: attach the map effect before the loop runs (mirrors
        # resolve_boss_combat) so hazard/sunlit/fog reproduce exactly (V.55/V.59).
        if map_effect_id:
            from src.game.loadout import attach_map_effect
            attach_map_effect(map_effect_id, ctx, seed=seed)
        self._ctx = ctx
        self._gen = _step_combat(ctx, None)
        self._tick = 0
        self._winner: str | None = None
        self._exhausted = False
        # Prime to the tick-0 anchor (`on_combat_start` fired, no tick processed),
        # or exhaust immediately on an instant resolution.
        self._advance()

    @property
    def tick(self) -> int:
        """The last fully-processed tick the replay is paused at (0 = start)."""
        return self._tick

    @property
    def winner(self) -> str | None:
        """Winner once the fight is fully drained, else None."""
        return self._winner

    @property
    def finished(self) -> bool:
        return self._exhausted

    def _advance(self) -> None:
        """Pull one yield from the loop generator (one processed tick, or the
        tick-0 anchor). On completion, capture the winner from the generator's
        return value and run no further."""
        if self._exhausted:
            return
        try:
            self._tick = next(self._gen)
        except StopIteration as exc:
            self._exhausted = True
            self._winner = exc.value if exc.value is not None else "draw"

    def step_to(self, tick: int) -> "CombatReplay":
        """Advance forward until paused at `tick` (or the fight ends first).
        Forward-only — a `tick` before the current position raises `ValueError`
        (use `inspect_at_tick` for backward/random seek)."""
        target = max(0, tick)
        if target < self._tick:
            raise ValueError(
                f"CombatReplay is forward-only: cannot step from tick "
                f"{self._tick} back to {target} (use inspect_at_tick)."
            )
        while self._tick < target and not self._exhausted:
            self._advance()
        return self

    def pieces(self) -> list[PieceView]:
        """Live read-only state of every piece at the current tick (incl.
        mid-fight summons). Raw `Piece` never escapes (V.1)."""
        return [_view(p) for p in self._ctx.all_pieces()]

    def board_cells(self) -> list[tuple[int, int, str]]:
        """Live map-effect cells as `(q, r, kind)` value tuples (`kind` ∈
        sunlit/hazard/ley/slow) for the combat-view overlay. Read-only — the raw
        `BoardState` never escapes `src/game/` (V.1)."""
        cells: list[tuple[int, int, str]] = []
        for (q, r), mods in self._ctx.board_state.cell_modifiers.items():
            for m in mods:
                cells.append((q, r, m.kind))
        return sorted(cells)


def inspect_at_tick(
    team: list[Champion],
    enemies: list[Enemy],
    weather: WeatherState,
    *,
    run_mods: Any = None,
    map_effect_id: str = "",
    tick: int,
) -> list[PieceView]:
    """Read every piece's live state at `tick` (pure; no recorder, stores
    nothing). `tick=0` → state right after combat start (initial board);
    `tick=N` → after ticks 1..N. Byte-identical to the same tick of the resolved
    fight (V.55/V.2); `map_effect_id` replays a boss fight's board hazards (V.59).

    Random-access wrapper over `CombatReplay` (re-runs from 0) so the two read
    paths share one driver — no parallel stepping logic (V.29)."""
    return CombatReplay(
        team, enemies, weather, run_mods=run_mods, map_effect_id=map_effect_id,
    ).step_to(max(0, tick)).pieces()
