"""Component construction tests for src/ui/components/."""

import time

import flet as ft

from src.game.models import WeatherState
from src.ui.components import (
    affinity_chip,
    champion_card,
    meter_bar,
    trait_chip,
    weather_badge,
)
from src.ui.theme import AFFINITY_COLORS, DANGER, SUCCESS, WARNING


class TestChampionCard:
    """champion_card returns an ft.Container with expected structure."""

    def _make_card(self, **overrides):
        defaults = dict(
            name="Fenrir",
            affinity=WeatherState.SNOW,
            traits=["Beast", "Skirmisher"],
            role="melee",
            tier=3,
            level=1,
            max_hp=100,
            stats={"strength": 45, "intelligence": 20, "attack_speed": 60},
        )
        defaults.update(overrides)
        return champion_card(**defaults)

    def test_returns_container(self):
        card = self._make_card()
        assert isinstance(card, ft.Container)

    def test_idle_state_full_opacity(self):
        card = self._make_card(state="idle")
        assert card.opacity == 1.0

    def test_disabled_state_reduced_opacity(self):
        card = self._make_card(state="disabled")
        assert card.opacity == 0.5

    def test_selected_state_has_border(self):
        card = self._make_card(state="selected")
        assert card.border is not None

    def test_hp_bar_shown_when_hp_provided(self):
        card = self._make_card(hp=50)
        # Card content is a Column; last control should be the HP bar
        col = card.content
        assert isinstance(col, ft.Column)
        # HP bar is the last control in the column
        assert len(col.controls) == 5  # header, chip_row, trait_row, stats_row, hp_bar

    def test_no_hp_bar_when_hp_none(self):
        card = self._make_card(hp=None)
        col = card.content
        assert isinstance(col, ft.Column)
        assert len(col.controls) == 4  # header, chip_row, trait_row, stats_row

    def test_all_states_construct_without_error(self):
        for state in ("idle", "selected", "disabled", "dead", "low_hp"):
            card = self._make_card(state=state)
            assert isinstance(card, ft.Container)

    def test_on_click_disabled_state(self):
        """Disabled state should not have on_click."""
        handler = lambda e: None
        card = self._make_card(state="disabled", on_click=handler)
        assert card.on_click is None

    def test_on_click_idle_state(self):
        handler = lambda e: None
        card = self._make_card(state="idle", on_click=handler)
        assert card.on_click is handler


class TestWeatherBadge:
    def test_returns_container(self):
        badge = weather_badge(weather=WeatherState.RAIN)
        assert isinstance(badge, ft.Container)

    def test_correct_border_color(self):
        badge = weather_badge(weather=WeatherState.RAIN)
        expected_color = AFFINITY_COLORS[WeatherState.RAIN]
        assert badge.border is not None
        assert badge.border.top.color == expected_color

    def test_all_weather_states(self):
        for ws in WeatherState:
            badge = weather_badge(weather=ws)
            assert isinstance(badge, ft.Container)

    def test_all_sizes(self):
        for size in ("sm", "md", "lg"):
            badge = weather_badge(weather=WeatherState.CLEAR, size=size)
            assert isinstance(badge, ft.Container)

    def test_staleness_dot_when_stale(self):
        stale_time = time.time() - (3 * 60 * 60)  # 3 hours ago
        badge = weather_badge(weather=WeatherState.MIST, fetched_at=stale_time)
        # The row should contain a staleness dot (extra container)
        row = badge.content
        assert isinstance(row, ft.Row)
        # Default: icon + label + dot = 3 controls
        assert len(row.controls) == 3

    def test_no_staleness_dot_when_fresh(self):
        fresh_time = time.time() - 60  # 1 minute ago
        badge = weather_badge(weather=WeatherState.MIST, fetched_at=fresh_time)
        row = badge.content
        assert isinstance(row, ft.Row)
        # icon + label only = 2 controls
        assert len(row.controls) == 2

    def test_has_tooltip(self):
        badge = weather_badge(weather=WeatherState.THUNDER)
        assert badge.tooltip is not None and len(badge.tooltip) > 0

    def test_icon_code_uses_image(self):
        badge = weather_badge(weather=WeatherState.RAIN, icon_code="10d")
        row = badge.content
        # First control should be an Image
        assert isinstance(row.controls[0], ft.Image)

    def test_no_icon_code_uses_icon(self):
        badge = weather_badge(weather=WeatherState.RAIN, icon_code=None)
        row = badge.content
        assert isinstance(row.controls[0], ft.Icon)


