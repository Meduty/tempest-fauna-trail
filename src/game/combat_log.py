"""Human-readable combat log over a resolved `BattleResult`.

Pure rendering layer: turns the engine's tick-ordered `BattleEvent` stream into
an ordered, step-by-step log. Two consumers:

- The combat UI (T12) walks `group_events_by_tick` to animate the battle.
- Tests use `render_combat_log` for stable golden-snapshot assertions.

No Flet imports, no I/O — the log is a deterministic function of the result.
"""

from __future__ import annotations

from src.game.combat import (
    EVENT_ABILITY,
    EVENT_ATTACK,
    EVENT_CAST,
    EVENT_DEATH,
    EVENT_DESPAWN,
    EVENT_DOT,
    EVENT_HEAL,
    EVENT_MOVE,
    EVENT_SPAWN,
    EVENT_STATUS,
    EVENT_STATUS_EXPIRE,
)
from src.game.models import BattleEvent, BattleResult, Champion, Enemy


def group_events_by_tick(result: BattleResult) -> list[tuple[int, list[BattleEvent]]]:
    """Group the event stream into per-tick steps, preserving order.

    Events are already tick-ordered (and resolution-ordered within a tick) by
    the engine, so this is a contiguous grouping — one entry per tick that had
    at least one event.
    """
    grouped: list[tuple[int, list[BattleEvent]]] = []
    for event in result.events:
        if grouped and grouped[-1][0] == event.tick:
            grouped[-1][1].append(event)
        else:
            grouped.append((event.tick, [event]))
    return grouped


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _format_event(
    event: BattleEvent, current_hp: dict[str, int], track_hp: bool
) -> str:
    if event.event_type == EVENT_MOVE:
        return f"{event.actor_id} moves to ({event.dest_q},{event.dest_r})"

    if event.event_type == EVENT_DEATH:
        killer = ""
        if event.target_id and event.target_id != event.actor_id:
            killer = f" by {event.target_id}"
        return f"{event.actor_id} is defeated{killer}"

    # Ability-framework casts (T.29c): amount 0, note = ability_id, possibly no
    # target → render the activation cleanly without a fake "0 damage" suffix.
    if event.event_type == EVENT_CAST and not event.amount:
        # Mana telemetry (T.36b): show which slot fired + the post-spend mana.
        mana = ""
        if event.slot_idx >= 0:
            mana = f" [slot {event.slot_idx}: -{event.mana_spent} → {event.mana_after} mana]"
        if event.target_id:
            return f"{event.actor_id} casts {event.note} at {event.target_id}{mana}"
        return f"{event.actor_id} casts {event.note}{mana}"

    if event.event_type in (EVENT_ATTACK, EVENT_CAST, EVENT_ABILITY, EVENT_DOT):
        verb = {
            EVENT_ATTACK: "attacks", EVENT_CAST: "casts at",
            EVENT_ABILITY: "hits", EVENT_DOT: "burns",
        }[event.event_type]
        line = (
            f"{event.actor_id} {verb} {event.target_id} "
            f"— {event.amount} {event.note}"
        )
        line += _hp_trace(event, current_hp, track_hp)
        return line

    if event.event_type == EVENT_HEAL:
        line = f"{event.actor_id} heals {event.target_id} — +{event.amount}"
        line += _hp_trace(event, current_hp, track_hp)
        return line

    if event.event_type == EVENT_STATUS:
        stacks = f" x{event.amount}" if event.amount > 1 else ""
        return f"{event.actor_id} gains {event.note}{stacks}"

    if event.event_type == EVENT_STATUS_EXPIRE:
        return f"{event.actor_id} loses {event.note}"

    if event.event_type == EVENT_SPAWN:
        return f"{event.actor_id} spawns at ({event.dest_q},{event.dest_r})"

    if event.event_type == EVENT_DESPAWN:
        return f"{event.actor_id} expires"

    # Unknown event type — render defensively rather than dropping it.
    return f"{event.actor_id} {event.event_type}"


def _hp_trace(event: BattleEvent, current_hp: dict[str, int], track_hp: bool, *, target: str | None = None) -> str:
    """`(target: before -> after)` suffix. Prefers the event's `hp_after`
    (engine truth — barrier/DOT/heal-correct, T.37a) over damage subtraction;
    falls back to subtraction for legacy events (`hp_after == -1`). `target`
    overrides whose HP changed (heals change the heal's *target*, not actor)."""
    tid = target if target is not None else event.target_id
    if not track_hp or tid not in current_hp:
        return ""
    before = current_hp[tid]
    if event.hp_after >= 0:
        after = event.hp_after
    elif event.event_type == EVENT_HEAL:
        after = before + event.amount
    else:
        after = max(0, before - event.amount)
    current_hp[tid] = after
    return f" ({tid}: {before} -> {after})"


def format_combat_log(
    result: BattleResult,
    *,
    team: list[Champion] | None = None,
    enemies: list[Enemy] | None = None,
) -> list[str]:
    """Render a `BattleResult` as ordered log lines.

    Pass `team` and `enemies` (the same rosters handed to `resolve_combat`) to
    include a running `(target: before -> after)` HP trace on every hit. Omit
    them for a lighter log with damage numbers only.
    """
    track_hp = team is not None and enemies is not None
    current_hp: dict[str, int] = {}

    lines: list[str] = ["=== Tempest Fauna Trail — Combat Log ==="]
    lines.append(f"Node: {result.node_id or '-'} | Weather: {result.weather.value}")

    if track_hp:
        assert team is not None and enemies is not None
        # max HP comes from the engine's own pieces via the result — the single
        # source of truth (weather + passives already applied). No recompute.
        current_hp = dict(result.piece_max_hp)
        lines.append("Team:    " + (", ".join(c.id for c in team) or "-"))
        lines.append("Enemies: " + (", ".join(e.id for e in enemies) or "-"))
    lines.append("")

    grouped = group_events_by_tick(result)
    if not grouped:
        lines.append("(no actions — stalemate)")
    for tick, events in grouped:
        lines.append(f"[tick {tick:04d}]")
        for event in events:
            lines.append("  " + _format_event(event, current_hp, track_hp))
    lines.append("")

    lines.append(f"=== Result: {result.outcome.value.upper()} ===")
    duration = (
        f"Duration: {result.duration_ticks} ticks · "
        f"{_plural(result.rounds, 'round')} · {_plural(result.turns, 'turn')}"
    )
    if result.timed_out:
        duration += " · timed out"
    lines.append(duration)

    survivors = result.surviving_team_ids + result.surviving_enemy_ids
    lines.append("Survivors: " + (", ".join(survivors) or "none"))

    dealt = ", ".join(
        f"{pid} {amount}"
        for pid, amount in result.team_damage_dealt.items()
        if amount
    )
    lines.append("Damage dealt: " + (dealt or "none"))
    return lines


def render_combat_log(
    result: BattleResult,
    *,
    team: list[Champion] | None = None,
    enemies: list[Enemy] | None = None,
) -> str:
    """`format_combat_log` joined into a single newline-delimited string."""
    return "\n".join(format_combat_log(result, team=team, enemies=enemies))
