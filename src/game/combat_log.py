"""Human-readable combat log over a resolved `BattleResult`.

Pure rendering layer: turns the engine's tick-ordered `BattleEvent` stream into
an ordered, step-by-step log. Two consumers:

- The combat UI (T12) walks `group_events_by_tick` to animate the battle.
- Tests use `render_combat_log` for stable golden-snapshot assertions.

No Flet imports, no I/O — the log is a deterministic function of the result.
"""

from __future__ import annotations

from src.game.combat import EVENT_ATTACK, EVENT_CAST, EVENT_DEATH, EVENT_MOVE
from src.game.models import BattleEvent, BattleResult, Champion, Enemy
from src.game.weather_effects import apply_weather


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


def _piece_max_hp(
    team: list[Champion], enemies: list[Enemy], result: BattleResult
) -> dict[str, int]:
    """Reconstruct each piece's weather-modified max HP for the log's HP trace."""
    max_hp: dict[str, int] = {}
    for source in [*team, *enemies]:
        state = apply_weather(source, result.weather)
        max_hp[state.piece_id] = state.max_hp
    return max_hp


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _format_event(
    event: BattleEvent, current_hp: dict[str, int], track_hp: bool
) -> str:
    if event.event_type == EVENT_MOVE:
        return f"{event.actor_id} moves to ({event.note})"

    if event.event_type == EVENT_DEATH:
        killer = ""
        if event.target_id and event.target_id != event.actor_id:
            killer = f" by {event.target_id}"
        return f"{event.actor_id} is defeated{killer}"

    if event.event_type in (EVENT_ATTACK, EVENT_CAST):
        verb = "attacks" if event.event_type == EVENT_ATTACK else "casts at"
        line = (
            f"{event.actor_id} {verb} {event.target_id} "
            f"— {event.amount} {event.note}"
        )
        if track_hp and event.target_id in current_hp:
            before = current_hp[event.target_id]
            after = max(0, before - event.amount)
            current_hp[event.target_id] = after
            line += f" ({event.target_id}: {before} -> {after})"
        return line

    # Unknown event type — render defensively rather than dropping it.
    return f"{event.actor_id} {event.event_type}"


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
        current_hp = _piece_max_hp(team, enemies, result)
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
