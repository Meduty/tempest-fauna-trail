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

from src.game.combat import (
    EVENT_ATTACK,
    EVENT_CAST,
    EVENT_DOT,
    EVENT_MOVE,
    MAX_TICKS,
    ROUND_TICKS,
)
from src.game.combat_log import group_events_by_tick
from src.game.models import (
    BattleEvent,
    BattleResult,
    Champion,
    Enemy,
    Footprint,
    WeatherState,
)
from src.game.registries import ABILITY_META

# Beats that count as "actions" on the projected queue (V.56 — moves render
# smaller + movement-iconed; attacks/casts are the primary entries). dot/heal/
# status/spawn/despawn are *cues* (they animate on their step) but are not queue
# entries.
_QUEUE_KINDS: frozenset[str] = frozenset({EVENT_MOVE, EVENT_ATTACK, EVENT_CAST})

# How many future rounds the action queue projects ahead of the cursor's round.
QUEUE_LOOKAHEAD_ROUNDS = 2

# --- Ability-intent classification (T.12c-B) ---------------------------------
# Tag → intent, from `AbilityMeta.tags` (the UI-iconography vocab, V.38). Element
# tags (`magic`/`physical`/`true`) mark a *damage* ability; `heal`/`summon` are
# explicit; an ability with a buff/support tag (and no damage element) is a buff;
# anything else — including unknown ids with no tags — defaults to *damage* (the
# safe, most-common cast shape). `control` is an orthogonal flag (the ability also
# applies hard/soft CC) used for telegraphs.
_INTENT_DAMAGE_TAGS: frozenset[str] = frozenset({"magic", "physical", "true"})
_INTENT_BUFF_TAGS: frozenset[str] = frozenset({
    "buff", "defense", "haste", "shield", "aura", "team", "empower", "support",
    "lifesteal", "evasion", "reflect", "penetration", "crit", "mana", "tempo",
    "scaling",
})
_INTENT_CONTROL_TAGS: frozenset[str] = frozenset({
    "stun", "root", "slow", "fear", "silence", "taunt", "disarm", "freeze",
    "debuff", "control",
})


@dataclass(frozen=True, slots=True)
class Intent:
    """An ability's presentation intent (T.12c-B). `kind` drives the VFX shape
    family (damage shape vs ally halo vs summon); `control` adds a telegraph."""

    kind: str  # "damage" | "heal" | "buff" | "summon"
    control: bool = False


def classify_intent(ability_id: str) -> Intent:
    """Map an ability id → presentation `Intent` from its `AbilityMeta.tags` (pure).

    Priority: heal → summon → damage (any element tag) → buff (a buff/support tag)
    → damage (default, no matching tag). The `control` flag is set whenever a
    control tag is present, regardless of kind. Unknown ids (no `AbilityMeta`)
    hit the default and classify as plain `damage` (a damage shape is the engine's
    most common cast)."""
    meta = ABILITY_META.get(ability_id)
    tags = frozenset(meta.tags) if meta is not None else frozenset()
    control = bool(tags & _INTENT_CONTROL_TAGS)
    if "heal" in tags:
        kind = "heal"
    elif "summon" in tags:
        kind = "summon"
    elif tags & _INTENT_DAMAGE_TAGS:
        kind = "damage"
    elif tags & _INTENT_BUFF_TAGS:
        kind = "buff"
    else:
        kind = "damage"
    return Intent(kind=kind, control=control)

SUDDEN_DEATH_TICK = MAX_TICKS  # = engine.SUDDEN_DEATH_TICK_START; the sudden-death threshold


def is_sudden_death(tick: int) -> bool:
    """True once the fight has entered the sudden-death timeout window."""
    return tick >= SUDDEN_DEATH_TICK


def pre_beat_ticks(step: "Step") -> list[int]:
    """Distinct ticks present in a step's interstitial DOT `pre_beats`, ascending
    — the drip reveals one tick-group per entry (same-tick beats together)."""
    return sorted({b.tick for b in step.pre_beats})


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
    map_effect_id: str = ""  # boss fights (T.12b) — board map effect; "" = non-boss
    # Optional starting-position override (piece-id → (q, r)) — the prep-phase /
    # dev-harness hand-placement path. None = deterministic default formation.
    positions: dict[str, tuple[int, int]] | None = None


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
    # Recorded targeting footprints at this tick (T.12c, V.61) — the view animates
    # them as per-ability circle/line shapes, joined to a `cast` beat by `cast_id`
    # for element colour. Geometry only, no resource numbers (B.28 guard holds).
    footprints: tuple[Footprint, ...] = ()


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
        """**Strictly-upcoming** actions (T.12d_b): everything at a tick *after* the
        resolved cursor tick, spanning the current round + the next
        `QUEUE_LOOKAHEAD_ROUNDS` (round-split markers come from each entry's
        `round`). `> now` (not `>=`) drops the just-resolved tick's entries off the
        rail as the cursor lands on them. At `cursor = -1`/tick 0 every real action
        is `tick > 0`, so the opening rail is full."""
        now = self.tick_at(cursor)
        cur_round = now // ROUND_TICKS
        max_round = cur_round + QUEUE_LOOKAHEAD_ROUNDS
        return [
            e for e in self._actions
            if e.tick > now and e.round <= max_round
        ]

    def next_action_tick(self, cursor: int) -> int | None:
        """The lowest upcoming action tick (the **next step**'s tick) — the queue
        chips at this tick are the ones a single Next press resolves, so the view
        highlights them as "next up". None when nothing is upcoming."""
        q = self.queue(cursor)
        return q[0].tick if q else None


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
    # Footprints joined to their action step by tick (a footprint is recorded
    # mid-handler at the cast's tick, so it shares the cast action step's tick).
    fps_by_tick: dict[int, list[Footprint]] = {}
    for fp in result.footprints:
        fps_by_tick.setdefault(fp.tick, []).append(fp)

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
                footprints=tuple(fps_by_tick.get(tick, ())),
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
