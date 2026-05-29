# T8 Plan — Theme + Shared Components (`src/ui/theme.py`, `src/ui/components/`)

## 1. Summary

T.8 delivers the visual design-token layer and reusable Flet component library
that every downstream UI task (T.9–T.13, T.15, T.23) imports. It ships:
`ui/theme.py` (colors, typography, spacing, animation constants) and
`ui/components/` (ChampionCard, WeatherBadge, HPBar, AffinityChip, TraitChip).
No routes, no game logic — purely presentational primitives. Sized **S (<1h)**
because it is tokens + shells; real interactivity lands in consumer tasks.

---

## 2. Design Tokens

### 2.1 Affinity Color Palette

Six colors mapped 1:1 to `WeatherState` (§V.5). Chosen for color-blind
safety (distinguishable across protanopia/deuteranopia via luminance + hue
separation) and WCAG AA contrast (≥4.5:1) against the dark background
`#1C1C1E`.

| WeatherState | Hex       | Flet Constant (approx)      | Contrast vs `#1C1C1E` |
|--------------|-----------|-----------------------------|-----------------------|
| `CLEAR`      | `#A8A8A8` | `ft.Colors.GREY_400`        | 5.3:1                 |
| `CLOUDY`     | `#B0BEC5` | `ft.Colors.BLUE_GREY_200`   | 5.8:1                 |
| `MIST`       | `#CE93D8` | `ft.Colors.PURPLE_200`      | 4.7:1                 |
| `RAIN`       | `#4FC3F7` | `ft.Colors.LIGHT_BLUE_300`  | 5.9:1                 |
| `SNOW`       | `#E0E0E0` | `ft.Colors.GREY_300`        | 8.5:1                 |
| `THUNDER`    | `#FFD54F` | `ft.Colors.AMBER_300`       | 9.1:1                 |

Source: `src/game/models.py:8-14` (enum values),
`docs/design/tasks/t2_weather_effects_plan.md` (ring semantics).

### 2.2 Semantic Palette

| Token              | Hex       | Usage                                |
|--------------------|-----------|--------------------------------------|
| `BG`               | `#1C1C1E` | Page background (dark theme)         |
| `SURFACE`          | `#2C2C2E` | Cards, panels                        |
| `SURFACE_ELEVATED` | `#3A3A3C` | Modals, tooltips, elevated cards     |
| `TEXT_PRIMARY`     | `#F5F5F5` | Headings, labels                     |
| `TEXT_MUTED`       | `#8E8E93` | Captions, secondary info             |
| `ACCENT`           | `#64B5F6` | Interactive elements, links          |
| `DANGER`           | `#EF5350` | HP critical, death state             |
| `SUCCESS`          | `#66BB6A` | Victory, full HP, heals              |
| `WARNING`          | `#FFA726` | Low HP threshold, stale cache        |

Justification: dark theme matches `admin.py` usage (`ft.Colors.with_opacity(0.04, ft.Colors.WHITE)` for subtle backgrounds implies dark page). We do **not** override admin's theme — both coexist under the same dark page background.

### 2.3 Typography Scale

| Token      | Family          | Size | Weight | Use                          |
|------------|-----------------|------|--------|------------------------------|
| `DISPLAY`  | System default  | 28   | Bold   | View titles                  |
| `H1`       | System default  | 22   | Bold   | Section headings             |
| `H2`       | System default  | 18   | Medium | Card names, panel headers    |
| `H3`       | System default  | 15   | Medium | Subheadings                  |
| `BODY`     | System default  | 14   | Normal | General text                 |
| `CAPTION`  | System default  | 12   | Normal | Muted labels, timestamps     |
| `MONO`     | `monospace`     | 12   | Normal | Stats, numeric values        |

Rationale: 7 sizes covers display → caption without redundancy. `monospace`
matches `admin.py`'s existing `_MONO = "monospace"` idiom. System default
avoids font-loading issues under `flet run`.

### 2.4 Spacing Scale

Base unit: **4px**. Exposed multipliers:

