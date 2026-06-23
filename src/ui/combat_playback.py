"""Pure, Flet-free combat-playback model for the combat view (T.12a).

The combat view is **pure presentation** over the replay backend (V.56). This
module derives the *animation* layer from a resolved `BattleResult`:

- **`CombatSession`** — the one input bundle the view consumes; built identically
  by the dev harness now and the Prep/Trail `Start Combat` flow later (V.56).
- **`build_playback(result)`** — turns the recorded event stream into ordered
  **animation-cue steps** (one per event-bearing tick) + a forward **action-queue
  projection** (current + next 2 rounds, with round-split markers).

**This model carries NO resource numbers** (hp / mana / barrier). Those are read
live off the forward `CombatReplay` stepper at render time (V.57) — the recorded
stream is *incomplete* for them (registered-ability burst emits no `hp_after`,
B.28). Here we only answer: *which tick to stop at, what to animate there, and
what's coming up.* Pure + deterministic; no Flet import, so it is unit-testable
with no display.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.game.combat import EVENT_ATTACK, EVENT_CAST, EVENT_DOT, EVENT_MOVE, ROUND_TICKS
from src.game.combat_log import group_events_by_tick
from src.game.models import BattleEvent, BattleResult, Champion, Enemy, WeatherState

# Beats that count as "actions" on the projected queue (V.56 — moves render
# smaller + movement-iconed; attacks/casts are the primary entries). dot/heal/
# status/spawn/despawn are *cues* (they animate on their step) but are not queue
# entries.
_QUEUE_KINDS: frozenset[str] = frozenset({EVENT_MOVE, EVENT_ATTACK, EVENT_CAST})

# How many future rounds the action queue projects ahead of the cursor's round.
QUEUE_LOOKAHEAD_ROUNDS = 2


@dataclass(frozen=True, slots=True)
class CombatSession:
    """The combat view's only input — plain game models, Flet-free (V.56).

    The dev harness builds this from selectors now; the Prep/Trail `Start Combat`
    flow builds the identical object later → one view, swappable producers. The
    view owns resolution: it calls `resolve_combat(session…)` for the cue stream
    and drives a `CombatReplay(session…)` for live resource state.
    """

    team: list[Champion]
    enemies: list[Enemy]
    weather: WeatherState
    run_mods: Any = None  # RunModifiers | None (active augments)
    node_id: str = ""


@dataclass(frozen=True, slots=True)
class Step:
    """One **action moment** — the cursor lands on ticks that have a real action
    (attack/cast/ability/move/heal/death/spawn/despawn), never on a DOT-only
    tick. `beats` = the action beats at `tick`; `pre_beats` = the DOT beats that
    ticked *between* the previous action step and this one (rendered as the "what
    bled in between" numbers, so Next goes action→action without instant-
    resolving DOTs and without spamming the cursor with DOT-only steps).

    Resource numbers are NOT here (read them off the stepper, V.57)."""

    tick: int
    round: int
    beats: tuple[BattleEvent, ...]
    pre_beats: tuple[BattleEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class QueueEntry:
    """One upcoming action on the projected queue (V.56)."""

    tick: int
    round: int
    actor_id: str
    kind: str  # EVENT_MOVE | EVENT_ATTACK | EVENT_CAST
    target_id: str | None
    note: str

    @property
    def is_move(self) -> bool:
        return self.kind == EVENT_MOVE


@dataclass(slots=True)
class Playback:
    """Animation-cue steps + action-queue projection over a resolved fight.

    Carries no resource state — the view reads hp/mana/stats/position from the
    live `CombatReplay` stepper at the step's tick (V.57)."""

    steps: list[Step] = field(default_factory=list)
    # All action beats (move/attack/cast) in resolved order — the queue source.
    _actions: list[QueueEntry] = field(default_factory=list)

    def step_count(self) -> int:
        return len(self.steps)

    def tick_at(self, cursor: int) -> int:
        """The tick the cursor points at. `cursor = -1` → tick 0 (initial board);
        `0..len-1` → that step's tick."""
        if cursor < 0 or not self.steps:
            return 0
        cursor = min(cursor, len(self.steps) - 1)
        return self.steps[cursor].tick

    def queue(self, cursor: int) -> list[QueueEntry]:
        """Upcoming actions from the cursor's tick forward, spanning the current
        round + the next `QUEUE_LOOKAHEAD_ROUNDS` (round-split markers come from
        each entry's `round`). Slides forward as the cursor crosses a round
        boundary."""
        now = self.tick_at(cursor)
        cur_round = now // ROUND_TICKS
        max_round = cur_round + QUEUE_LOOKAHEAD_ROUNDS
        return [
            e for e in self._actions
            if e.tick >= now and e.round <= max_round
        ]


def _entry(event: BattleEvent) -> QueueEntry:
    return QueueEntry(
        tick=event.tick,
        round=event.tick // ROUND_TICKS,
        actor_id=event.actor_id,
        kind=event.event_type,
        target_id=event.target_id,
        note=event.note,
    )


def build_playback(result: BattleResult) -> Playback:
    """Derive the action-moment steps + action-queue source from a resolved
    `BattleResult`. Pure + deterministic (no RNG, no Flet).

    DOT-only ticks are **absorbed** into the next action step's `pre_beats`
    rather than becoming their own steps, so stepping is action-to-action and
    DOTs read as "what bled between these two actions" (V.54 stream unchanged —
    this is a view-side regrouping). Trailing DOTs after the last action (e.g.
    sudden-death bleed before the killing tick) attach to a final step.
    """
    steps: list[Step] = []
    pending_dots: list[BattleEvent] = []
    for tick, beats in group_events_by_tick(result):
        dots = [b for b in beats if b.event_type == EVENT_DOT]
        actions = [b for b in beats if b.event_type != EVENT_DOT]
        if actions:
            steps.append(Step(
                tick=tick, round=tick // ROUND_TICKS,
                beats=tuple(actions),
                pre_beats=tuple(pending_dots) + tuple(dots),
            ))
            pending_dots = []
        else:
            pending_dots.extend(dots)  # DOT-only tick → carry to the next action
    if pending_dots:  # trailing DOTs with no following action
        last = pending_dots[-1]
        steps.append(Step(
            tick=last.tick, round=last.tick // ROUND_TICKS,
            beats=(), pre_beats=tuple(pending_dots),
        ))
    queue_actions = [
        _entry(e) for e in result.events if e.event_type in _QUEUE_KINDS
    ]
    return Playback(steps=steps, _actions=queue_actions)
