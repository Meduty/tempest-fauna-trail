"""Design tokens for the Tempest Fauna Trail UI.

Import these constants in any src/ui/ module.  Never import from game/ into
this module beyond WeatherState (for the affinity color map).
"""

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
