"""AffinityChip and TraitChip components."""

from __future__ import annotations

import flet as ft

from src.game.models import WeatherState
from src.ui.theme import (
    AFFINITY_COLORS,
    BG,
    CHIP_RADIUS,
    FONT_SIZE_CAPTION,
    FONT_SIZE_BODY,
    SPACING_XS,
    SPACING_SM,
    SURFACE_ELEVATED,
    TEXT_MUTED,
)

_CHIP_SIZES = {
    "sm": {"font_size": FONT_SIZE_CAPTION, "h_pad": SPACING_SM, "v_pad": SPACING_XS},
    "md": {"font_size": FONT_SIZE_BODY, "h_pad": SPACING_SM + 2, "v_pad": SPACING_XS + 2},
}


def affinity_chip(
    *,
    affinity: WeatherState,
    size: str = "sm",
) -> ft.Container:
    """Small colored pill showing the affinity name on its AFFINITY_COLORS background."""
    cfg = _CHIP_SIZES.get(size, _CHIP_SIZES["sm"])
    color = AFFINITY_COLORS[affinity]
    return ft.Container(
        content=ft.Text(
            affinity.value.capitalize(),
            size=cfg["font_size"],
            color=BG,
            weight=ft.FontWeight.W_500,
        ),
        bgcolor=color,
        border_radius=CHIP_RADIUS,
        padding=ft.Padding(
            left=cfg["h_pad"], right=cfg["h_pad"],
            top=cfg["v_pad"], bottom=cfg["v_pad"],
        ),
    )


def trait_chip(
    *,
    label: str,
    size: str = "sm",
) -> ft.Container:
    """Neutral-colored pill for synergy trait tags."""
    cfg = _CHIP_SIZES.get(size, _CHIP_SIZES["sm"])
    return ft.Container(
        content=ft.Text(
            label,
            size=cfg["font_size"],
            color=TEXT_MUTED,
            weight=ft.FontWeight.W_400,
        ),
        bgcolor=SURFACE_ELEVATED,
        border_radius=CHIP_RADIUS,
        padding=ft.Padding(
            left=cfg["h_pad"], right=cfg["h_pad"],
            top=cfg["v_pad"], bottom=cfg["v_pad"],
        ),
    )
