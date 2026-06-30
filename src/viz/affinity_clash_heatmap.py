"""Affinity-Clash heatmap viz — the per-hit damage triangle as a colored matrix.

Shows :func:`weather_effects.damage_modifier` for every (attacker-affinity,
defender-affinity) pair as one colored cell: **green** = you deal *more* (favor,
``>1.0``), **gray** = neutral (``1.0``), **red** = you deal *less* (clash,
``<1.0``). Rows are the attacker's affinity, columns the defender's.

Two layers, mirroring :mod:`src.viz.route_map` / :mod:`src.viz.run_summary`:

- **Pure data** — :func:`clash_matrix_specs` builds a grid of
  :class:`ClashCellSpec`. Flet-free + test-asserted. Each cell reads its number
  straight from ``damage_modifier`` (the *same* function the combat engine calls
  per hit), so the heatmap **cannot drift** from real combat — source-of-truth,
  mirroring the V.38 tooltip contract.
- **Builder** — :func:`build_affinity_clash_heatmap` lays the specs out as a grid
  of colored ``ft.Container`` cells (a heatmap reads as boxes, not a hand-drawn
  ``flet.canvas`` chart — V.72's canvas rule targets the Flet-removed bar/line/pie
  widgets, which this is not). Pure presentation, no game state (V.1/V.63).
"""

from __future__ import annotations

from dataclasses import dataclass

import flet as ft

