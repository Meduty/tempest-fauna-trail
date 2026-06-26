"""Shared iconography + tone helpers — the single place the affinity/weather/trait
glyph + favor-color conventions live (V.1: presentation only, no combat math).

Color alone is ambiguous and colorblind-hostile, so every affinity/weather/trait
state pairs a **glyph** with its color. These helpers keep that pairing — and the
buff=green / debuff=red favor tone — in one module instead of re-deriving it in
each view (Prep, Combat, the badges, the synergy panel).
"""

from __future__ import annotations

import flet as ft

from src.game.models import WeatherState
from src.game.weather_effects import RingRelation
from src.ui.theme import (
    ABILITY_TAG_ICONS,
    AFFINITY_COLORS,
    AFFINITY_ICONS,
    CARD_RADIUS,
    DANGER,
    FONT_MONO,
    FONT_SIZE_CAPTION,
    ROLE_ICONS,
    STAT_ICONS,
    SUCCESS,
    SURFACE,
    SURFACE_ELEVATED,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TIER_BRONZE,
    TIER_GOLD,
    TIER_SILVER,
    TRAIT_ICON_FALLBACK,
    TRAIT_ICONS,
)

# Ring relations that are a *buff* (rest are debuff / neutral) — single source.
_BUFF_RELATIONS = frozenset({
    RingRelation.SELF,
    RingRelation.PRIMARY_PREDATOR,
    RingRelation.SECONDARY_PREDATOR,
})
_DEBUFF_RELATIONS = frozenset({
    RingRelation.PRIMARY_PREY,
    RingRelation.SECONDARY_PREY,
})


# --------------------------------------------------------------------------
# Affinity / weather glyphs
# --------------------------------------------------------------------------
def affinity_glyph(
    affinity: WeatherState, *, size: int = 14, color: str | None = None,
) -> ft.Icon:
    """The affinity/weather glyph, tinted ``color`` (defaults to the affinity color)."""
    return ft.Icon(
        AFFINITY_ICONS[affinity],
        size=size,
        color=color if color is not None else AFFINITY_COLORS[affinity],
    )


def affinity_marker(affinity: WeatherState, *, size: int = 14) -> ft.Icon:
    """Drop-in replacement for the bare colored dot — same color, now a glyph so
    the affinity reads without a legend."""
    return affinity_glyph(affinity, size=size)


# --------------------------------------------------------------------------
# Favor tone (buff / debuff / neutral)
# --------------------------------------------------------------------------
def favor_tone(relation: RingRelation) -> str:
    """The semantic color for a ring relation: buff → SUCCESS, debuff → DANGER,
    neutral → muted. One definition for every favor/clash readout."""
    if relation in _BUFF_RELATIONS:
        return SUCCESS
    if relation in _DEBUFF_RELATIONS:
        return DANGER
    return TEXT_MUTED


def clash_marker(relation: RingRelation) -> tuple[str, str]:
    """``(glyph, color)`` for an affinity-clash hint: predator ▲ green, prey ▼ red,
    neutral · muted. Mirrors ``favor_tone`` so color stays consistent."""
    if relation in _BUFF_RELATIONS:
        return ("▲", SUCCESS)
    if relation in _DEBUFF_RELATIONS:
        return ("▼", DANGER)
    return ("·", TEXT_MUTED)


def clash_legend() -> ft.Control:
    """Tiny inline legend so the ▲/▼ clash markers teach themselves."""
    def _item(glyph: str, color: str, label: str) -> ft.Control:
        return ft.Row(
            [ft.Text(glyph, size=10, color=color),
             ft.Text(label, size=9, color=TEXT_MUTED)],
            spacing=2, tight=True,
        )
    return ft.Row(
        [_item("▲", SUCCESS, "you prey on"), _item("▼", DANGER, "preys on you")],
        spacing=10,
    )


# --------------------------------------------------------------------------
# Trait glyphs (TFT-style)
# --------------------------------------------------------------------------
def _tier_color(cleared: int) -> str:
    """Bronze/silver/gold by how many rungs are cleared (TFT convention)."""
    if cleared >= 3:
        return TIER_GOLD
    if cleared == 2:
        return TIER_SILVER
    return TIER_BRONZE


def trait_glyph(
    trait_id: str, *, size: int = 16, color: str | None = None,
    cleared: int = 0, active: bool = True,
) -> ft.Icon:
    """The trait's glyph. When ``color`` is given it wins; otherwise an active trait
    is tinted by tier (bronze/silver/gold from ``cleared`` rungs) and a dormant one
    is muted — same readout as TFT's trait hexes."""
    icon = TRAIT_ICONS.get(trait_id, TRAIT_ICON_FALLBACK)
    if color is None:
        color = _tier_color(cleared) if active else TEXT_MUTED
    return ft.Icon(icon, size=size, color=color)


# --------------------------------------------------------------------------
# Role / stat / ability-tag glyphs
# --------------------------------------------------------------------------
def role_glyph(
    role: str, *, size: int = 15, color: str = TEXT_MUTED,
) -> ft.Icon | None:
    """The champion-role glyph (assassin/mage/tank/…), or ``None`` for an unknown
    role. Tooltipped by the caller. Shown next to a piece's name."""
    icon = ROLE_ICONS.get(role.lower())
    if icon is None:
        return None
    g = ft.Icon(icon, size=size, color=color)
    g.tooltip = role.capitalize()
    return g


def stat_glyph(
    label: str, *, size: int = 12, color: str = TEXT_MUTED,
) -> ft.Icon | None:
    """The glyph for a stat short-label (``"STR"``, ``"MS"``, …), or ``None`` if the
    stat has no icon. Case-insensitive."""
    icon = STAT_ICONS.get(label.lower())
    if icon is None:
        return None
    return ft.Icon(icon, size=size, color=color)


def tag_glyphs(
    tags: tuple[str, ...], *, size: int = 13, max_n: int = 4,
) -> list[ft.Control]:
    """Glyph chips for an ability's effect tags — physical = weapon, magic = wand,
    haste = runner, etc. Only mapped tags render (no fallback clutter), capped at
    ``max_n``, each tooltipped by tag name. Order follows ``tags``."""
    out: list[ft.Control] = []
    for tag in tags:
        icon = ABILITY_TAG_ICONS.get(tag)
        if icon is None:
            continue
        g = ft.Icon(icon, size=size, color=TEXT_MUTED)
        g.tooltip = tag
        out.append(g)
        if len(out) >= max_n:
            break
    return out


# --------------------------------------------------------------------------
# Styled tooltip
# --------------------------------------------------------------------------
def rich_tooltip(message: str, *, tone: str | None = None) -> ft.Tooltip:
    """A legible tooltip: dark card, mono text, optional tone-tinted border.

    Flet tooltips are single-style (one ``text_style`` for the whole message — no
    per-line color), so structure carries meaning via markers (●/○, +/−) in the
    caller's text; this helper supplies the consistent card styling + a tone accent."""
    border_color = tone if tone is not None else SURFACE_ELEVATED
    return ft.Tooltip(
        message=message,
        padding=ft.Padding(left=10, right=10, top=8, bottom=8),
        text_style=ft.TextStyle(
            size=FONT_SIZE_CAPTION, color=TEXT_PRIMARY, font_family=FONT_MONO,
        ),
        decoration=ft.BoxDecoration(
            bgcolor=SURFACE,
            border=ft.Border.all(1, border_color),
            border_radius=CARD_RADIUS,
        ),
        wait_duration=200,
    )