class TestMeterBar:
    def test_returns_container(self):
        bar = meter_bar(current=50, maximum=100)
        assert isinstance(bar, ft.Container)

    def test_full_bar_uses_default_color(self):
        bar = meter_bar(current=100, maximum=100)
        # Inner bar is in the row
        row = bar.content
        assert isinstance(row, ft.Row)

    def test_low_bar_uses_warn_color(self):
        bar = meter_bar(current=40, maximum=100)
        # Ratio 0.4 <= 0.5 warn_threshold
        row = bar.content
        inner_container = row.controls[0]
        inner_bar = inner_container.content
        assert inner_bar.bgcolor == WARNING

    def test_critical_bar_uses_danger_color(self):
        bar = meter_bar(current=10, maximum=100)
        # Ratio 0.1 <= 0.25 danger_threshold
        row = bar.content
        inner_container = row.controls[0]
        inner_bar = inner_container.content
        assert inner_bar.bgcolor == DANGER

    def test_zero_maximum_no_error(self):
        bar = meter_bar(current=0, maximum=0)
        assert isinstance(bar, ft.Container)

    def test_custom_thresholds(self):
        bar = meter_bar(
            current=70, maximum=100,
            warn_threshold=0.8, danger_threshold=0.5,
        )
        # 0.7 <= 0.8, so should be warn
        row = bar.content
        inner_container = row.controls[0]
        inner_bar = inner_container.content
        assert inner_bar.bgcolor == WARNING


class TestAffinityChip:
    def test_returns_container(self):
        chip = affinity_chip(affinity=WeatherState.MIST)
        assert isinstance(chip, ft.Container)

    def test_uses_affinity_color(self):
        chip = affinity_chip(affinity=WeatherState.MIST)
        assert chip.bgcolor == AFFINITY_COLORS[WeatherState.MIST]

    def test_all_affinities(self):
        for ws in WeatherState:
            chip = affinity_chip(affinity=ws)
            assert chip.bgcolor == AFFINITY_COLORS[ws]

    def test_sizes(self):
        for size in ("sm", "md"):
            chip = affinity_chip(affinity=WeatherState.RAIN, size=size)
            assert isinstance(chip, ft.Container)


class TestTraitChip:
    def test_returns_container(self):
        chip = trait_chip(label="Beast")
        assert isinstance(chip, ft.Container)

    def test_renders_label(self):
        chip = trait_chip(label="Beast")
        text = chip.content
        assert isinstance(text, ft.Text)
        assert text.value == "Beast"

    def test_sizes(self):
        for size in ("sm", "md"):
            chip = trait_chip(label="Skirmisher", size=size)
            assert isinstance(chip, ft.Container)


class TestIconography:
    """Shared affinity/weather/trait glyph + tone helpers."""

    def test_affinity_glyph_all_states(self):
        from src.ui.components.iconography import affinity_glyph
        from src.ui.theme import AFFINITY_ICONS

        for ws in WeatherState:
            g = affinity_glyph(ws)
            assert isinstance(g, ft.Icon)
            assert g.icon == AFFINITY_ICONS[ws]

    def test_favor_tone_buff_debuff_neutral(self):
        from src.game.weather_effects import RingRelation
        from src.ui.components.iconography import favor_tone

        assert favor_tone(RingRelation.SELF) == SUCCESS
        assert favor_tone(RingRelation.PRIMARY_PREDATOR) == SUCCESS
        assert favor_tone(RingRelation.PRIMARY_PREY) == DANGER
        assert favor_tone(RingRelation.NEUTRAL) not in (SUCCESS, DANGER)

    def test_clash_marker_colors_match_tone(self):
        from src.game.weather_effects import RingRelation
        from src.ui.components.iconography import clash_marker, favor_tone

        for rel in RingRelation:
            _glyph, color = clash_marker(rel)
            assert color == favor_tone(rel)

    def test_trait_glyph_tier_colors(self):
        from src.ui.components.iconography import trait_glyph
        from src.ui.theme import TEXT_MUTED, TIER_BRONZE, TIER_GOLD, TIER_SILVER

        assert trait_glyph("Beast", cleared=1).color == TIER_BRONZE
        assert trait_glyph("Beast", cleared=2).color == TIER_SILVER
        assert trait_glyph("Beast", cleared=3).color == TIER_GOLD
        assert trait_glyph("Beast", active=False).color == TEXT_MUTED

    def test_trait_glyph_unknown_tag_uses_fallback(self):
        from src.ui.components.iconography import trait_glyph
        from src.ui.theme import TRAIT_ICON_FALLBACK

        assert trait_glyph("NotARealTag").icon == TRAIT_ICON_FALLBACK

    def test_rich_tooltip_is_tooltip(self):
        from src.ui.components.iconography import rich_tooltip

        tip = rich_tooltip("hello", tone=SUCCESS)
        assert isinstance(tip, ft.Tooltip)
        assert tip.message == "hello"
