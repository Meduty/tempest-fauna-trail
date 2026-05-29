"""HPBar / ManaBar — shared meter_bar component."""

from __future__ import annotations

import flet as ft

from src.ui.theme import (
    ANIM_COMBAT_TICK,
    DANGER,
    SUCCESS,
    SURFACE_ELEVATED,
    WARNING,
)


def meter_bar(
    *,
    current: int | float,
    maximum: int | float,
    color: str = SUCCESS,
    warn_color: str = WARNING,
    danger_color: str = DANGER,
    warn_threshold: float = 0.5,
    danger_threshold: float = 0.25,
    height: int = 6,
    width: int | None = None,
    animate: bool = True,
) -> ft.Container:
    """A horizontal meter bar with threshold-based color changes.

    Returns an ft.Container with a filled inner bar proportional to current/maximum.
    """
    ratio = max(0.0, min(1.0, current / maximum)) if maximum > 0 else 0.0

    # Determine fill color based on thresholds
    if ratio <= danger_threshold:
        fill_color = danger_color
    elif ratio <= warn_threshold:
        fill_color = warn_color
    else:
        fill_color = color

    fill_width = ratio  # Used as fraction for expand-based layout

    inner_bar = ft.Container(
        bgcolor=fill_color,
        border_radius=height // 2,
        height=height,
        expand=True,
        animate=ft.Animation(ANIM_COMBAT_TICK, ft.AnimationCurve.LINEAR)
        if animate
        else None,
    )

    # Wrap in a row to control proportional fill
    bar_content = ft.Row(
        controls=[
            ft.Container(
                content=inner_bar,
                expand=int(max(1, round(ratio * 100))),
            ),
            ft.Container(expand=int(max(1, round((1 - ratio) * 100)))),
        ],
        spacing=0,
        tight=True,
    )

    return ft.Container(
        content=bar_content,
        bgcolor=SURFACE_ELEVATED,
        border_radius=height // 2,
        height=height,
        width=width,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
    )
