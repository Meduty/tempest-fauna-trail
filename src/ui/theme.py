"""Design tokens for the Tempest Fauna Trail UI.

Import these constants in any src/ui/ module.  Never import from game/ into
this module beyond WeatherState (for the affinity color/icon maps).
"""

import flet as ft

from src.game.models import WeatherState

# --- Affinity Colors (per WeatherState) ---
AFFINITY_COLORS: dict[WeatherState, str] = {
    WeatherState.CLEAR: "#A8A8A8",
    WeatherState.CLOUDY: "#B0BEC5",
    WeatherState.MIST: "#CE93D8",
    WeatherState.RAIN: "#4FC3F7",
    WeatherState.SNOW: "#E0E0E0",
    WeatherState.THUNDER: "#FFD54F",
}

# --- Affinity / Weather Icons (per WeatherState) ---
# Affinity == WeatherState (V.6), so one glyph map serves both the weather badge
# and every affinity marker — color alone is ambiguous + colorblind-hostile, the
# icon disambiguates at a glance. Canonical here; consumers never redefine it.
AFFINITY_ICONS: dict[WeatherState, str] = {
    WeatherState.CLEAR: ft.Icons.WB_SUNNY,
    WeatherState.CLOUDY: ft.Icons.CLOUD,
    WeatherState.MIST: ft.Icons.BLUR_ON,
    WeatherState.RAIN: ft.Icons.WATER_DROP,
    WeatherState.SNOW: ft.Icons.AC_UNIT,
    WeatherState.THUNDER: ft.Icons.FLASH_ON,
}

# --- Trait Icons (TFT-style per-synergy glyph) ---
# One Material glyph per synergy trait so the trait list + piece infocards read
# at a glance. The six weather-themed Callings reuse their affinity glyph above
# so the synergy and its weather read identically; the rest get a thematic icon.
# Keys MUST match TRAIT_REGISTRY ids exactly (guarded by a UI test).
TRAIT_ICONS: dict[str, str] = {
    # weather-themed Callings → reuse the affinity glyph
    "Frostbound": AFFINITY_ICONS[WeatherState.SNOW],
    "Galvanized": AFFINITY_ICONS[WeatherState.THUNDER],
    "Overcast": AFFINITY_ICONS[WeatherState.CLOUDY],
    "Shrouded": AFFINITY_ICONS[WeatherState.MIST],
    "Stormfed": AFFINITY_ICONS[WeatherState.RAIN],
    "Sunlit": AFFINITY_ICONS[WeatherState.CLEAR],
    # role / kinship traits
    "Beast": ft.Icons.PETS,
    "Bruiser": ft.Icons.SPORTS_MMA,
    "Channeler": ft.Icons.AUTO_FIX_HIGH,
    "Guardian": ft.Icons.SHIELD,
    "Hunter": ft.Icons.GPS_FIXED,
    "Mender": ft.Icons.HEALING,
    "Multicaster": ft.Icons.AUTORENEW,
    "Mystic": ft.Icons.AUTO_FIX_NORMAL,
    "Packmate": ft.Icons.GROUPS,
    "Primordial": ft.Icons.WHATSHOT,
    "Scaled": ft.Icons.LAYERS,
    "Skirmisher": ft.Icons.SPORTS_KABADDI,
    "Skyborn": ft.Icons.FLIGHT,
    "Spirit": ft.Icons.AUTO_AWESOME,
    "Stalker": ft.Icons.VISIBILITY_OFF,
    "Swarm": ft.Icons.GRAIN,
    "Tidekin": ft.Icons.WAVES,
    "Trickster": ft.Icons.THEATER_COMEDY,
    "Warden": ft.Icons.ADD_MODERATOR,
}

# Fallback glyph for any trait tag without a dedicated icon (open-ended tags, V.8).
TRAIT_ICON_FALLBACK: str = ft.Icons.WORKSPACE_PREMIUM

# --- Synergy tier colors (TFT bronze/silver/gold by rungs cleared) ---
TIER_BRONZE = "#CD7F32"
TIER_SILVER = "#C0C0C0"
TIER_GOLD = "#FFD54F"

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
DOT_DAMAGE = "#CE93D8"  # damage-over-time floats — distinct from hit red / crit amber

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
