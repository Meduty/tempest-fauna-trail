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
    EVENT_STATUS,
    ROUND_TICKS,
    resolve_boss_combat,
    resolve_combat,
)
from src.game.combat.engine import DMG_MAGICAL, DMG_TRUE
from src.game.combat.recorder import DMG_DOT, DMG_PHYSICAL
from src.game.combat.replay import PieceView
from src.game.models import CombatOutcome, Footprint
from src.game.registries import ABILITY_META
from src.ui.combat_playback import (
    CombatSession,
    QueueEntry,
    build_playback,
    classify_intent,
    is_sudden_death,
    playback_delay_s,
    pre_beat_ticks,
)
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
    SPACING_XS,
    SUCCESS,
    SURFACE,
    SURFACE_ELEVATED,
    TEXT_MUTED,
    TEXT_PRIMARY,
    WARNING,
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

_TWEEN_MS = 250              # token glide / bar-follow animation duration
# Delay between consecutive action beats *within one tick* (intra-tick stagger).
# Multiple pieces can act on the same tick; the engine records their beats in
# chronological order, and the view reveals them one at a time this far apart so a
# move→attack→… sequence reads in order instead of flashing all at once.
_BEAT_STAGGER_S = 0.22

# Map-effect cell tint by kind (boss board overlay, T.12b).
_CELL_COLORS: dict[str, str] = {
    "hazard": DANGER, "sunlit": WARNING, "ley": ACCENT, "slow": TEXT_MUTED,
}

# Status pip colours (combat view only; falls back to TEXT_MUTED).
_STATUS_COLORS: dict[str, str] = {
    "burn": WARNING, "poison": SUCCESS, "grief": DOT_DAMAGE, "bleed": DANGER,
    "sudden_death": DANGER, "stun": "#FFD54F", "slow": ACCENT, "barrier": ACCENT,
}


def _arrow(x1: float, y1: float, x2: float, y2: float, color: str) -> list:
    """A line from (x1,y1)→(x2,y2) with a small arrowhead at the target end
    (ranged attacks / casts)."""
    import math
    paint = ft.Paint(color=color, style=ft.PaintingStyle.STROKE, stroke_width=2.5)
    shapes = [cv.Line(x1, y1, x2, y2, paint)]
    ang = math.atan2(y2 - y1, x2 - x1)
    for da in (math.radians(150), math.radians(-150)):
        hx = x2 + 9 * math.cos(ang + da)
        hy = y2 + 9 * math.sin(ang + da)
        shapes.append(cv.Line(x2, y2, hx, hy, paint))
    return shapes


def _swoosh(ax: float, ay: float, tx: float, ty: float, color: str) -> list:
    """A minimalist melee slash — a crescent arc across the target, oriented along
    the attack direction (stick-fight 'swoosh'). Drawn at the target token."""
    import math
    r = _TOKEN_R + 6
    paint = ft.Paint(color=color, style=ft.PaintingStyle.STROKE, stroke_width=3.5)
    # centre the arc on the side the attacker is coming from
    facing = math.atan2(ay - ty, ax - tx)
    start = facing - math.radians(75)
    return [cv.Arc(tx - r, ty - r, r * 2, r * 2,
                   start_angle=start, sweep_angle=math.radians(150), paint=paint)]


def _fp_pixel_radius(radius_cells: int) -> float:
    """A footprint's hex radius in cells → pixel radius (≈ one row per cell ring)."""
    return max(float(_TOKEN_R), radius_cells * _ROW_H)


def _footprint_circle(fp: Footprint, color: str, idx: int,
                      scale: float, opacity: float) -> ft.Control:
    """A radius-AoE footprint: translucent fill + ring, keyed + `animate_scale`/
    `animate_opacity` so it pops (expand + fade-in) when revealed and stays as the
    static residue. Keyed by cast id + index so concurrent footprints don't clash."""
    cx, cy = _cell_xy(fp.center_q, fp.center_r)
    pr = _fp_pixel_radius(fp.radius)
    return ft.Container(
        key=f"fp-{fp.cast_id}-{idx}",
        left=cx - pr, top=cy - pr, width=pr * 2, height=pr * 2, border_radius=pr,
        bgcolor=ft.Colors.with_opacity(0.16, color),
        border=ft.Border.all(2.5, color),
        scale=scale, opacity=opacity,
        animate_scale=ft.Animation(_TWEEN_MS, ft.AnimationCurve.EASE_OUT),
        animate_opacity=ft.Animation(_TWEEN_MS, ft.AnimationCurve.EASE_OUT),
    )


