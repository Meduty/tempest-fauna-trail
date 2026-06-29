"""Shared champion-infocard core (T.12d_a, V.82) — the identity header + stat grid
+ ability blurbs that **both** the Prep sheet and the Combat inspect panel render
through, so the two can never re-drift (the old combat panel was a thinner inline
copy — no role/trait glyphs, no inline effect icons).

Pure presentation (V.1): imports `game/` enums + the ability render-layer, never
combat math, never mutates `game/` state. Each view wraps this core with its own
extras — Prep adds the copy-level line / interactive item chips / shop-preview Buy;
Combat adds live current-HP/barrier/per-slot-mana/status rows. The genuinely
identical surface (who is this · what are its stats · what does it do) is the core.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import flet as ft

from src.game.ability_text import render_for
from src.game.models import WeatherState
from src.ui.components.iconography import (
    affinity_marker,
    inline_effect_text,
    role_glyph,
    stat_glyph,
    trait_glyph,
)
from src.ui.theme import (
    ACCENT,
    AFFINITY_COLORS,
    FONT_MONO,
    FONT_SIZE_CAPTION,
    FONT_SIZE_H3,
    SPACING_SM,
    SPACING_XS,
    TEXT_MUTED,
    TEXT_PRIMARY,
)


@dataclass(frozen=True, slots=True)
class PieceInfo:
    """Normalized infocard input — built by each view from its own model
    (`Champion` in Prep, `PieceView` in Combat) so the core never imports either.

    `primary_stats`/`premium_stats` are pre-formatted `(label, value)` rows in
    display order (each view chooses which stats it surfaces). `stat_src` exposes
    `.stat(name)` for `render_for` (a `Champion` per V.38, or the combat view's
    `_ViewStatSource`)."""

    name: str
    affinity: WeatherState
    role: str
    traits: tuple[str, ...]
    primary_stats: tuple[tuple[str, str], ...]
    premium_stats: tuple[tuple[str, str], ...]
    actives: tuple[str, ...]
    passive: str
    stat_src: Any
    subtitle: str


def _icon_cluster(info: PieceInfo) -> ft.Control:
    """Top-right identity glyphs: the affinity glyph (in its affinity colour) +
    one glyph per trait, each tooltipped by name (the old Prep `_piece_icon_cluster`)."""
    aff = affinity_marker(info.affinity, size=18)
    aff.tooltip = info.affinity.value.capitalize()
    glyphs: list[ft.Control] = [aff]
    for t in info.traits:
        g = trait_glyph(t, size=16, color=TEXT_PRIMARY)
        g.tooltip = t
        glyphs.append(g)
    return ft.Row(glyphs, spacing=SPACING_XS, tight=True, wrap=False)


def infocard_header(info: PieceInfo) -> ft.Control:
    """Identity header: role glyph + affinity-coloured name + affinity/trait
    cluster, with a muted subtitle line underneath."""
    color = AFFINITY_COLORS.get(info.affinity, TEXT_PRIMARY)
    name_row: list[ft.Control] = [
        ft.Text(info.name, size=FONT_SIZE_H3, color=color,
                weight=ft.FontWeight.BOLD, expand=True),
        _icon_cluster(info),
    ]
    role_ic = role_glyph(info.role, size=16, color=color)
    if role_ic is not None:
        name_row.insert(0, role_ic)
    return ft.Column([
        ft.Row(name_row, spacing=SPACING_XS,
               vertical_alignment=ft.CrossAxisAlignment.START),
        ft.Text(info.subtitle, size=FONT_SIZE_CAPTION, color=TEXT_MUTED),
    ], spacing=2, tight=True)


def _stat_row(label: str, value: str) -> ft.Control:
    glyph = stat_glyph(label, size=12)
    icon_cell: ft.Control = glyph if glyph is not None else ft.Container(width=12)
    return ft.Row(
        [icon_cell,
         ft.Text(label, size=11, color=TEXT_MUTED, width=50),
         ft.Text(value, size=11, color=TEXT_PRIMARY)],
        spacing=SPACING_XS,
    )


def infocard_stat_grid(info: PieceInfo) -> ft.Control:
    """Two-column stat grid: each row is a stat glyph + label + value."""
    return ft.Row([
        ft.Column([_stat_row(lbl, v) for lbl, v in info.primary_stats],
                  spacing=2, expand=True),
        ft.Column([_stat_row(lbl, v) for lbl, v in info.premium_stats],
                  spacing=2, expand=True),
    ], spacing=SPACING_SM)


def infocard_abilities(info: PieceInfo) -> list[ft.Control]:
    """Actives + passive, each rendered name + blurb (with inline effect glyphs)
    + formula. Blurbs route through `render_for(stat_src)` (V.38) so the numbers
    scale to the source (Champion level in Prep, live effective stats in Combat)."""
    out: list[ft.Control] = []
    for header, ids in (("Actives", list(info.actives)),
                        ("Passive", [info.passive])):
        ids = [a for a in ids if a]
        if not ids:
            continue
        out.append(ft.Text(header, size=11, color=TEXT_MUTED, weight=ft.FontWeight.BOLD))
        for aid in ids:
            rendered = render_for(aid, info.stat_src)
            if rendered is None:
                out.append(ft.Text(f"• {aid}", size=11, color=TEXT_MUTED))
                continue
            out.append(ft.Text(rendered.name, size=11, color=ACCENT,
                               weight=ft.FontWeight.BOLD))
            out.append(inline_effect_text(rendered.text, size=11, color=TEXT_PRIMARY))
            if rendered.formula:
                out.append(ft.Text(rendered.formula, size=10, color=TEXT_MUTED,
                                   font_family=FONT_MONO))
    return out
