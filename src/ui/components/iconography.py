"""Shared iconography + tone helpers — the single place the affinity/weather/trait
glyph + favor-color conventions live (V.1: presentation only, no combat math).

Color alone is ambiguous and colorblind-hostile, so every affinity/weather/trait
state pairs a **glyph** with its color. These helpers keep that pairing — and the
buff=green / debuff=red favor tone — in one module instead of re-deriving it in
each view (Prep, Combat, the badges, the synergy panel).
"""

from __future__ import annotations

import re

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
    ROLE_ICON_ASSETS,
    ROLE_ICONS,
    STAT_ICONS,
    SUCCESS,
    SURFACE,
    SURFACE_ELEVATED,
    SWORD_ICON_ASSET,
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
) -> ft.Control | None:
    """The champion-role glyph (assassin/mage/tank/…), or ``None`` for an unknown
    role. Some roles (swashbuckler) use a custom SVG asset; the rest a Material
    icon. Tooltipped by the role name. Shown next to a piece's name."""
    asset = ROLE_ICON_ASSETS.get(role.lower())
    if asset is not None:
        g: ft.Control = ft.Image(src=asset, width=size, height=size, color=color)
    else:
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


# Prose keyword (normalized, lowercased, letters only) → effect key. Inline icons
# are injected right after the matching word in a blurb (e.g. "physical damage ⚔").
_INLINE_KEYWORDS: dict[str, str] = {
    "physical": "physical",
    "magic": "magic", "magical": "magic",
    "heal": "heal", "heals": "heal", "healing": "heal",
    "shield": "shield", "shields": "shield", "barrier": "shield",
    "stun": "stun", "stuns": "stun", "stunned": "stun",
    "slow": "slow", "slows": "slow", "slowed": "slow",
    "burn": "burn", "burns": "burn", "burning": "burn",
    "poison": "poison", "poisoned": "poison", "poisons": "poison",
    "mana": "mana",
    "armor": "armor",
    "movespeed": "haste",
    "crit": "crit", "critical": "crit",
}

# Two-word phrases (checked before single words) — the glyph lands after the noun,
# so "physical damage ⚔" and "+10 Move Speed 🏃" read the way they're written.
_INLINE_PHRASES: dict[str, str] = {
    "physical damage": "physical",
    "magic damage": "magic", "magical damage": "magic",
    "move speed": "haste", "movement speed": "haste",
    "attack speed": "as",
}


def _norm(word: str) -> str:
    """Lowercase a prose word and strip non-letters (so ``"damage,"`` → ``"damage"``)."""
    return re.sub(r"[^a-z]", "", word.lower())


def _effect_icon(key: str, *, size: int, color: str) -> ft.Control | None:
    """The glyph for an effect/stat key — physical damage from the custom sword
    asset (no fitting Material glyph), everything else a tinted Material icon."""
    if key == "physical":
        return ft.Image(src=SWORD_ICON_ASSET, width=size, height=size, color=color)
    icon = ABILITY_TAG_ICONS.get(key) or STAT_ICONS.get(key)
    return ft.Icon(icon, size=size, color=color) if icon else None


def inline_effect_text(
    text: str, *, size: int = 11, color: str = TEXT_PRIMARY,
    icon_color: str | None = None,
) -> ft.Control:
    """Render blurb prose with effect glyphs **inline** — the icon sits right after
    the keyword it describes (``"deal 120 physical damage ⚔ to the target"``).

    Word-walks the text (with a ``"<type> damage"`` lookahead so the damage glyph
    lands after the noun) and lays the runs + icons out in a wrapping Row, so a
    long blurb still flows. Unmatched words are plain text; pure presentation."""
    glyph_color = icon_color if icon_color is not None else TEXT_MUTED
    words = text.split()
    controls: list[ft.Control] = []
    i = 0
    while i < len(words):
        norm = _norm(words[i])
        nxt = _norm(words[i + 1]) if i + 1 < len(words) else ""
        key: str | None = None
        consumed = 1
        # Two-word phrase first (glyph after the noun), else a single keyword.
        if nxt and f"{norm} {nxt}" in _INLINE_PHRASES:
            key = _INLINE_PHRASES[f"{norm} {nxt}"]
            consumed = 2
        elif norm in _INLINE_KEYWORDS:
            key = _INLINE_KEYWORDS[norm]
        controls.append(ft.Text(" ".join(words[i:i + consumed]), size=size, color=color))
        if key is not None:
            icon = _effect_icon(key, size=size + 2, color=glyph_color)
            if icon is not None:
                controls.append(icon)
        i += consumed
    return ft.Row(controls, wrap=True, spacing=4, run_spacing=2,
                  vertical_alignment=ft.CrossAxisAlignment.CENTER)


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
