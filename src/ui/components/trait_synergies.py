"""Shared trait-synergy panel (TFT-style) — used by Prep and Combat (V.1, no
combat math here). Renders a `TraitPreview` list so **active** synergies (≥1
breakpoint cleared) read prominently and **dormant** ones (carried but below the
first rung) are greyed, with the full rung ladder shown as pips that light as
breakpoints clear.

This is the presentation half only: the breakpoint *effect text* (what each rung
grants) is the planned shared render-layer (B) — not authored here. Tooltips show
the numeric ladder, mirroring TFT's "you have N, next rung at M".
"""

from __future__ import annotations

import flet as ft

from src.game.describe import render_trait
from src.game.traits import TraitPreview
from src.ui.theme import (
    CARD_RADIUS,
    FONT_SIZE_H3,
    SPACING_XS,
    SUCCESS,
    SURFACE,
    SURFACE_ELEVATED,
    TEXT_MUTED,
    TEXT_PRIMARY,
)


def _rung_pip(value: int, *, lit: bool) -> ft.Control:
    """One breakpoint pip — lit (cleared) shows filled accent, else a grey outline."""
    return ft.Container(
        ft.Text(str(value), size=9,
                color=SURFACE if lit else TEXT_MUTED,
                weight=ft.FontWeight.BOLD),
        width=16, height=16, border_radius=8,
        alignment=ft.Alignment.CENTER,
        bgcolor=SUCCESS if lit else None,
        border=None if lit else ft.Border.all(1, SURFACE_ELEVATED),
    )


def _trait_tooltip(tp: TraitPreview) -> str:
    """Rich tooltip: trait blurb + every breakpoint's effect text + derived stat
    line (T.41b `describe.render_trait`), cleared rungs marked ●. Falls back to a
    numeric line if the trait has no metadata."""
    rt = render_trait(tp.trait)
    if rt is None:
        if tp.next_threshold is not None:
            return f"{tp.trait}: {tp.count} carriers · next rung at {tp.next_threshold}"
        return f"{tp.trait}: {tp.count} carriers · top rung cleared"
    lines = [f"{rt.name} — {rt.blurb}", f"Carriers: {tp.count}"]
    for r in rt.rungs:
        # Cleared if an int rung the count reached; the dynamic apex ("full") is
        # marked cleared only when the top rung is reached (next_threshold is None).
        cleared = (tp.count >= r.count) if isinstance(r.count, int) else (
            tp.active and tp.next_threshold is None
        )
        mark = "●" if cleared else "○"
        stat = f" {r.stat_line}" if r.stat_line else ""
        # Scope says who it hits: carriers (tag-sharers) vs the whole team.
        lines.append(f"{mark} @{r.count} [{r.scope}]{stat} — {r.text}")
    return "\n".join(lines)


def _trait_row(tp: TraitPreview) -> ft.Control:
    """One trait: name + count badge + rung-ladder pips. Active = bright + a SUCCESS
    rail; dormant = greyed."""
    active = tp.active
    name_color = TEXT_PRIMARY if active else TEXT_MUTED
    # Ladder pips (fall back to the cleared/next pair if no full ladder present).
    rungs = tp.thresholds or tuple(
        t for t in (tp.threshold, tp.next_threshold) if t
    )
    pips = [_rung_pip(t, lit=tp.count >= t) for t in rungs]
    tip = _trait_tooltip(tp)

    header = ft.Row([
        ft.Container(width=6, height=6, border_radius=3,
                     bgcolor=SUCCESS if active else SURFACE_ELEVATED),
        ft.Text(tp.trait, size=12, no_wrap=True, expand=True,
                color=name_color,
                weight=ft.FontWeight.BOLD if active else ft.FontWeight.W_400),
        ft.Text(str(tp.count), size=12, color=SUCCESS if active else TEXT_MUTED,
                weight=ft.FontWeight.BOLD),
    ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    return ft.Container(
        ft.Column([
            header,
            ft.Row(pips, spacing=4, wrap=True, run_spacing=4),
        ], spacing=4),
        bgcolor=SURFACE_ELEVATED if active else None,
        border=ft.Border(left=ft.BorderSide(2, SUCCESS)) if active else None,
        border_radius=CARD_RADIUS,
        padding=ft.Padding(left=8, right=8, top=5, bottom=5),
        opacity=1.0 if active else 0.6,
        tooltip=tip,
    )


def trait_synergies_panel(
    previews: list[TraitPreview],
    *,
    title: str = "Traits",
    empty_hint: str = "Place units to see synergies.",
) -> ft.Control:
    """Build the TFT-style trait panel. ``previews`` come from
    ``traits.preview_team_traits`` (already sorted active-first)."""
    rows: list[ft.Control] = [
        ft.Text(title, size=FONT_SIZE_H3, color=TEXT_PRIMARY,
                weight=ft.FontWeight.BOLD),
    ]
    if not previews:
        rows.append(ft.Text(empty_hint, size=12, color=TEXT_MUTED))
    else:
        active = [p for p in previews if p.active]
        dormant = [p for p in previews if not p.active]
        rows.extend(_trait_row(p) for p in active)
        if active and dormant:
            rows.append(ft.Text("Dormant", size=10, color=TEXT_MUTED))
        rows.extend(_trait_row(p) for p in dormant)
    return ft.Column(rows, spacing=SPACING_XS)