| Token   | Value | Use                                  |
|---------|-------|--------------------------------------|
| `XS`    | 4     | Inline pill padding, tight gaps      |
| `SM`    | 8     | Component internal padding           |
| `MD`    | 12    | Between related controls             |
| `LG`    | 16    | Section separation                   |
| `XL`    | 24    | Panel margins                        |
| `XXL`   | 32    | Major layout gutters                 |

### 2.5 Elevation & Radius

| Token           | Value | Use                              |
|-----------------|-------|----------------------------------|
| `CARD_RADIUS`   | 8     | Champion card, weather badge     |
| `CHIP_RADIUS`   | 12    | Affinity/Trait chips (pill)      |
| `BUTTON_RADIUS` | 6     | Action buttons                   |
| `SURFACE_ELEV`  | 2     | Card `shadow` blur radius        |

### 2.6 Animation Timing

Per `CLAUDE.md` Flet conventions (`animate_opacity`, `animate_offset`,
`ft.AnimatedSwitcher`):

| Token              | Duration (ms) | Easing            | Use                        |
|--------------------|---------------|-------------------|----------------------------|
| `ANIM_FAST`        | 150           | `ease_out`        | Hover, chip toggle         |
| `ANIM_NORMAL`      | 300           | `ease_in_out`     | Card selection, slide      |
| `ANIM_SLOW`        | 500           | `ease_in_out`     | View transitions, fade     |
| `ANIM_COMBAT_TICK` | 200           | `linear`          | HP bar drain, mana fill    |

---

## 3. `ui/theme.py` Shape

### 3.1 Design Decision

**Module-level constants** (not a class, not `page.session`).

Justification:
- `admin.py` already uses module-level `_MONO = "monospace"` — this extends
  the existing pattern.
- No runtime theme switching needed for MVP (dark only) — no benefit from a
  `Theme` object or `@dataclass`.
- `game/` never imports this (V.1 invariant) — the dependency is one-way
  (`ui → game` for `WeatherState` enum, never reverse).
- Flet views import `from src.ui.theme import SURFACE, H2, SPACING_MD` etc.
  directly — simple, zero-cost.

### 3.2 Light/Dark

**Dark only for MVP.** `admin.py` already implies dark (white text on dark
containers). T.8 sets `page.bgcolor = BG` and `page.theme_mode =
ft.ThemeMode.DARK` at app init. Admin view is unaffected — it already renders
correctly on a dark page.

### 3.3 Module Sketch

```python
# src/ui/theme.py
"""Design tokens for the Tempest Fauna Trail UI.

Import these constants in any src/ui/ module.  Never import from game/ into
this module beyond WeatherState (for the affinity color map).
"""
from src.game.models import WeatherState

# --- Affinity Colors (per WeatherState) ---
AFFINITY_COLORS: dict[str, str] = {
    WeatherState.CLEAR: "#A8A8A8",
    WeatherState.CLOUDY: "#B0BEC5",
    WeatherState.MIST: "#CE93D8",
    WeatherState.RAIN: "#4FC3F7",
    WeatherState.SNOW: "#E0E0E0",
    WeatherState.THUNDER: "#FFD54F",
}

# --- Semantic Palette ---
BG = "#1C1C1E"
SURFACE = "#2C2C2E"
SURFACE_ELEVATED = "#3A3A3C"
TEXT_PRIMARY = "#F5F5F5"
TEXT_MUTED = "#8E8E93"
ACCENT = "#64B5F6"
DANGER = "#EF5350"
SUCCESS = "#66BB6A"
WARNING = "#FFA726"

# --- Typography ---
FONT_MONO = "monospace"
FONT_SIZE_DISPLAY = 28
FONT_SIZE_H1 = 22
FONT_SIZE_H2 = 18
FONT_SIZE_H3 = 15
FONT_SIZE_BODY = 14
FONT_SIZE_CAPTION = 12
FONT_SIZE_MONO = 12

# --- Spacing (base 4px) ---
SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 12
SPACING_LG = 16
SPACING_XL = 24
SPACING_XXL = 32

# --- Radius / Elevation ---
CARD_RADIUS = 8
CHIP_RADIUS = 12
BUTTON_RADIUS = 6
SURFACE_ELEVATION = 2

# --- Animation (ms) ---
ANIM_FAST = 150
ANIM_NORMAL = 300
ANIM_SLOW = 500
ANIM_COMBAT_TICK = 200
```