def _footprint_line(fp: Footprint, color: str) -> list:
    """A beam footprint: a thick element-coloured line from the origin along the
    direction for `length` cells. Static canvas shape (no roster ability uses
    `line_targets` yet — kept correct for when one does / for direct tests)."""
    cx, cy = _cell_xy(fp.center_q, fp.center_r)
    dq, dr = fp.direction
    ex, ey = _cell_xy(fp.center_q + dq * fp.length, fp.center_r + dr * fp.length)
    return [cv.Line(cx, cy, ex, ey,
                    ft.Paint(color=color, style=ft.PaintingStyle.STROKE, stroke_width=6))]


# Per-ability-shape VFX (T.12c). Element colour from `AbilityMeta.tags` (the
# UI-iconography vocab uses "magic"/"physical"/"true"); falls back to ACCENT.
_ELEMENT_COLORS: dict[str, str] = {
    "physical": DANGER, "magic": ACCENT, "true": TEXT_PRIMARY,
}


def _element_color(ability_id: str) -> str:
    """The footprint shape colour for an ability id, from its `AbilityMeta` element
    tag. Unknown / untagged → ACCENT (V.61: view reads `AbilityMeta`, no math)."""
    meta = ABILITY_META.get(ability_id)
    if meta is not None:
        for tag in meta.tags:
            if tag in _ELEMENT_COLORS:
                return _ELEMENT_COLORS[tag]
    return ACCENT


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


