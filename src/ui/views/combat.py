"""Combat view (T.12a) — the TFT-style hex-board fight, interactive + read-only.

Pure presentation over the replay backend (V.56). The view:

1. Resolves the fight once: `resolve_combat(session…)` → `BattleResult` → the
   animation-cue + action-queue `Playback` (`ui/combat_playback.py`).
2. Holds **one forward `CombatReplay`** and drives it as the player steps, reading
   **live HP/mana/stat/position** off it (V.57) — never reconstructing resources
   from the event stream (incomplete for ability burst, B.28).

Default playback = manual event-step (Next); autoplay is opt-in + event-paced,
never tick=second (V.56). `TICKS_PER_SECOND` (V.39) renders durations as text
only. No combat math here — `ui/` imports `game/`, never the reverse (V.1).
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

import flet as ft
import flet.canvas as cv

from src.game.ability_text import TICKS_PER_SECOND, render_for
from src.game.combat import (
    BOARD_HEIGHT,
    BOARD_WIDTH,
    CombatReplay,
    EVENT_ABILITY,
    EVENT_ATTACK,
    EVENT_CAST,
    EVENT_DOT,
    EVENT_HEAL,
    ROUND_TICKS,
    resolve_combat,
)
from src.game.combat.engine import DMG_MAGICAL, DMG_TRUE
from src.game.combat.recorder import DMG_DOT, DMG_PHYSICAL
from src.game.combat.replay import PieceView
from src.game.models import CombatOutcome
from src.ui.combat_playback import CombatSession, Playback, QueueEntry, build_playback
from src.ui.components.meter_bar import meter_bar
from src.ui.theme import (
    ACCENT,
    AFFINITY_COLORS,
    BG,
    DANGER,
    DOT_DAMAGE,
    FONT_MONO,
    SPACING_LG,
    SPACING_MD,
    SPACING_SM,
    SUCCESS,
    SURFACE,
    SURFACE_ELEVATED,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

# Floating damage-number colour by damage-type `note` (V.57 numbers come from
# the beat's `amount`; the bar lands on the live stepper hp). phys=red, magic=
# blue, true=white, dot=purple. Heal (green) handled separately.
_DMG_COLORS: dict[str, str] = {
    DMG_PHYSICAL: DANGER,
    DMG_MAGICAL: ACCENT,
    DMG_TRUE: TEXT_PRIMARY,
    DMG_DOT: DOT_DAMAGE,
}

# --- Board geometry (pixel layout of the 10×7 hex grid) ---
_MARGIN_X = 40
_MARGIN_Y = 34
_COL_W = 46
_ROW_H = 50
_TOKEN_R = 17
_BAR_W = 34

_BOARD_W = _MARGIN_X * 2 + (BOARD_WIDTH - 1) * _COL_W
_BOARD_H = _MARGIN_Y * 2 + (BOARD_HEIGHT - 1) * _ROW_H + _ROW_H // 2

_AUTOPLAY_INTERVAL_S = 0.75  # event-paced (first-pass, tunable); fast-fwd = no delay


def _cell_xy(q: int, r: int) -> tuple[float, float]:
    """Offset-hex (q,r) → pixel centre. Odd columns stagger down half a row."""
    x = _MARGIN_X + q * _COL_W
    y = _MARGIN_Y + r * _ROW_H + (_ROW_H // 2 if q % 2 else 0)
    return float(x), float(y)


def _initials(name: str) -> str:
    parts = [p for p in name.replace("_", " ").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def _secs(ticks: int) -> str:
    return f"{ticks / TICKS_PER_SECOND:.1f}s"


class _ViewStatSource:
    """Adapts a `PieceView` to the `.stat(name)` interface `ability_text.render`
    expects, so ability tooltips show numbers scaled to the piece's *current*
    effective stats at the cursor tick. Missing keys → 0."""

    __slots__ = ("_stats",)

    def __init__(self, view: PieceView) -> None:
        self._stats = view.stats

    def stat(self, name: str) -> float:
        return float(self._stats.get(name, 0.0))


def build_combat_view(
    page: ft.Page,
    session: CombatSession,
    on_exit: Callable[[], None],
) -> ft.View:
    """Build the `/combat` view for one `CombatSession`. `on_exit` is called by
    the combat-end panel's Continue button (returns to the producer)."""
    result = resolve_combat(
        session.team, session.enemies, session.weather,
        node_id=session.node_id, run_mods=session.run_mods,
    )
    playback = build_playback(result)

    # Display-name + roster lookups (summons fall back to their id).
    name_by_id: dict[str, str] = {c.id: c.name for c in session.team}
    name_by_id.update({e.id: e.name for e in session.enemies})
    champ_by_id = {c.id: c for c in session.team}
    # Ability ids per piece (active + passive) for hover tooltips.
    abilities_by_id: dict[str, list[str]] = {}
    for _unit in (*session.team, *session.enemies):
        ids = list(getattr(_unit, "active_abilities", []) or [])
        if getattr(_unit, "passive_ability", ""):
            ids.append(_unit.passive_ability)
        abilities_by_id[_unit.id] = ids

    def _ability_tooltip(pv: PieceView) -> str:
        """Token hover text: the piece's name + each ability's name + live blurb
        (rendered against the piece's current effective stats, V.38)."""
        lines = [name_by_id.get(pv.id, pv.id)]
        src = _ViewStatSource(pv)
        for aid in abilities_by_id.get(pv.id, []):
            rendered = render_for(aid, src)
            if rendered is not None:
                lines.append(f"• {rendered.name}: {rendered.text}")
        return "\n".join(lines)

    # --- mutable view state ---
    state: dict[str, Any] = {
        "cursor": -1,          # -1 = initial board (tick 0); 0..N-1 = step index
        "replay": CombatReplay(
            session.team, session.enemies, session.weather, run_mods=session.run_mods,
        ),
        "selected": None,      # selected piece id (inspect)
        "playing": False,
        "alive": True,         # cleared on view pop → stops the autoplay thread
    }

    # --- controls that get rebuilt each render ---
    board_stack = ft.Stack(width=_BOARD_W, height=_BOARD_H)
    queue_row = ft.Row(spacing=SPACING_SM, scroll=ft.ScrollMode.AUTO, height=64)
    inspect_col = ft.Column(spacing=SPACING_SM, width=300, scroll=ft.ScrollMode.AUTO)
    status_text = ft.Text("", size=12, color=TEXT_MUTED)
    # Full-screen overlay for the combat-end panel. MUST stay `visible=False`
    # until the fight ends — a visible expand=True container on top of `body`
    # in the root Stack would intercept all pointer events (Next / token clicks
    # frozen). `visible=False` removes it from hit-testing entirely.
    end_overlay = ft.Container(
        visible=False, alignment=ft.Alignment.CENTER, expand=True,
        bgcolor=ft.Colors.with_opacity(0.75, BG),
    )

    def _last_cursor() -> int:
        return playback.step_count() - 1

    def _current_tick() -> int:
        return playback.tick_at(state["cursor"])

    def _advance_to(new_cursor: int) -> None:
        """Move the cursor and drive the (forward-only) replay to its tick.
        Backward / restart rebuilds a fresh `CombatReplay` (§4.8)."""
        new_cursor = max(-1, min(new_cursor, _last_cursor()))
        target_tick = playback.tick_at(new_cursor)
        replay: CombatReplay = state["replay"]
        if target_tick < replay.tick:
            replay = CombatReplay(
                session.team, session.enemies, session.weather, run_mods=session.run_mods,
            )
            state["replay"] = replay
        replay.step_to(target_tick)
        state["cursor"] = new_cursor

    # ---------- board ----------
    def _build_board(pieces: list[PieceView]) -> None:
        shapes: list[cv.Shape] = []
        overlays: list[ft.Control] = []

        # subtle cell grid (behind the tokens)
        for q in range(BOARD_WIDTH):
            for r in range(BOARD_HEIGHT):
                cx, cy = _cell_xy(q, r)
                shapes.append(cv.Circle(
                    cx, cy, 3,
                    ft.Paint(color=SURFACE_ELEVATED, style=ft.PaintingStyle.FILL),
                ))

        # current step's cue beats — floating numbers keyed by target
        cur_beats = ()
        if state["cursor"] >= 0:
            cur_beats = playback.steps[state["cursor"]].beats
        pos_by_id = {p.id: p for p in pieces}

        for p in pieces:
            if not p.alive:
                continue
            cx, cy = _cell_xy(p.q, p.r)
            tint = AFFINITY_COLORS.get(p.affinity, ACCENT)

            # selection ring
            if p.id == state["selected"]:
                shapes.append(cv.Circle(
                    cx, cy, _TOKEN_R + 4,
                    ft.Paint(color=ACCENT, style=ft.PaintingStyle.STROKE, stroke_width=3),
                ))
            # token disc + enemy outline
            shapes.append(cv.Circle(
                cx, cy, _TOKEN_R,
                ft.Paint(color=tint, style=ft.PaintingStyle.FILL),
            ))
            shapes.append(cv.Circle(
                cx, cy, _TOKEN_R,
                ft.Paint(
                    color=DANGER if p.is_enemy else SUCCESS,
                    style=ft.PaintingStyle.STROKE, stroke_width=2,
                ),
            ))
            shapes.append(cv.Text(
                cx - _TOKEN_R, cy - 8,
                _initials(name_by_id.get(p.id, p.id)),
                ft.TextStyle(size=11, weight=ft.FontWeight.BOLD, color="#111111"),
            ))

            # HP bar overlay below the token
            overlays.append(ft.Container(
                left=cx - _BAR_W / 2, top=cy + _TOKEN_R + 2, width=_BAR_W,
                content=meter_bar(current=p.hp, maximum=max(1, p.max_hp), height=5, width=_BAR_W),
            ))
            # mana bar (first slot) if the piece has mana
            if p.mana:
                slot = p.mana[0]
                overlays.append(ft.Container(
                    left=cx - _BAR_W / 2, top=cy + _TOKEN_R + 9, width=_BAR_W,
                    content=meter_bar(
                        current=slot.current_mana, maximum=max(1, slot.max_mana),
                        color=ACCENT, warn_color=ACCENT, danger_color=ACCENT,
                        height=4, width=_BAR_W,
                    ),
                ))
            # transparent click target (robust hit-test, no canvas gesture math);
            # hover tooltip shows the piece's abilities + live blurbs.
            overlays.append(ft.Container(
                left=cx - _TOKEN_R, top=cy - _TOKEN_R,
                width=_TOKEN_R * 2, height=_TOKEN_R * 2,
                border_radius=_TOKEN_R, bgcolor="#00000000",
                on_click=lambda _e, pid=p.id: _select(pid),
                tooltip=_ability_tooltip(p),
            ))

        # floating damage / heal numbers for this step's beats. Monospaced for
        # legibility; colour by damage type (phys red / magic blue / true white /
        # dot purple, heal green); crit marked with `!` + a size bump rather than
        # colour (keeps the type colour readable); multiple numbers on one target
        # staggered so they don't overlap (research §7.1).
        hit_count: dict[str, int] = {}
        for b in cur_beats:
            tgt = pos_by_id.get(b.target_id or "")
            if tgt is None or not b.amount:
                continue
            if b.event_type == EVENT_HEAL:
                txt, col = f"+{b.amount}", SUCCESS
            elif b.event_type in (EVENT_ATTACK, EVENT_ABILITY, EVENT_CAST, EVENT_DOT):
                col = _DMG_COLORS.get(b.note, DANGER)
                txt = f"-{b.amount}" + ("!" if b.is_crit else "")
            else:
                continue
            tx, ty = _cell_xy(tgt.q, tgt.r)
            n = hit_count.get(b.target_id, 0)
            hit_count[b.target_id] = n + 1
            shapes.append(cv.Text(
                tx - 6 + n * 6, ty - _TOKEN_R - 18 - n * 14, txt,
                ft.TextStyle(
                    size=15 if b.is_crit else 13, weight=ft.FontWeight.BOLD,
                    color=col, font_family=FONT_MONO,
                ),
            ))

        board_stack.controls = [cv.Canvas(shapes=shapes, width=_BOARD_W, height=_BOARD_H), *overlays]

    # ---------- action queue ----------
    def _queue_chip(entry: QueueEntry) -> ft.Control:
        is_move = entry.is_move
        label = _initials(name_by_id.get(entry.actor_id, entry.actor_id))
        icon = "→" if is_move else ("✦" if entry.kind == EVENT_CAST else "⚔")
        size = 34 if is_move else 44
        return ft.Container(
            width=size, height=size, border_radius=6,
            bgcolor=SURFACE_ELEVATED if not is_move else SURFACE,
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                [ft.Text(icon, size=10 if is_move else 12, color=TEXT_MUTED),
                 ft.Text(label, size=9 if is_move else 11, color=TEXT_PRIMARY)],
                spacing=0, alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True,
            ),
            tooltip=f"{name_by_id.get(entry.actor_id, entry.actor_id)} · {entry.kind} · {_secs(entry.tick)}",
        )

    def _build_queue() -> None:
        entries = playback.queue(state["cursor"])
        controls: list[ft.Control] = []
        last_round: int | None = None
        for e in entries:
            if last_round is not None and e.round != last_round:
                controls.append(ft.Container(
                    width=2, height=44, bgcolor=ACCENT,
                    tooltip=f"round {e.round + 1}",
                ))
            controls.append(_queue_chip(e))
            last_round = e.round
        if not controls:
            controls = [ft.Text("— no upcoming actions —", size=12, color=TEXT_MUTED)]
        queue_row.controls = controls

    # ---------- inspect panel ----------
    def _stat_row(label: str, value: str) -> ft.Control:
        return ft.Row(
            [ft.Text(label, size=11, color=TEXT_MUTED, width=90),
             ft.Text(value, size=11, color=TEXT_PRIMARY)],
            spacing=SPACING_SM,
        )

    def _build_inspect(pieces: list[PieceView]) -> None:
        controls: list[ft.Control] = []
        sel = state["selected"]
        pv = next((p for p in pieces if p.id == sel), None)
        if pv is not None:
            controls.append(ft.Text(
                name_by_id.get(pv.id, pv.id), size=15, weight=ft.FontWeight.BOLD,
                color=AFFINITY_COLORS.get(pv.affinity, TEXT_PRIMARY),
            ))
            controls.append(ft.Text(
                f"{pv.affinity.value} · {'enemy' if pv.is_enemy else 'ally'}"
                + (" · summon" if pv.summon else ""),
                size=11, color=TEXT_MUTED,
            ))
            controls.append(_stat_row("HP", f"{pv.hp} / {pv.max_hp}"))
            if pv.barrier_total:
                controls.append(_stat_row("barrier", str(pv.barrier_total)))
            for key in ("strength", "intelligence", "attack_speed", "armor", "resistance", "attack_range"):
                controls.append(_stat_row(key, f"{pv.stats.get(key, 0):.0f}"))
            for i, slot in enumerate(pv.mana):
                controls.append(_stat_row(
                    f"mana[{i}]", f"{slot.current_mana} / {slot.max_mana} (cost {slot.mana_cost})"))
            for st in pv.statuses:
                controls.append(_stat_row(
                    st.status_id, f"x{st.stacks} · {_secs(st.remaining_ticks)}"))
            champ = champ_by_id.get(pv.id)
            if champ is not None:
                if champ.items:
                    controls.append(ft.Divider(height=8))
                    controls.append(ft.Text("Items", size=12, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY))
                    controls.extend(ft.Text(f"• {i}", size=11, color=TEXT_MUTED) for i in champ.items)
                if champ.traits:
                    controls.append(ft.Text("Traits", size=12, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY))
                    controls.extend(ft.Text(f"• {t}", size=11, color=TEXT_MUTED) for t in champ.traits)
        else:
            controls.append(ft.Text("Click a piece to inspect.", size=12, color=TEXT_MUTED))

        # global panel: active augments + cleared traits
        controls.append(ft.Divider(height=12))
        controls.append(ft.Text("Team", size=13, weight=ft.FontWeight.BOLD, color=ACCENT))
        augs = list(getattr(session.run_mods, "augments", []) or [])
        controls.append(ft.Text(
            "Augments: " + (", ".join(augs) if augs else "none"),
            size=11, color=TEXT_MUTED, selectable=True,
        ))
        if result.trait_activations:
            controls.append(ft.Text("Cleared traits:", size=11, color=TEXT_MUTED))
            controls.extend(
                ft.Text(f"• {tid} ({n}) ≥{thr}", size=11, color=TEXT_MUTED)
                for tid, n, thr in result.trait_activations
            )
        inspect_col.controls = controls

    # ---------- combat-end panel ----------
    def _build_end_panel() -> None:
        at_end = state["cursor"] >= _last_cursor() and state["replay"].finished
        end_overlay.visible = bool(at_end)
        if not at_end:
            end_overlay.content = None
            return
        outcome = result.outcome
        won = outcome == CombatOutcome.WIN
        dealt = sum(result.team_damage_dealt.values())
        taken = sum(result.team_damage_taken.values())
        end_overlay.content = ft.Container(
            padding=SPACING_LG, border_radius=8, bgcolor=SURFACE_ELEVATED,
            content=ft.Column([
                ft.Text(
                    "Victory" if won else ("Defeat" if outcome == CombatOutcome.LOSS else "Draw"),
                    size=22, weight=ft.FontWeight.BOLD,
                    color=SUCCESS if won else DANGER,
                ),
                ft.Text(f"Survivors — team {len(result.surviving_team_ids)} · "
                        f"enemy {len(result.surviving_enemy_ids)}", size=12, color=TEXT_MUTED),
                ft.Text(f"Damage dealt {dealt} · taken {taken}"
                        + (" · timed out" if result.timed_out else ""),
                        size=12, color=TEXT_MUTED),
                ft.FilledButton("Continue", on_click=lambda _e: on_exit()),
            ], spacing=SPACING_SM, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        )

    # ---------- render ----------
    def _render() -> None:
        if not state["alive"]:
            return
        pieces = state["replay"].pieces()
        _build_board(pieces)
        _build_queue()
        _build_inspect(pieces)
        _build_end_panel()
        tick = _current_tick()
        rnd = tick // ROUND_TICKS + 1
        status_text.value = (
            f"tick {tick} ({_secs(tick)}) · round {rnd} · "
            f"step {state['cursor'] + 1}/{playback.step_count()}"
        )
        page.update()

    # ---------- controls / interactions ----------
    def _select(pid: str) -> None:
        state["selected"] = pid
        _render()

    def _step(delta: int) -> None:
        _advance_to(state["cursor"] + delta)
        _render()

    def _restart() -> None:
        state["playing"] = False
        _advance_to(-1)
        _render()

    def _fast_forward() -> None:
        state["playing"] = False
        _advance_to(_last_cursor())
        _render()

    async def _autoplay_loop() -> None:
        # Async loop driven by the flet event loop (`page.run_task`) — reliable
        # in flet 0.85 where a bare thread's `page.update()` may not repaint.
        while state["alive"] and state["playing"]:
            await asyncio.sleep(_AUTOPLAY_INTERVAL_S)
            if not (state["alive"] and state["playing"]):
                break
            if state["cursor"] >= _last_cursor():
                state["playing"] = False
                autoplay_btn.text = "▶ Autoplay"
                _render()
                break
            _advance_to(state["cursor"] + 1)
            _render()

    def _toggle_autoplay(_e: Any) -> None:
        state["playing"] = not state["playing"]
        autoplay_btn.text = "⏸ Pause" if state["playing"] else "▶ Autoplay"
        page.update()
        if state["playing"]:
            page.run_task(_autoplay_loop)

    autoplay_btn = ft.OutlinedButton("▶ Autoplay", on_click=_toggle_autoplay)

    controls_row = ft.Row([
        ft.OutlinedButton("◀ Prev", on_click=lambda _e: _step(-1)),
        ft.FilledButton("Next ▶", on_click=lambda _e: _step(1)),
        autoplay_btn,
        ft.OutlinedButton("⏭ End", on_click=lambda _e: _fast_forward()),
        ft.TextButton("↺ Restart", on_click=lambda _e: _restart()),
        ft.Container(expand=True),
        ft.TextButton("Exit", on_click=lambda _e: on_exit()),
    ], spacing=SPACING_SM)

    # ---------- layout ----------
    header = ft.Row([
        ft.Text("Combat", size=18, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
        ft.Container(width=SPACING_LG),
        ft.Text(f"weather: {session.weather.value}", size=12, color=TEXT_MUTED),
        ft.Container(expand=True),
        status_text,
    ])

    left = ft.Column([
        queue_row,
        ft.Container(
            content=board_stack, bgcolor=SURFACE, border_radius=8,
            padding=SPACING_SM, width=_BOARD_W + SPACING_MD, height=_BOARD_H + SPACING_MD,
        ),
        controls_row,
    ], spacing=SPACING_MD)

    body = ft.Row([
        left,
        ft.Container(
            content=inspect_col, bgcolor=SURFACE, border_radius=8,
            padding=SPACING_MD, width=320, expand=True,
        ),
    ], spacing=SPACING_LG, vertical_alignment=ft.CrossAxisAlignment.START, expand=True)

    root = ft.Container(
        bgcolor=BG, padding=SPACING_LG, expand=True,
        content=ft.Column([
            header,
            ft.Stack([body, end_overlay], expand=True),
        ], spacing=SPACING_MD, expand=True),
    )

    def _on_pop(_e: Any) -> None:
        state["alive"] = False
        state["playing"] = False

    view = ft.View(route="/combat", controls=[root], padding=0)
    view.data = _on_pop  # harness wires this into page.on_view_pop

    # initial paint
    _advance_to(-1)
    _render()
    return view