from src.game.models import WeatherState
from src.game.weather_effects import RingRelation, damage_modifier, ring_relation
from src.ui.components.iconography import affinity_marker, rich_tooltip
from src.ui.theme import (
    ACCENT,
    CARD_RADIUS,
    DANGER,
    FONT_SIZE_CAPTION,
    SPACING_SM,
    SPACING_XS,
    SUCCESS,
    SURFACE,
    SURFACE_ELEVATED,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

# Display order: the predator/prey ring (each row is a rotation, giving a clean
# diagonal of 1.0s), with the inert CLEAR appended last.
AXIS_ORDER: tuple[WeatherState, ...] = (
    WeatherState.MIST,
    WeatherState.CLOUDY,
    WeatherState.RAIN,
    WeatherState.SNOW,
    WeatherState.THUNDER,
    WeatherState.CLEAR,
)

# Cell tint strength per ring relation — primary matchups read stronger than
# secondary; the two `1.0` relations (SELF / NEUTRAL) carry no tone.
_CELL_OPACITY: dict[RingRelation, float] = {
    RingRelation.PRIMARY_PREDATOR: 0.55,
    RingRelation.SECONDARY_PREDATOR: 0.26,
    RingRelation.SECONDARY_PREY: 0.26,
    RingRelation.PRIMARY_PREY: 0.55,
}

# Cell tone follows the *multiplier* (the user-facing semantic: green >1, gray =1,
# red <1) — NOT the ring relation. A SELF matchup is on the buff side of the ring
# but deals ×1.0, so it must read neutral, not green.
_CATEGORY_TONE: dict[str, str] = {
    "favor": SUCCESS,
    "neutral": TEXT_MUTED,
    "clash": DANGER,
}

# Geometry (px).
_CELL_W = 42
_CELL_H = 30
_HEAD_W = 46


@dataclass(frozen=True, slots=True)
class ClashCellSpec:
    """One (attacker, defender) cell — pure data (no Flet), asserted by tests.

    ``mult`` is read from :func:`damage_modifier` so it equals the live combat
    multiplier. ``tone`` is the semantic color (green favor / red clash / muted
    neutral) and ``category`` classifies the cell for legend + tests.
    """

    attacker: WeatherState
    defender: WeatherState
    mult: float
    relation: RingRelation
    tone: str
    category: str  # "favor" (>1) | "neutral" (==1) | "clash" (<1)


def _category(mult: float) -> str:
    if mult > 1.0:
        return "favor"
    if mult < 1.0:
        return "clash"
    return "neutral"


def clash_matrix_specs(
    order: tuple[WeatherState, ...] = AXIS_ORDER,
) -> list[list[ClashCellSpec]]:
    """Build the attacker×defender clash grid (rows = attacker, cols = defender).

    Each cell's ``mult`` comes from :func:`damage_modifier` — the exact per-hit
    multiplier the engine applies — so this viz is a faithful read of the live
    rule, never a re-typed copy. Pure + deterministic (V.2), Flet-free.
    """
    grid: list[list[ClashCellSpec]] = []
    for attacker in order:
        row: list[ClashCellSpec] = []
        for defender in order:
            mult = damage_modifier(attacker, defender)
            relation = ring_relation(attacker, defender)
            category = _category(mult)
            row.append(
                ClashCellSpec(
                    attacker=attacker,
                    defender=defender,
                    mult=mult,
                    relation=relation,
                    tone=_CATEGORY_TONE[category],
                    category=category,
                )
            )
        grid.append(row)
    return grid


def _abbrev(affinity: WeatherState) -> str:
    """3-letter axis label (``MIST`` → ``MIS``)."""
    return affinity.value[:3].upper()


def _cell_bg(spec: ClashCellSpec) -> str:
    """A tone-tinted background by relation strength; flat surface for neutral."""
    opacity = _CELL_OPACITY.get(spec.relation)
    if opacity is None:  # SELF / NEUTRAL → no favor either way
        return SURFACE_ELEVATED
    return ft.Colors.with_opacity(opacity, spec.tone)


def _header_cell(affinity: WeatherState, *, highlighted: bool) -> ft.Control:
    """An axis header — affinity glyph + 3-letter label, tooltipped by name."""
    return ft.Container(
        ft.Column(
            [
                affinity_marker(affinity, size=15),
                ft.Text(
                    _abbrev(affinity),
                    size=9,
                    color=ACCENT if highlighted else TEXT_MUTED,
                    weight=ft.FontWeight.BOLD,
                ),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        ),
        width=_CELL_W,
        height=_HEAD_W,
        alignment=ft.Alignment.CENTER,
        tooltip=affinity.value.capitalize(),
    )


def _data_cell(spec: ClashCellSpec) -> ft.Control:
    rel_label = spec.relation.value.replace("_", " ")
    tip = (
        f"{spec.attacker.value.capitalize()} attacking "
        f"{spec.defender.value.capitalize()}\n"
        f"×{spec.mult:.2f} damage · {rel_label}"
    )
    return ft.Container(
        ft.Text(f"{spec.mult:.2f}", size=11, color=TEXT_PRIMARY,
                weight=ft.FontWeight.BOLD),
        width=_CELL_W,
        height=_CELL_H,
        alignment=ft.Alignment.CENTER,
        bgcolor=_cell_bg(spec),
        border_radius=4,
        tooltip=rich_tooltip(tip, tone=spec.tone),
    )


def _legend() -> ft.Control:
    def _swatch(color: str, label: str) -> ft.Control:
        return ft.Row(
            [
                ft.Container(width=12, height=12, border_radius=3,
                             bgcolor=ft.Colors.with_opacity(0.55, color)
                             if color != TEXT_MUTED else SURFACE_ELEVATED),
                ft.Text(label, size=9, color=TEXT_MUTED),
            ],
            spacing=4, tight=True,
        )

    return ft.Row(
        [
            _swatch(SUCCESS, ">1 you deal more"),
            _swatch(TEXT_MUTED, "=1 neutral"),
            _swatch(DANGER, "<1 you deal less"),
        ],
        spacing=SPACING_SM, wrap=True, run_spacing=4,
    )


def build_affinity_clash_heatmap(
    *,
    highlight: set[WeatherState] | None = None,
    order: tuple[WeatherState, ...] = AXIS_ORDER,
) -> ft.Control:
    """Render the Affinity-Clash matrix as a colored cell grid.

    ``highlight`` (e.g. the player's team affinities) accents the matching
    **attacker rows** so the player reads their own damage stakes at a glance.
    Pure presentation over :func:`clash_matrix_specs` — recomputes nothing (V.63).
    """
    hi = highlight or set()
    grid = clash_matrix_specs(order)

    # Header row: a corner axis-key cell, then a glyph header per defender.
    corner = ft.Container(
        ft.Text("atk ╲ def", size=9, color=TEXT_MUTED, text_align=ft.TextAlign.CENTER),
        width=_HEAD_W, height=_HEAD_W, alignment=ft.Alignment.CENTER,
    )
    header = ft.Row(
        [corner] + [_header_cell(d, highlighted=d in hi) for d in order],
        spacing=2,
    )

    rows: list[ft.Control] = [header]
    for attacker, spec_row in zip(order, grid):
        mine = attacker in hi
        row_head = ft.Container(
            ft.Row(
                [
                    affinity_marker(attacker, size=15),
                    ft.Text(_abbrev(attacker), size=9,
                            color=ACCENT if mine else TEXT_MUTED,
                            weight=ft.FontWeight.BOLD),
                    *([ft.Text("◀", size=8, color=ACCENT)] if mine else []),
                ],
                spacing=2, tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            width=_HEAD_W, height=_CELL_H, alignment=ft.Alignment.CENTER_LEFT,
            tooltip=(f"{attacker.value.capitalize()} — your team"
                     if mine else attacker.value.capitalize()),
        )
        rows.append(ft.Row([row_head] + [_data_cell(s) for s in spec_row], spacing=2))

    title = ft.Text("Affinity Clash — damage you deal", size=FONT_SIZE_CAPTION,
                    color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
    subtitle = ft.Text("row affinity attacks column affinity", size=9, color=TEXT_MUTED)

    return ft.Column(
        [
            title,
            subtitle,
            # The grid is wider than a side rail; let it scroll horizontally as a
            # unit (the column of rows scrolls left↔right inside the panel).
            ft.Container(
                ft.Row([ft.Column(rows, spacing=2, tight=True)],
                       scroll=ft.ScrollMode.AUTO),
                bgcolor=SURFACE, border_radius=CARD_RADIUS, padding=SPACING_SM,
            ),
            _legend(),
        ],
        spacing=SPACING_XS,
    )
