"""WeatherBadge component."""

from __future__ import annotations

import time

import flet as ft

from src.game.models import WeatherState
from src.game.weather_effects import WEATHER_BUFF_BASE, WEATHER_DEBUFF_BASE
from src.ui.theme import (
    AFFINITY_COLORS,
    CARD_RADIUS,
    FONT_SIZE_BODY,
    FONT_SIZE_CAPTION,
    FONT_SIZE_H2,
    SPACING_SM,
    SPACING_XS,
    SURFACE,
    TEXT_PRIMARY,
    WARNING,
)

# Staleness threshold: 2 hours (per §V.11 / D.17)
_STALE_THRESHOLD_S = 2 * 60 * 60

# Weather icon fallback glyphs
_WEATHER_ICONS: dict[WeatherState, str] = {
    WeatherState.CLEAR: ft.Icons.WB_SUNNY,
    WeatherState.CLOUDY: ft.Icons.CLOUD,
    WeatherState.MIST: ft.Icons.BLUR_ON,
    WeatherState.RAIN: ft.Icons.WATER_DROP,
    WeatherState.SNOW: ft.Icons.AC_UNIT,
    WeatherState.THUNDER: ft.Icons.FLASH_ON,
}

_BADGE_SIZES = {
    "sm": {"icon_size": 16, "font_size": FONT_SIZE_CAPTION, "padding": SPACING_XS},
    "md": {"icon_size": 24, "font_size": FONT_SIZE_BODY, "padding": SPACING_SM},
    "lg": {"icon_size": 32, "font_size": FONT_SIZE_H2, "padding": SPACING_SM + 4},
}


def _build_tooltip(weather: WeatherState) -> str:
    """Build tooltip describing weather buff/debuff effects."""
    buff = WEATHER_BUFF_BASE.get(weather)
    debuff = WEATHER_DEBUFF_BASE.get(weather)

    # Describe non-identity modifiers
    buff_parts: list[str] = []
    debuff_parts: list[str] = []

    if buff:
        for field_name in [
            "hp_mult", "str_mult", "int_mult", "as_mult",
            "ms_mult", "mr_mult", "thr_mult", "armor_mult", "res_mult",
        ]:
            val = getattr(buff, field_name, 1.0)
            if val != 1.0:
                stat = field_name.replace("_mult", "").upper()
                pct = round((val - 1.0) * 100)
                buff_parts.append(f"+{pct}% {stat}" if pct > 0 else f"{pct}% {stat}")
        if buff.attack_range_delta != 0:
            buff_parts.append(f"+{buff.attack_range_delta} RNG")

    if debuff:
        for field_name in [
            "hp_mult", "str_mult", "int_mult", "as_mult",
            "ms_mult", "mr_mult", "thr_mult", "armor_mult", "res_mult",
        ]:
            val = getattr(debuff, field_name, 1.0)
            if val != 1.0:
                stat = field_name.replace("_mult", "").upper()
                pct = round((val - 1.0) * 100)
                debuff_parts.append(f"{pct}% {stat}")
        if debuff.attack_range_delta != 0:
            debuff_parts.append(f"{debuff.attack_range_delta} RNG")

    lines = [f"{weather.value.capitalize()} Favor:"]
    if buff_parts:
        lines.append(f"  Buff: {', '.join(buff_parts)}")
    if debuff_parts:
        lines.append(f"  Debuff: {', '.join(debuff_parts)}")
    if not buff_parts and not debuff_parts:
        lines.append("  No modifier (neutral)")
    return "\n".join(lines)


def weather_badge(
    *,
    weather: WeatherState,
    show_icon: bool = True,
    icon_code: str | None = None,
    show_label: bool = True,
    size: str = "md",
    fetched_at: float | None = None,
) -> ft.Container:
    """Colored badge representing a WeatherState with optional icon and staleness dot."""
    cfg = _BADGE_SIZES.get(size, _BADGE_SIZES["md"])
    color = AFFINITY_COLORS[weather]

    controls: list[ft.Control] = []

    # Icon
    if show_icon:
        if icon_code:
            controls.append(
                ft.Image(
                    src=f"https://openweathermap.org/img/wn/{icon_code}@2x.png",
                    width=cfg["icon_size"],
                    height=cfg["icon_size"],
                )
            )
        else:
            controls.append(
                ft.Icon(
                    _WEATHER_ICONS[weather],
                    color=color,
                    size=cfg["icon_size"],
                )
            )

    # Label
    if show_label:
        controls.append(
            ft.Text(
                weather.value.capitalize(),
                size=cfg["font_size"],
                color=TEXT_PRIMARY,
                weight=ft.FontWeight.W_500,
            )
        )

    # Staleness dot
    if fetched_at is not None:
        age = time.time() - fetched_at
        if age > _STALE_THRESHOLD_S:
            controls.append(
                ft.Container(
                    width=6,
                    height=6,
                    bgcolor=WARNING,
                    border_radius=3,
                )
            )

    tooltip_text = _build_tooltip(weather)

    side = ft.BorderSide(1, color)
    return ft.Container(
        content=ft.Row(controls=controls, spacing=SPACING_XS, tight=True),
        bgcolor=SURFACE,
        border=ft.Border(top=side, right=side, bottom=side, left=side),
        border_radius=CARD_RADIUS,
        padding=ft.Padding(
            left=cfg["padding"], right=cfg["padding"],
            top=cfg["padding"], bottom=cfg["padding"],
        ),
        tooltip=tooltip_text,
    )
