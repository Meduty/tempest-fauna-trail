# T8 — Theme + Shared Components

**Date**: 2026-05-29

## Summary

Implemented the design-token layer (`src/ui/theme.py`) and reusable Flet
component library (`src/ui/components/`) that all downstream UI tasks
(T.9–T.13, T.15, T.23) will import.

## What Shipped

### `src/ui/theme.py`
Module-level constants following the existing `admin.py` idiom (`_MONO = "monospace"`):
- **Affinity colors**: 6 hex values mapped to `WeatherState`, all WCAG AA (≥4.5:1) against `BG`
- **Semantic palette**: 9 tokens (BG, SURFACE, SURFACE_ELEVATED, TEXT_PRIMARY, TEXT_MUTED, ACCENT, DANGER, SUCCESS, WARNING)
- **Typography**: 7 size tokens + monospace family
- **Spacing**: 6 values on a 4px base grid
- **Radius/elevation**: CARD_RADIUS, CHIP_RADIUS, BUTTON_RADIUS, SURFACE_ELEVATION
- **Animation timing**: 4 tokens (FAST/NORMAL/SLOW/COMBAT_TICK)

### `src/ui/components/`
Five presentational components, all returning `ft.Container`:
- **`champion_card`** — Full champion display with inline AffinityChip, TraitChips, stats row, optional HP bar. Supports 5 visual states (idle/selected/disabled/dead/low_hp).
- **`weather_badge`** — Colored badge per WeatherState with OpenWeather icon or fallback glyph, staleness dot hook, and buff/debuff tooltip.
- **`meter_bar`** — Generic HP/Mana bar with threshold-based color transitions (success → warning → danger). Animated by default.
- **`affinity_chip`** — Colored pill on affinity background.
- **`trait_chip`** — Neutral pill for synergy trait tags, visually distinct from affinity.

### Tests
- `tests/ui/test_theme.py` — Validates hex format, WCAG contrast, spacing multiples, positive sizes
- `tests/ui/test_components.py` — Construction tests for all components (40 tests)

## Key Decisions

1. **Module-level constants, not a Theme class** — matches existing pattern, simple imports, no runtime switching needed for dark-only MVP.
2. **Flet 0.85 API** — Uses `ft.Padding(...)` and `ft.Border(...)` constructors directly (no `ft.padding.symmetric` or `ft.border.all` — these don't exist in 0.85).
3. **`ft.Icon` positional arg** — Flet 0.85 takes icon name as first positional arg, not `name=` kwarg.
4. **WeatherBadge tooltip** — Shows actual buff/debuff stat modifiers from `weather_effects.py`, addressing the playtest finding "weather impact is thin."
5. **`fetched_at` staleness prop** — Hook ready for D.17 cache health UX; threshold set to 2h per §V.11.

## Open Items Flagged

- **Route naming** (§5.1 in plan): SPEC vs views_spec drift. T.8 is route-agnostic; resolution deferred to T.9.
- **views_spec §11 staleness**: 7-node / 4-value NodeType doesn't match implemented 50-node / 6-value model. Doesn't block T.8; flagged for sync pass.
- **Ability tooltip content**: Cards show ability names when ability system docs are authored (T.20+).
