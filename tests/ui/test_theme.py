"""Unit tests for src/ui/theme.py design tokens."""

import re

from src.game.models import WeatherState
from src.ui.theme import (
    AFFINITY_COLORS,
    AFFINITY_ICONS,
    ANIM_COMBAT_TICK,
    ANIM_FAST,
    ANIM_NORMAL,
    ANIM_SLOW,
    BG,
    BUTTON_RADIUS,
    CARD_RADIUS,
    CHIP_RADIUS,
    FONT_SIZE_BODY,
    FONT_SIZE_CAPTION,
    FONT_SIZE_DISPLAY,
    FONT_SIZE_H1,
    FONT_SIZE_H2,
    FONT_SIZE_H3,
    FONT_SIZE_MONO,
    SPACING_LG,
    SPACING_MD,
    SPACING_SM,
    SPACING_XL,
    SPACING_XS,
    SPACING_XXL,
    SURFACE_ELEVATION,
)


_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _relative_luminance(hex_color: str) -> float:
    """Compute relative luminance per WCAG 2.1."""
    r, g, b = (int(hex_color[i : i + 2], 16) / 255.0 for i in (1, 3, 5))
    channels = []
    for c in (r, g, b):
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast_ratio(fg: str, bg: str) -> float:
    """Compute WCAG contrast ratio between two hex colors."""
    l1 = _relative_luminance(fg)
    l2 = _relative_luminance(bg)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


class TestAffinityColors:
    def test_has_all_weather_states(self):
        assert set(AFFINITY_COLORS.keys()) == set(WeatherState)

    def test_exactly_six_keys(self):
        assert len(AFFINITY_COLORS) == 6

    def test_all_valid_hex(self):
        for ws, color in AFFINITY_COLORS.items():
            assert _HEX_RE.match(color), f"{ws}: {color} not valid #RRGGBB"

    def test_wcag_aa_contrast_against_bg(self):
        for ws, color in AFFINITY_COLORS.items():
            ratio = _contrast_ratio(color, BG)
            assert ratio >= 4.5, (
                f"{ws.value}: contrast {ratio:.2f} < 4.5 against BG"
            )


class TestAffinityIcons:
    def test_has_all_weather_states(self):
        assert set(AFFINITY_ICONS.keys()) == set(WeatherState)

    def test_all_non_empty(self):
        for ws, icon in AFFINITY_ICONS.items():
            assert icon, f"{ws}: empty icon"


class TestTraitIcons:
    def test_every_registered_trait_has_an_icon(self):
        # Color-only states are ambiguous; every synergy gets a glyph. Guards the
        # TRAIT_ICONS map against drifting from TRAIT_REGISTRY (new/renamed traits).
        import src.game.traits  # noqa: F401 — populate TRAIT_REGISTRY
        from src.game.registries import TRAIT_REGISTRY
        from src.ui.theme import TRAIT_ICONS

        assert set(TRAIT_ICONS) == set(TRAIT_REGISTRY), (
            f"missing: {set(TRAIT_REGISTRY) - set(TRAIT_ICONS)}; "
            f"orphan: {set(TRAIT_ICONS) - set(TRAIT_REGISTRY)}"
        )

    def test_weather_traits_reuse_affinity_glyph(self):
        # All six weather-themed Callings must read identically to their affinity
        # (SPEC V.81 + docs/live/systems/ui.md).
        from src.ui.theme import TRAIT_ICONS

        for trait, weather in (
            ("Frostbound", WeatherState.SNOW),
            ("Galvanized", WeatherState.THUNDER),
            ("Overcast", WeatherState.CLOUDY),
            ("Shrouded", WeatherState.MIST),
            ("Stormfed", WeatherState.RAIN),
            ("Sunlit", WeatherState.CLEAR),
        ):
            assert TRAIT_ICONS[trait] == AFFINITY_ICONS[weather], trait


class TestRoleIcons:
    def test_every_roster_role_has_an_icon(self):
        # Every role the roster actually uses must have a glyph (guards ROLE_ICONS
        # against a new role slipping in without an icon).
        from src.game.content import CHAMPION_DEF_BY_ID, build_champion_at_level
        from src.ui.theme import ROLE_ICON_ASSETS, ROLE_ICONS

        roles = {build_champion_at_level(cid, 1).role for cid in CHAMPION_DEF_BY_ID}
        known = set(ROLE_ICONS) | set(ROLE_ICON_ASSETS)
        missing = {r for r in roles if r.lower() not in known}
        assert not missing, f"roles without an icon: {missing}"


class TestStatAndTagIcons:
    def test_stat_icons_non_empty(self):
        from src.ui.theme import STAT_ICONS

        assert STAT_ICONS and all(STAT_ICONS.values())

    def test_movespeed_has_a_runner(self):
        # The operator's "shoe with motion" — movement must read as movement.
        import flet as ft

        from src.ui.theme import STAT_ICONS

        assert STAT_ICONS["ms"] == ft.Icons.DIRECTIONS_RUN

    def test_damage_type_glyphs(self):
        # Physical = a custom sword asset (no fitting Material glyph); magic = wand.
        import os

        import flet as ft

        from src.ui.theme import ABILITY_TAG_ICONS, SWORD_ICON_ASSET

        assert "physical" not in ABILITY_TAG_ICONS  # owned by the inline sword asset
        assert ABILITY_TAG_ICONS["magic"] == ft.Icons.AUTO_FIX_HIGH
        assert SWORD_ICON_ASSET.endswith(".svg")
        # The asset actually exists on disk under src/assets.
        assert os.path.exists(os.path.join("src", "assets", SWORD_ICON_ASSET))


class TestSemanticPalette:
    def test_all_hex_format(self):
        from src.ui import theme

        palette_names = [
            "BG", "SURFACE", "SURFACE_ELEVATED", "TEXT_PRIMARY",
            "TEXT_MUTED", "ACCENT", "DANGER", "SUCCESS", "WARNING",
        ]
        for name in palette_names:
            val = getattr(theme, name)
            assert _HEX_RE.match(val), f"{name}: {val} not valid #RRGGBB"


class TestSpacing:
    def test_all_multiples_of_4(self):
        spacings = [SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG, SPACING_XL, SPACING_XXL]
        for s in spacings:
            assert s % 4 == 0, f"Spacing {s} not a multiple of 4"


class TestTypography:
    def test_all_positive_integers(self):
        sizes = [
            FONT_SIZE_DISPLAY, FONT_SIZE_H1, FONT_SIZE_H2,
            FONT_SIZE_H3, FONT_SIZE_BODY, FONT_SIZE_CAPTION, FONT_SIZE_MONO,
        ]
        for size in sizes:
            assert isinstance(size, int) and size > 0, f"Font size {size} invalid"


class TestRadius:
    def test_positive_values(self):
        for val in [CARD_RADIUS, CHIP_RADIUS, BUTTON_RADIUS, SURFACE_ELEVATION]:
            assert isinstance(val, int) and val > 0


class TestAnimation:
    def test_positive_durations(self):
        for val in [ANIM_FAST, ANIM_NORMAL, ANIM_SLOW, ANIM_COMBAT_TICK]:
            assert isinstance(val, int) and val > 0