---

## 4. Component Inventory

### 4.1 Summary Table

| Component       | File                              | Consumers                              | T.8 Status |
|-----------------|-----------------------------------|----------------------------------------|------------|
| `ChampionCard`  | `ui/components/champion_card.py`  | Recruit (T.10), Prep (T.23), Combat (T.12), Summary (T.13) | **Ship** |
| `WeatherBadge`  | `ui/components/weather_badge.py`  | Trail (T.11), Prep (T.23), Combat (T.12) | **Ship** |
| `HPBar`         | `ui/components/meter_bar.py`      | Combat (T.12), Trail team panel         | **Ship** |
| `ManaBar`       | `ui/components/meter_bar.py`      | Combat (T.12)                           | **Ship** |
| `AffinityChip`  | `ui/components/chips.py`          | ChampionCard, Trail, Prep               | **Ship** |
| `TraitChip`     | `ui/components/chips.py`          | ChampionCard, Prep                      | **Ship** |
| `NodeMarker`    | `viz/route_map.py`                | Trail canvas (T.11) only                | **Defer to T.11** |

### 4.2 Component APIs

#### `ChampionCard`

```python
def champion_card(
    *,
    name: str,
    affinity: WeatherState,
    traits: list[str],
    role: str,
    tier: int,
    level: int,
    max_hp: int,
    hp: int | None = None,          # None = full HP (recruit/prep idle)
    stats: dict[str, int | float],  # {strength, intelligence, attack_speed, ...}
    state: str = "idle",            # idle | selected | disabled | dead | low_hp
    on_click: Callable | None = None,
) -> ft.Container:
```

**Props source**: `src/game/models.py:96-114` (`Champion` fields) and
`src/game/content.py:126-142` (`ChampionDef`). Every card prop maps to a model
field — no invented fields.

**States**:
- `idle`: default surface + full opacity
- `selected`: accent border glow
- `disabled`: muted opacity 0.5, no click
- `dead`: grayscale filter + `DANGER` overlay
- `low_hp`: `WARNING` border accent

**Internal sub-components**: Composes `AffinityChip`, `TraitChip` inline, and
an `HPBar` when `hp is not None`. Card **owns** the HP bar rendering (no
separate composition needed at consumer level for the in-card bar).

**Layout assumptions**: Fixed width ~200px, variable height. Parent arranges
cards in `ft.Row(wrap=True)` or `ft.GridView`.

#### `WeatherBadge`

```python
def weather_badge(
    *,
    weather: WeatherState,
    show_icon: bool = True,         # OpenWeather icon URL
    icon_code: str | None = None,   # e.g. "10d" — required if show_icon=True
    show_label: bool = True,        # text label under/beside icon
    size: str = "md",               # sm | md | lg
    fetched_at: float | None = None,  # timestamp; badge shows staleness dot if aged
) -> ft.Container:
```

**6 variants**: One per `WeatherState`, colored via `AFFINITY_COLORS[weather]`.

**Icon strategy**: Shows OpenWeather icon (`https://openweathermap.org/img/wn/{icon_code}@2x.png`)
when `icon_code` provided (live data available). Falls back to a colored
`ft.Icon` glyph (static) when icon_code is None (e.g. during loading or for
stylized display). This satisfies both use cases.

**Staleness hook**: If `fetched_at` is provided and age exceeds a threshold
(hookable, default 2h per §V.11 / D.17), badge shows a subtle warning dot.
Full health UX is deferred to D.17, but the prop is here.