def _mana_bar(current: int, cost: int, maximum: int, *, width: int, height: int = 5) -> ft.Control:
    """Mana bar with **cast-threshold ticks**. `max_mana` (= 2×cost by default,
    V.48) means the fill alone doesn't show when a cast fires — so draw a tick at
    each `k×cost` and highlight the bar once `current ≥ cost` (a cast is ready)."""
    maximum = max(1, maximum)
    ratio = max(0.0, min(1.0, current / maximum))
    ready = cost > 0 and current >= cost
    children: list[ft.Control] = [
        ft.Container(width=width, height=height, bgcolor=SURFACE_ELEVATED, border_radius=height // 2),
        ft.Container(width=max(0.0, ratio * width), height=height,
                     bgcolor=ACCENT, border_radius=height // 2),
    ]
    if cost > 0:
        k = 1
        while k * cost < maximum:
            x = (k * cost / maximum) * width
            children.append(ft.Container(left=x - 0.75, width=1.5, height=height, bgcolor=TEXT_PRIMARY))
            k += 1
    return ft.Container(
        content=ft.Stack(children, width=width, height=height),
        width=width, height=height, border_radius=height // 2,
        border=ft.Border.all(1, SUCCESS) if ready else None,
    )


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
    boss = bool(session.map_effect_id)

    def _new_replay() -> CombatReplay:
        return CombatReplay(
            session.team, session.enemies, session.weather,
            run_mods=session.run_mods, map_effect_id=session.map_effect_id,
            positions=session.positions,
        )

    if boss:
        result = resolve_boss_combat(
            session.team, session.enemies, session.weather,
            map_effect_id=session.map_effect_id, node_id=session.node_id,
            run_mods=session.run_mods, positions=session.positions,
        )
    else:
        result = resolve_combat(
            session.team, session.enemies, session.weather,
            node_id=session.node_id, run_mods=session.run_mods,
            positions=session.positions,
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
        "replay": _new_replay(),
        "selected": None,      # selected piece id (inspect)
        "playing": False,
        "alive": True,         # cleared on view pop → stops the autoplay thread
        "reveal_tick": 0,      # tick cutoff: pre_beats with tick<=this are shown; action at reveal_tick>=step.tick
        "anim_token": 0,       # invalidates an in-flight pre-beat drip on re-advance
        "fp_phase": 1.0,       # footprint-shape pop phase 0→1 (0 = tiny+clear seed, 1 = full). Cosmetic only.
        "reveal_n": 0,         # action beats of the current step revealed so far (intra-tick stagger)
    }

    # --- controls that get rebuilt each render ---
    board_stack = ft.Stack(width=_BOARD_W, height=_BOARD_H)
    board_container = ft.Container(
        content=board_stack, bgcolor=SURFACE, border_radius=8,
        padding=SPACING_SM, width=_BOARD_W + SPACING_MD, height=_BOARD_H + SPACING_MD,
    )
    # Fixed width (= board) + horizontal overflow scroll, so the queue never
    # resizes the layout (which made the inspect panel jump erratically).
    queue_row = ft.Row(spacing=SPACING_SM, scroll=ft.ScrollMode.AUTO, height=64,
                       width=_BOARD_W, vertical_alignment=ft.CrossAxisAlignment.CENTER)
    inspect_col = ft.Column(spacing=SPACING_SM, width=300, scroll=ft.ScrollMode.AUTO)
    status_text = ft.Text("", size=12, color=TEXT_MUTED)
    sudden_death_badge = ft.Container(
        visible=False, padding=ft.Padding(8, 2, 8, 2), border_radius=4,
        bgcolor=ft.Colors.with_opacity(0.2, DANGER),
        content=ft.Text("⚠ SUDDEN DEATH", size=12, weight=ft.FontWeight.BOLD, color=DANGER),
    )
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
            replay = _new_replay()
            state["replay"] = replay
        replay.step_to(target_tick)
        state["cursor"] = new_cursor
        # Default: reveal everything (instant) — `reveal_tick` past the step tick.
        # The animated forward path (`_step(+1)`/autoplay) lowers it then drips.
        state["anim_token"] += 1
        state["reveal_tick"] = target_tick
        # Footprint shapes default to their full static residue; the drip path
        # (`_drip_action_beats` / autoplay) seeds them small first to animate in.
        state["fp_phase"] = 1.0
        # Default: every action beat of the landed step is revealed (static truth,
        # backward/rapid-Next). The forward animated path lowers it to 0 and drips
        # the beats one at a time in recorded chronological order.
        _new_step = playback.steps[new_cursor] if new_cursor >= 0 else None
        state["reveal_n"] = len(_new_step.beats) if _new_step is not None else 0

    # ---------- board ----------
    def _token(p: PieceView, cx: float, cy: float, offx: float = 0.0, offy: float = 0.0) -> ft.Control:
        """Keyed overlay token (circle + initials). Keyed by piece id + given
        `animate_position` so a position change between renders **glides** (canvas
        shapes can't animate). `offx`/`offy` lunge the attacker toward its target
        on an action step (tweens out, returns next step). Doubles as the
        click/inspect hit-target."""
        selected = p.id == state["selected"]
        return ft.Container(
            key=f"tok-{p.id}",
            left=cx - _TOKEN_R + offx, top=cy - _TOKEN_R + offy,
            width=_TOKEN_R * 2, height=_TOKEN_R * 2,
            border_radius=_TOKEN_R, bgcolor=AFFINITY_COLORS.get(p.affinity, ACCENT),
            border=ft.Border.all(3, ACCENT) if selected
            else ft.Border.all(2, DANGER if p.is_enemy else SUCCESS),
            alignment=ft.Alignment.CENTER,
            content=ft.Text(_initials(name_by_id.get(p.id, p.id)),
                            size=11, weight=ft.FontWeight.BOLD, color="#111111"),
            on_click=lambda _e, pid=p.id: _select(pid),
            tooltip=_ability_tooltip(p),
            animate_position=ft.Animation(_TWEEN_MS, ft.AnimationCurve.EASE_OUT),
        )

    def _status_pips(p: PieceView, cx: float, cy: float) -> ft.Control | None:
        if not p.statuses:
            return None
        pips = [
            ft.Container(
                width=11, height=11, border_radius=5,
                bgcolor=_STATUS_COLORS.get(st.status_id, TEXT_MUTED),
                alignment=ft.Alignment.CENTER,
                content=ft.Text(str(st.stacks), size=7, color="#111111") if st.stacks > 1 else None,
                tooltip=f"{st.status_id} ×{st.stacks} · {_secs(st.remaining_ticks)}",
            )
            for st in p.statuses[:5]
        ]
        return ft.Container(
            key=f"st-{p.id}", left=cx - _BAR_W / 2, top=cy + _TOKEN_R + 16,
            content=ft.Row(pips, spacing=2, tight=True),
            animate_position=ft.Animation(_TWEEN_MS, ft.AnimationCurve.EASE_OUT),
        )

    def _build_board(pieces: list[PieceView]) -> None:
        shapes: list[cv.Shape] = []
        overlays: list[ft.Control] = []
        pos_by_id = {p.id: p for p in pieces}

        # subtle cell grid (behind everything)
        for q in range(BOARD_WIDTH):
            for r in range(BOARD_HEIGHT):
                cx, cy = _cell_xy(q, r)
                shapes.append(cv.Circle(
                    cx, cy, 3, ft.Paint(color=SURFACE_ELEVATED, style=ft.PaintingStyle.FILL)))

        # boss map-effect tiles (hazard/sunlit/ley/slow) tinted under the tokens
        for q, r, kind in state["replay"].board_cells():
            cx, cy = _cell_xy(q, r)
            col = _CELL_COLORS.get(kind, TEXT_MUTED)
            shapes.append(cv.Circle(
                cx, cy, _TOKEN_R + 2,
                ft.Paint(color=ft.Colors.with_opacity(0.22, col), style=ft.PaintingStyle.FILL)))

        cursor = state["cursor"]
        reveal_tick = state["reveal_tick"]
        step = playback.steps[cursor] if cursor >= 0 else None
        action_shown = step is not None and reveal_tick >= step.tick
        # Intra-tick stagger: only the first `reveal_n` action beats (recorded in
        # chronological order) are drawn — the forward drip reveals them in turn so
        # multiple pieces acting on one tick animate in sequence, not all at once.
        revealed = step.beats[:state["reveal_n"]] if (action_shown and step is not None) else []

        # Effect lines + attacker lunge — driven off the *effect* beats (attack/
        # ability/heal), NOT the `cast` activation marker (whose target is the
        # caster's combat target, not the ability's real target — that drew heal
        # lines at enemies). Melee attack → red swoosh; ranged/ability → arrow
        # (type colour); heal → green beam to the healed ally; cast marker → a
        # glow ring on the caster. `lunge[actor_id]` (damage only) tweens the token.
        import math

        def _lunge(actor: PieceView, bx: float, by: float) -> None:
            ax, ay = _cell_xy(actor.q, actor.r)
            d = math.hypot(bx - ax, by - ay) or 1.0
            k = min(16.0, d * 0.35)
            lunge[actor.id] = ((bx - ax) / d * k, (by - ay) / d * k)

        lunge: dict[str, tuple[float, float]] = {}
        if action_shown:
            for b in revealed:
                et = b.event_type
                actor = pos_by_id.get(b.actor_id)
                if actor is None:
                    continue
                ax, ay = _cell_xy(actor.q, actor.r)
                if et == EVENT_CAST:  # activation marker only → caster glow ring
                    shapes.append(cv.Circle(
                        ax, ay, _TOKEN_R + 5,
                        ft.Paint(color=ACCENT, style=ft.PaintingStyle.STROKE, stroke_width=2)))
                    continue
                if et not in (EVENT_ATTACK, EVENT_ABILITY, EVENT_HEAL):
                    continue
                tgt = pos_by_id.get(b.target_id or "")
                if tgt is None or tgt.id == actor.id:  # self/AoE → ring on actor
                    ring = SUCCESS if et == EVENT_HEAL else _DMG_COLORS.get(b.note, ACCENT)
                    shapes.append(cv.Circle(
                        ax, ay, _TOKEN_R + 6,
                        ft.Paint(color=ring, style=ft.PaintingStyle.STROKE, stroke_width=2)))
                    continue
                bx, by = _cell_xy(tgt.q, tgt.r)
                if et == EVENT_HEAL:  # green beam to the healed ally (no lunge)
                    shapes.append(cv.Line(
                        ax, ay, bx, by,
                        ft.Paint(color=SUCCESS, style=ft.PaintingStyle.STROKE, stroke_width=2.5)))
                elif et == EVENT_ATTACK and actor.stats.get("attack_range", 9) <= 1.5:
                    shapes.extend(_swoosh(ax, ay, bx, by, DANGER))
                    _lunge(actor, bx, by)
                else:  # ranged attack or ability damage
                    shapes.extend(_arrow(ax, ay, bx, by, _DMG_COLORS.get(b.note, ACCENT)))
                    _lunge(actor, bx, by)

        # Per-ability-shape VFX (T.12c, V.61): the cast's recorded targeting
        # footprint(s). Colour joins each footprint to its cast by `cast_id` (the
        # `cast` beat carries the ability id in `note`). The cast's *intent*
        # (T.12c-B, `classify_intent`) recolours the shape: an ally-directed
        # heal/buff renders as a green halo (not an element colour), and a control
        # ability adds a WARNING telegraph ring just outside the AoE. A `circle`
        # (radius AoE) is an animated overlay — translucent fill + ring that pops
        # (expand + fade-in) via `fp_phase` then stays as the static residue. A
        # `line` (beam) draws on the canvas (no roster ability uses `line_targets`
        # yet — kept correct, static).
        fp_overlays: list[ft.Control] = []
        if action_shown and step is not None and step.footprints:
            # Join footprints to their cast by id — but only *revealed* casts, so a
            # footprint pops with its cast beat during the intra-tick stagger.
            ability_by_cast = {
                b.cast_id: b.note for b in revealed
                if b.event_type == EVENT_CAST and b.cast_id >= 0
            }
            ph = state["fp_phase"]
            fp_scale = 0.35 + 0.65 * ph
            fp_op = ph
            for i, fp in enumerate(step.footprints):
                if fp.cast_id not in ability_by_cast:
                    continue  # its cast beat hasn't been revealed yet
                aid = ability_by_cast.get(fp.cast_id, "")
                intent = classify_intent(aid) if aid else None
                if intent is not None and intent.kind in ("heal", "buff"):
                    color = SUCCESS  # ally-directed → green halo (T.12c-B)
                else:
                    color = _element_color(aid)
                if fp.kind == "circle":
                    fp_overlays.append(_footprint_circle(fp, color, i, fp_scale, fp_op))
                    if intent is not None and intent.control:
                        # control telegraph: WARNING ring just outside the AoE
                        cx, cy = _cell_xy(fp.center_q, fp.center_r)
                        tpx = _fp_pixel_radius(fp.radius) + 5
                        fp_overlays.append(ft.Container(
                            key=f"fp-tel-{fp.cast_id}-{i}",
                            left=cx - tpx, top=cy - tpx,
                            width=tpx * 2, height=tpx * 2, border_radius=tpx,
                            border=ft.Border.all(2, WARNING), opacity=fp_op,
                            animate_opacity=ft.Animation(_TWEEN_MS, ft.AnimationCurve.EASE_OUT),
                        ))
                elif fp.kind == "line":
                    shapes.extend(_footprint_line(fp, color))

        # T.12c-B intent FX driven by recorded beats (observer-only, V.56): an
        # ally **halo** on each healed target — covers single-target heals, which
        # produce no targeting footprint, so the footprint recolour above never
        # fires for them — and a **status-apply flash** on a piece the moment a
        # status lands (`status` beats are otherwise skipped by the arrow loop).
        # Both read existing heal/status beats; no sim-path change (V.2/V.14).
        # They share the footprint pop phase so Next/autoplay animate them alike.
        if action_shown and step is not None:
            ph = state["fp_phase"]
            fx_scale = 0.35 + 0.65 * ph
            for b in revealed:
                if b.event_type == EVENT_HEAL and b.target_id:
                    tgt = pos_by_id.get(b.target_id)
                    if tgt is None:
                        continue
                    hx, hy = _cell_xy(tgt.q, tgt.r)
                    hr = _TOKEN_R + 7
                    fp_overlays.append(ft.Container(
                        key=f"heal-halo-{b.target_id}",
                        left=hx - hr, top=hy - hr, width=hr * 2, height=hr * 2,
                        border_radius=hr,
                        bgcolor=ft.Colors.with_opacity(0.15, SUCCESS),
                        border=ft.Border.all(2.5, SUCCESS),
                        scale=fx_scale, opacity=ph,
                        animate_scale=ft.Animation(_TWEEN_MS, ft.AnimationCurve.EASE_OUT),
                        animate_opacity=ft.Animation(_TWEEN_MS, ft.AnimationCurve.EASE_OUT),
                    ))
                elif b.event_type == EVENT_STATUS:
                    afflicted = pos_by_id.get(b.actor_id)  # status beat: actor = afflicted
                    if afflicted is None:
                        continue
                    sx, sy = _cell_xy(afflicted.q, afflicted.r)
                    sr = _TOKEN_R + 4
                    scolor = _STATUS_COLORS.get(b.note, WARNING)
                    fp_overlays.append(ft.Container(
                        key=f"stflash-{b.actor_id}-{b.note}",
                        left=sx - sr, top=sy - sr, width=sr * 2, height=sr * 2,
                        border_radius=sr,
                        bgcolor=ft.Colors.with_opacity(0.22, scolor),
                        border=ft.Border.all(2, scolor),
                        scale=fx_scale, opacity=ph,
                        animate_scale=ft.Animation(_TWEEN_MS, ft.AnimationCurve.EASE_OUT),
                        animate_opacity=ft.Animation(_TWEEN_MS, ft.AnimationCurve.EASE_OUT),
                    ))

        for p in pieces:
            if not p.alive:
                continue
            cx, cy = _cell_xy(p.q, p.r)
            ox, oy = lunge.get(p.id, (0.0, 0.0))
            overlays.append(_token(p, cx, cy, ox, oy))
            overlays.append(ft.Container(
                key=f"hp-{p.id}", left=cx - _BAR_W / 2, top=cy + _TOKEN_R + 2,
                content=meter_bar(current=p.hp, maximum=max(1, p.max_hp), height=5, width=_BAR_W),
                animate_position=ft.Animation(_TWEEN_MS, ft.AnimationCurve.EASE_OUT),
            ))
            if p.mana:
                slot = p.mana[0]
                overlays.append(ft.Container(
                    key=f"mp-{p.id}", left=cx - _BAR_W / 2, top=cy + _TOKEN_R + 9,
                    content=_mana_bar(slot.current_mana, slot.mana_cost, slot.max_mana,
                                      width=_BAR_W, height=4),
                    animate_position=ft.Animation(_TWEEN_MS, ft.AnimationCurve.EASE_OUT),
                ))
            pips = _status_pips(p, cx, cy)
            if pips is not None:
                overlays.append(pips)

        # Floating damage / heal numbers for the current step. Monospaced;
        # coloured by damage type (phys red / magic blue / true white / dot
        # purple, heal green); crit = `!` + size bump (not colour). The step's
        # `pre_beats` (DOTs that ticked *between* the previous action and this
        # one) render first — dimmer + stacked higher — so the player reads "these
        # bleeds happened, then this action"; the action `beats` render bright +
        # low. Per-target stagger avoids overlap. (V.57: number from `beat.amount`,
        # bar from the live stepper.)
        # Numbers are OVERLAY controls (added after the tokens) so they render ON
        # TOP — `cv.Text` on the canvas sat *behind* the overlay tokens and got
        # hidden when a piece stood directly above the target.
        numbers: list[ft.Control] = []

        def _emit_number(b: Any, base_rise: int, opacity: float, hit_count: dict[str, int]) -> None:
            tgt = pos_by_id.get(b.target_id or "")
            if tgt is None or not b.amount:
                return
            if b.event_type == EVENT_HEAL:
                txt, base = f"+{b.amount}", SUCCESS
            elif b.event_type in (EVENT_ATTACK, EVENT_ABILITY, EVENT_CAST, EVENT_DOT):
                base = _DMG_COLORS.get(b.note, DANGER)
                txt = f"-{b.amount}" + ("!" if b.is_crit else "")
            else:
                return
            tx, ty = _cell_xy(tgt.q, tgt.r)
            n = hit_count.get(b.target_id, 0)
            hit_count[b.target_id] = n + 1
            numbers.append(ft.Container(
                left=tx - 8 + n * 7, top=ty - _TOKEN_R - 16 - base_rise - n * 14,
                content=ft.Text(
                    txt, size=15 if b.is_crit else 13, weight=ft.FontWeight.BOLD,
                    color=ft.Colors.with_opacity(opacity, base), font_family=FONT_MONO,
                    no_wrap=True,
                ),
            ))

        if step is not None:
            # interstitial DOTs reveal up to `reveal_tick` (a tick cutoff): all
            # DOTs sharing a tick show together, dimmer + stacked higher, as a
            # real-time sequence; the action `beats` show once reveal_tick reaches
            # the action tick.
            pre_hits: dict[str, int] = {}
            shown_pre = [b for b in step.pre_beats if b.tick <= reveal_tick]
            for i, b in enumerate(shown_pre):
                _emit_number(b, base_rise=20 + i * 2, opacity=0.6, hit_count=pre_hits)
            if action_shown:
                act_hits: dict[str, int] = {}
                for b in revealed:
                    _emit_number(b, base_rise=0, opacity=1.0, hit_count=act_hits)

        # canvas (cells/lines/swoosh/beam) behind, footprint AoE shapes next,
        # tokens+bars over them, numbers on top.
        board_stack.controls = [
            cv.Canvas(shapes=shapes, width=_BOARD_W, height=_BOARD_H),
            *fp_overlays, *overlays, *numbers,
        ]

    # ---------- action queue ----------
    def _queue_chip(entry: QueueEntry, active: bool) -> ft.Control:
        """One queue entry. `active` = currently resolving (this step's tick) →
        bigger + accent highlight so the player sees what's being resolved."""
        is_move = entry.is_move
        label = _initials(name_by_id.get(entry.actor_id, entry.actor_id))
        icon = "→" if is_move else ("✦" if entry.kind == EVENT_CAST else "⚔")
        size = (40 if is_move else 52) if active else (34 if is_move else 44)
        return ft.Container(
            width=size, height=size, border_radius=6,
            bgcolor=ft.Colors.with_opacity(0.25, ACCENT) if active
            else (SURFACE_ELEVATED if not is_move else SURFACE),
            border=ft.Border.all(2, ACCENT) if active else None,
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                [ft.Text(icon, size=12 if (active or not is_move) else 10, color=TEXT_PRIMARY if active else TEXT_MUTED),
                 ft.Text(label, size=11 if (active or not is_move) else 9, color=TEXT_PRIMARY)],
                spacing=0, alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True,
            ),
            tooltip=f"{name_by_id.get(entry.actor_id, entry.actor_id)} · {entry.kind} · {_secs(entry.tick)}"
            + (" · resolving now" if active else ""),
            animate_size=ft.Animation(_TWEEN_MS, ft.AnimationCurve.EASE_OUT),
        )

    def _build_queue() -> None:
        now = playback.tick_at(state["cursor"])
        entries = playback.queue(state["cursor"])
        controls: list[ft.Control] = []
        last_round: int | None = None
        sd_marked = False
        for e in entries:
            # sudden-death divider once the queue crosses the threshold
            if not sd_marked and is_sudden_death(e.tick):
                controls.append(ft.Container(
                    width=4, height=48, bgcolor=DANGER, border_radius=2,
                    tooltip="Sudden Death",
                ))
                sd_marked = True
            elif last_round is not None and e.round != last_round:
                controls.append(ft.Container(
                    width=2, height=44, bgcolor=ACCENT,
                    tooltip=f"round {e.round + 1}",
                ))
            controls.append(_queue_chip(e, active=(e.tick == now and state["cursor"] >= 0)))
            last_round = e.round
        if not controls:
            controls = [ft.Text("— no upcoming actions —", size=12, color=TEXT_MUTED)]
        queue_row.controls = controls

    # ---------- inspect panel ----------
    def _stat_row(label: str, value: str, label_w: int = 90) -> ft.Control:
        return ft.Row(
            [ft.Text(label, size=11, color=TEXT_MUTED, width=label_w),
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

            # Two-column stat block: primary (combat) | premium (mr/pen/crit/…).
            def _fmt(key: str) -> str:
                v = pv.stats.get(key, 0.0)
                if key in ("crit_chance", "penetration_pct"):
                    return f"{v * 100:.0f}%"
                return f"{v:.0f}"

            primary = [("STR", "strength"), ("INT", "intelligence"), ("AS", "attack_speed"),
                       ("armor", "armor"), ("res", "resistance"), ("range", "attack_range")]
            premium = [("MS", "move_speed"), ("MR", "mana_regen"), ("crit", "crit_chance"),
                       ("pen", "penetration"), ("pen%", "penetration_pct"), ("threat", "threat")]
            controls.append(ft.Row([
                ft.Column([_stat_row(lbl, _fmt(k), label_w=48) for lbl, k in primary],
                          spacing=SPACING_XS, expand=True),
                ft.Column([_stat_row(lbl, _fmt(k), label_w=48) for lbl, k in premium],
                          spacing=SPACING_XS, expand=True),
            ], spacing=SPACING_SM))
            for i, slot in enumerate(pv.mana):
                controls.append(_stat_row(
                    f"mana[{i}]", f"{slot.current_mana} / {slot.max_mana} (cost {slot.mana_cost})"))
            for st in pv.statuses:
                controls.append(_stat_row(
                    st.status_id, f"x{st.stacks} · {_secs(st.remaining_ticks)}"))
            # Abilities (active + passive) with live-rendered descriptions — for
            # any piece (team or enemy), against its current effective stats.
            abil_ids = abilities_by_id.get(pv.id, [])
            if abil_ids:
                src = _ViewStatSource(pv)
                controls.append(ft.Divider(height=8))
                controls.append(ft.Text("Abilities", size=12, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY))
                for aid in abil_ids:
                    rendered = render_for(aid, src)
                    if rendered is None:
                        continue
                    controls.append(ft.Text(rendered.name, size=11, weight=ft.FontWeight.BOLD, color=ACCENT))
                    controls.append(ft.Text(rendered.text, size=11, color=TEXT_MUTED))
                    if rendered.formula:
                        controls.append(ft.Text(
                            rendered.formula, size=10, color=TEXT_MUTED, font_family=FONT_MONO))
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
        sd = is_sudden_death(tick)
        sudden_death_badge.visible = sd
        board_container.border = ft.Border.all(2, DANGER) if sd else None
        status_text.value = (
            f"tick {tick} ({_secs(tick)}) · round {rnd} · "
            f"step {state['cursor'] + 1}/{playback.step_count()}"
        )
        page.update()

    # ---------- controls / interactions ----------
    def _select(pid: str) -> None:
        state["selected"] = pid
        _render()

    async def _play_step(cursor_at: int, token: int) -> None:
        """Reveal the step's interstitial DOTs (grouped by tick) then its action,
        paced real-time (1s game ≈ 1s real, `playback_delay_s`). Same-tick DOTs
        pop together; aborts if the cursor moved on (token mismatch)."""
        step = playback.steps[cursor_at]
        prev_tick = playback.tick_at(cursor_at - 1) if cursor_at > 0 else 0
        # reveal targets = each distinct pre-beat tick, then the action tick.
        targets = pre_beat_ticks(step)
        if not targets or targets[-1] != step.tick:
            targets = targets + [step.tick]
        for t in targets:
            await asyncio.sleep(playback_delay_s(prev_tick, t))
            if not state["alive"] or state["anim_token"] != token or state["cursor"] != cursor_at:
                return
            state["reveal_tick"] = t
            _render()
            prev_tick = t

    async def _drip_action_beats(cur: int, token: int) -> None:
        """Reveal a step's action beats one at a time in recorded (chronological)
        order — multiple pieces acting on the same tick animate in sequence, not
        all at once — popping each beat's footprint/halo/flash as it lands. The
        full reveal is the static truth `_advance_to` already set, so a rapid Next
        or a cursor move just interrupts (token/cursor guard) and leaves everything
        shown. Used by both manual Next and autoplay so they behave identically."""
        step = playback.steps[cur] if 0 <= cur < playback.step_count() else None
        if step is None:
            return
        total = len(step.beats)
        for n in range(1, total + 1):
            if not state["alive"] or state["anim_token"] != token or state["cursor"] != cur:
                return
            state["reveal_n"] = n
            state["fp_phase"] = 0.0  # seed the just-revealed beat's shape pop
            _render()
            await asyncio.sleep(0.03)  # let the seed frame paint before growing
            if not state["alive"] or state["anim_token"] != token or state["cursor"] != cur:
                return
            state["fp_phase"] = 1.0
            _render()
            if n < total:
                await asyncio.sleep(_BEAT_STAGGER_S)  # gap before the next beat

    def _step(delta: int) -> None:
        # Forward Next animates the landed tick's action beats in recorded order
        # (intra-tick stagger) so a multi-piece tick reads move→attack→… in
        # sequence, each beat's footprint/halo/flash popping as it lands. Backward /
        # seek shows the full static truth at once. Interrupt-safe via anim_token —
        # a rapid Next aborts the drip and the next advance shows everything.
        _advance_to(state["cursor"] + delta)
        cur = state["cursor"]
        if delta > 0 and cur >= 0:
            token = state["anim_token"]
            state["reveal_n"] = 0  # seed: nothing yet; drip reveals beats in order
            _render()
            page.run_task(_drip_action_beats, cur, token)
        else:
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
        # Real-time autoplay (1s ≈ 1s) on the flet event loop (`page.run_task`):
        # advance one step, drip its DOTs + action paced by the tick gap.
        while state["alive"] and state["playing"]:
            if state["cursor"] >= _last_cursor():
                state["playing"] = False
                autoplay_btn.text = "▶ Autoplay"
                _render()
                break
            _advance_to(state["cursor"] + 1)
            cur = state["cursor"]
            token = state["anim_token"]
            state["reveal_tick"] = -1
            state["fp_phase"] = 0.0  # seed the footprint pop; grows after reveal
            _render()
            await _play_step(cur, token)
            if state["anim_token"] != token:  # user interrupted mid-step
                break
            # `_play_step` reveals the action at `reveal_tick == step.tick`; `reveal_n`
            # stays at the step's full beat count (set by `_advance_to`), so autoplay
            # shows the tick's beats together and the FX linger. Pop the shapes/halos.
            # NOTE: the intra-tick **stagger is a manual-Next affordance only**;
            # staggered autoplay is deferred polish (SPEC §T.12c / §D.28) — gating
            # autoplay's beats behind the drip made single-beat steps flash sub-frame
            # ("no animations"). Manual Next keeps the in-order reveal.
            if playback.steps[cur].footprints or any(
                b.event_type in (EVENT_HEAL, EVENT_STATUS)
                for b in playback.steps[cur].beats
            ):
                state["fp_phase"] = 1.0
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
        ft.Container(width=SPACING_MD),
        sudden_death_badge,
        ft.Container(expand=True),
        status_text,
    ])

    def _legend_dot(color: str, label: str) -> ft.Control:
        return ft.Row(
            [ft.Container(width=10, height=10, bgcolor=color, border_radius=5),
             ft.Text(label, size=10, color=TEXT_MUTED)],
            spacing=4, tight=True,
        )

    legend = ft.Column([
        ft.Row([
            _legend_dot(DANGER, "Phys"), _legend_dot(ACCENT, "Magic"),
            _legend_dot(TEXT_PRIMARY, "True"), _legend_dot(DOT_DAMAGE, "DoT"),
            _legend_dot(SUCCESS, "Heal"),
        ], spacing=SPACING_MD, wrap=True),
        ft.Text("→/↵ Next · ← Prev · Space play · F end · R restart · Esc exit",
                size=10, color=TEXT_MUTED),
    ], spacing=SPACING_XS, width=_BOARD_W)

    left = ft.Column([
        queue_row,
        board_container,
        controls_row,
        legend,
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

    def _on_key(e: ft.KeyboardEvent) -> None:
        if not state["alive"]:
            return
        k = e.key
        if k in ("Arrow Right", "Enter"):
            _step(1)
        elif k == "Arrow Left":
            _step(-1)
        elif k in (" ", "Space"):
            _toggle_autoplay(None)
        elif k == "F":
            _fast_forward()
        elif k == "R":
            _restart()
        elif k == "Escape":
            on_exit()

    def _on_pop(_e: Any) -> None:
        state["alive"] = False
        state["playing"] = False
        page.on_keyboard_event = None

    view = ft.View(route="/combat", controls=[root], padding=0)
    view.data = _on_pop  # harness wires this into page.on_view_pop
    page.on_keyboard_event = _on_key

    # initial paint
    _advance_to(-1)
    _render()
    return view
