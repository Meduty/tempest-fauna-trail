"""ChampionCard component."""

from __future__ import annotations

from typing import Callable

import flet as ft

from src.game.models import WeatherState
from src.ui.theme import (
    ACCENT,
    AFFINITY_COLORS,
    ANIM_FAST,
    CARD_RADIUS,
    DANGER,
    FONT_MONO,
    FONT_SIZE_BODY,
    FONT_SIZE_CAPTION,
    FONT_SIZE_H2,
    FONT_SIZE_MONO,
    SPACING_SM,
    SPACING_XS,
    SURFACE,
    SURFACE_ELEVATED,
    TEXT_MUTED,
    TEXT_PRIMARY,
    WARNING,
)
from src.ui.components.chips import affinity_chip, trait_chip
from src.ui.components.meter_bar import meter_bar


# Card width constant
_CARD_WIDTH = 200

# State-driven styling
_STATE_STYLES: dict[str, dict] = {
    "idle": {"opacity": 1.0, "border_color": None, "overlay_color": None},
    "selected": {"opacity": 1.0, "border_color": ACCENT, "overlay_color": None},
    "disabled": {"opacity": 0.5, "border_color": None, "overlay_color": None},
    "dead": {"opacity": 0.7, "border_color": DANGER, "overlay_color": DANGER},
    "low_hp": {"opacity": 1.0, "border_color": WARNING, "overlay_color": None},
}


def champion_card(
    *,
    name: str,
    affinity: WeatherState,
    traits: list[str],
    role: str,
    tier: int,
    level: int,
    max_hp: int,
    hp: int | None = None,
    stats: dict[str, int | float],
    state: str = "idle",
    on_click: Callable | None = None,
) -> ft.Container:
    """Build a champion card with inline chips and optional HP bar.

    Args:
        name: Champion display name.
        affinity: WeatherState affinity for coloring.
        traits: List of trait tag strings.
        role: Champion role (e.g. "melee", "ranged").
        tier: Champion tier (1-10).
        level: Champion level (1-3).
        max_hp: Maximum hit points.
        hp: Current HP; None means full HP (recruit/prep idle display).
        stats: Dict of stat name → value for display.
        state: Visual state: idle | selected | disabled | dead | low_hp.
        on_click: Optional click handler.
    """
    style = _STATE_STYLES.get(state, _STATE_STYLES["idle"])

    # Header: name + tier/level
    header = ft.Row(
        controls=[
            ft.Text(
                name,
                size=FONT_SIZE_H2,
                color=TEXT_PRIMARY,
                weight=ft.FontWeight.BOLD,
                expand=True,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            ft.Text(
                f"T{tier}·L{level}",
                size=FONT_SIZE_CAPTION,
                color=TEXT_MUTED,
                font_family=FONT_MONO,
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    # Role + Affinity chip row
    chip_row = ft.Row(
        controls=[
            ft.Text(role.capitalize(), size=FONT_SIZE_CAPTION, color=TEXT_MUTED),
            affinity_chip(affinity=affinity, size="sm"),
        ],
        spacing=SPACING_SM,
    )

    # Trait chips
    trait_row = ft.Row(
        controls=[trait_chip(label=t, size="sm") for t in traits],
        spacing=SPACING_XS,
        wrap=True,
    )

    # Stats
    stat_controls: list[ft.Control] = []
    for stat_name, stat_val in stats.items():
        abbr = stat_name[:3].upper()
        stat_controls.append(
            ft.Text(
                f"{abbr}:{stat_val}",
                size=FONT_SIZE_MONO,
                font_family=FONT_MONO,
                color=TEXT_MUTED,
            )
        )
    stats_row = ft.Row(controls=stat_controls, spacing=SPACING_XS, wrap=True)

    # HP bar (only when hp is provided)
    hp_section: list[ft.Control] = []
    if hp is not None:
        hp_section.append(meter_bar(current=hp, maximum=max_hp, height=6))

    # Assemble card content
    card_content = ft.Column(
        controls=[header, chip_row, trait_row, stats_row, *hp_section],
        spacing=SPACING_SM,
    )

    # Border
    border = None
    if style["border_color"]:
        side = ft.BorderSide(2, style["border_color"])
        border = ft.Border(top=side, right=side, bottom=side, left=side)

    return ft.Container(
        content=card_content,
        width=_CARD_WIDTH,
        bgcolor=SURFACE,
        border_radius=CARD_RADIUS,
        border=border,
        padding=ft.Padding(
            left=SPACING_SM, right=SPACING_SM,
            top=SPACING_SM, bottom=SPACING_SM,
        ),
        opacity=style["opacity"],
        animate_opacity=ft.Animation(ANIM_FAST, ft.AnimationCurve.EASE_OUT),
        on_click=on_click if state != "disabled" else None,
    )