**Favor tooltip**: Badge tooltip shows the stat-pack semantics from
`weather_effects.WEATHER_BUFF_BASE` / `WEATHER_DEBUFF_BASE` (e.g. "Rain:
+AS, +MR / −STR"). This addresses the playtest finding "weather impact is
thin" by making the Favor magnitude visible at a glance.

Source: `SPEC.md:281-302` (Content Inspiration → Weather States),
`src/game/weather_effects.py:106-122`.

#### `HPBar` / `ManaBar` (shared `meter_bar`)

```python
def meter_bar(
    *,
    current: int | float,
    maximum: int | float,
    color: str = SUCCESS,           # fill color
    warn_color: str = WARNING,      # color when ratio < warn_threshold
    danger_color: str = DANGER,     # color when ratio < danger_threshold
    warn_threshold: float = 0.5,
    danger_threshold: float = 0.25,
    height: int = 6,
    width: int | None = None,       # None = expand
    animate: bool = True,
) -> ft.Container:
```

Pre-designed for combat (T.12) to avoid inventing primitives under pressure.
`ManaBar` is just `meter_bar(color=ACCENT, warn_threshold=0, danger_threshold=0)`.

#### `AffinityChip`

```python
def affinity_chip(
    *,
    affinity: WeatherState,
    size: str = "sm",               # sm | md
) -> ft.Container:
```

Small colored pill showing the affinity name on its `AFFINITY_COLORS` background.
Distinct from `TraitChip` per §V.6/V.8 requirement — affinity is singular and
weather-mapped; traits are open-ended synergy tags.

#### `TraitChip`

```python
def trait_chip(
    *,
    label: str,                     # e.g. "Beast", "Skirmisher"
    size: str = "sm",
) -> ft.Container:
```

Neutral-colored pill (surface-elevated bg, muted text). Visually distinct from
`AffinityChip` to prevent confusion between the single affinity (game mechanic)
and multiple synergy traits (content flavor).

Source: `src/game/content.py:100-122` (`KINSHIP_TAGS`, `CALLING_TAGS`).

---

## 5. Open Questions / D.16 Reconciliation

### 5.1 Route Naming Drift (D.16)

**Conflict**: SPEC §I defines routes `/recruit`, `/map`, `/summary`.
`views_spec.md` defines `/trail`, `/prep`, `/combat` (and `/` for menu).

| SPEC Route  | views_spec Route | Reconciliation Proposal         |
|-------------|------------------|---------------------------------|
| `/`         | `/`              | ✅ Agreed                       |
| `/recruit`  | _(not present)_  | **Propose**: keep `/recruit` — it serves the T.10 team-pick flow which is distinct from `/prep` |
| `/map`      | `/trail`         | **Propose**: use `/trail` — it is the richer name and matches the game's "trail" metaphor |
| —           | `/prep`          | **Propose**: add `/prep` — views_spec §6 defines a pre-combat planning layer not in SPEC routes |
| `/combat`   | `/combat`        | ✅ Agreed                       |
| `/summary`  | _(end state)_    | **Propose**: keep `/summary` — end-of-run BarChart view per SPEC |

**Proposed canonical set**: `/`, `/recruit`, `/trail`, `/prep`, `/combat`, `/summary`, `/admin`.

⚠️ **User must confirm** before T.9+ tasks code route handlers. T.8 itself is
route-agnostic (components don't know about routes).

### 5.2 views_spec §11 Staleness

`views_spec.md` §11 references a 7-node route with 4-value `NodeType`
(`normal`, `elite`, `boss`, `reward`). The implemented model
(`src/game/models.py:33-39`) has a 50-node route with 6-value `NodeType`
(`FIGHT`, `REWARD`, `AUGMENT`, `SUPPLY`, `CHALLENGE`, `BOSS_FIGHT`).

This does **not** block T.8 (components render whatever data they receive), but
it affects `NodeMarker` visual variants when T.11 lands. Flagged for a
`views_spec.md` sync pass.

### 5.3 Champion Card: Active/Passive Display

`Champion` has `active_ability: str | None` and `passive_ability: str | None`.
Card design shows name only (tooltip for description when ability system docs
are authored). Confirm: display ability names on card face, or keep it
hover/detail only?

---

## 6. Test Plan

### 6.1 Unit Tests (`tests/ui/test_theme.py`)

Theme tokens are pure constants — tests validate structural integrity:

- `AFFINITY_COLORS` has exactly 6 keys matching `WeatherState` members.
- All hex strings are valid 7-char format (`#RRGGBB`).
- All spacing values are multiples of 4.
- All font sizes are positive integers.

### 6.2 Component Construction Tests (`tests/ui/test_components.py`)

Components are Flet-coupled but can be **constructed** without a running app:

- `champion_card(...)` returns an `ft.Container` with expected child count.
- `weather_badge(weather=WeatherState.RAIN, ...)` produces a container with
  the correct background color.
- `meter_bar(current=50, maximum=100)` renders without error; ratio-based
  color thresholds produce correct fill color.
- `affinity_chip(affinity=WeatherState.MIST)` uses the MIST color.
- `trait_chip(label="Beast")` renders label text.
- All components accept all documented states/props without raising.

### 6.3 Visual Review Only (no automated test)

- Overall dark-theme appearance.
- Color-blind safety (manual inspection with simulated filters).
- Animation feel (timing constants are subjective).

---

## 7. Module Layout

### 7.1 File Structure

```
src/ui/
├── theme.py                    # Design tokens (§3)
├── components/
│   ├── __init__.py             # Re-exports public API
│   ├── champion_card.py        # ChampionCard
│   ├── weather_badge.py        # WeatherBadge
│   ├── meter_bar.py            # meter_bar (HPBar + ManaBar)
│   └── chips.py                # AffinityChip + TraitChip
└── views/
    └── admin.py                # (existing, unchanged)
```

### 7.2 `__init__.py` Re-export Policy

```python
# src/ui/components/__init__.py
from src.ui.components.champion_card import champion_card
from src.ui.components.weather_badge import weather_badge
from src.ui.components.meter_bar import meter_bar
from src.ui.components.chips import affinity_chip, trait_chip
```

Consumers import: `from src.ui.components import champion_card, weather_badge`.

### 7.3 Import Path Verification

**Under `flet run`** (cwd = `src/`, `src/` on `sys.path`):
- `main.py` shim adds project root → `src.ui.theme` resolves ✅
- `from src.ui.components import champion_card` resolves ✅

**Under pytest** (cwd = project root, project root on `sys.path`):
- `src.ui.theme` resolves directly ✅
- `conftest.py` at root handles path setup ✅

Both paths work because `main.py:8-9` adds `_PROJECT_ROOT` to `sys.path`.

---

## 8. Integration: Admin View Coexistence

T.8 does **not** modify `admin.py`. Reconciliation:

- `theme.py` sets page-wide `page.bgcolor` and `page.theme_mode` in `main.py`
  at app init (before admin mount).
- `admin.py` already uses `bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.WHITE)` — this remains correct on the dark page.
- Admin's `AppBar` (line 295-296) is set per-view via `ft.View(appbar=...)` — no conflict with other views that set their own `appbar`.
- No shared state, no style collision.

---

## 9. Out of Scope (Non-Goals for T.8)

| Item | Deferred To | Reason |
|------|-------------|--------|
| Route handlers / `page.on_route_change` | T.9 (Menu) | T.8 is route-agnostic |
| Route map canvas styling / `NodeMarker` | T.11 | Canvas-specific; not a reusable component |
| Combat log animation choreography | T.12 | Relies on `BattleResult` event stream |
| Prep board grid / hex layout | T.23 | Layout-specific to prep view |
| End-of-run summary BarChart | T.13 | Visualization task |
| Light theme / theme switching | Post-MVP | Dark only for MVP; admin already dark |
| Cache health UX (D.17) | Post-T.8 | Badge has the `fetched_at` hook; full UX is polish |
| Ability tooltip content | T.20+ | Ability descriptions not authored yet |
| `game/` imports of theme | Never | V.1 invariant — `game/` has zero Flet imports |
| Route name canonicalization code | T.9 | T.8 flags the question (§5.1); T.9 implements |
