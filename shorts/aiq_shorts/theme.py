"""American Inequality brand theme for vertical short-form video.

Every colour, font, and layout constant the renderer uses lives here, so the
look of every video can be changed in one place.
"""
from pathlib import Path

# --- Canvas -----------------------------------------------------------------
W, H = 1080, 1920
FPS = 30

# --- Brand palette ------------------------------------------------------------
ORANGE = (252, 85, 40)        # fc5528  defining colour / background
GOLD = (255, 177, 0)          # ffb100  Arrow Gold
YELLOW = (241, 232, 39)       # f1e827  Arrow Yellow
GREEN = (0, 140, 57)          # 008c39  Arrow Green
BLUE_LIGHT = (0, 152, 198)    # 0098c6  Arrow Blue (light)
BLUE_DARK = (0, 76, 144)      # 004c90  Arrow Blue (dark)
TITLE = (254, 248, 251)       # fef8fb  title text
NAVY = (0, 51, 117)           # 003375  subtitle & author text

# Derived tones (kept on-palette: darker/lighter mixes of the brand colours)
ORANGE_DEEP = (214, 64, 24)   # vignette edge of the orange background
INK = (8, 22, 48)             # near-black navy used to darken photos

# Names usable in storyboards: "color": "navy"
COLORS = {
    "orange": ORANGE,
    "gold": GOLD,
    "yellow": YELLOW,
    "green": GREEN,
    "blue": BLUE_LIGHT,
    "lightblue": BLUE_LIGHT,
    "darkblue": BLUE_DARK,
    "white": TITLE,
    "title": TITLE,
    "navy": NAVY,
    "ink": INK,
}


def color(value, default=TITLE):
    """Resolve a storyboard colour: a palette name, '#rrggbb', or an RGB list."""
    if value is None:
        return default
    if isinstance(value, (list, tuple)):
        return tuple(int(v) for v in value[:3])
    value = str(value).strip().lower()
    if value in COLORS:
        return COLORS[value]
    value = value.lstrip("#")
    if len(value) == 6:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    raise ValueError(f"Unknown colour: {value!r}")


# --- Typography ---------------------------------------------------------------
FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
FONTS = {
    "mono": "IBMPlexMono-Bold.ttf",          # headlines, numbers, stamps
    "mono_semi": "IBMPlexMono-SemiBold.ttf",  # chart labels
    "mono_med": "IBMPlexMono-Medium.ttf",     # source lines, small print
    "sans": "Inter-Bold.ttf",                 # captions, chart titles
    "sans_semi": "Inter-SemiBold.ttf",
    "sans_heavy": "Inter-ExtraBold.ttf",      # article-card title
    "display": "InterDisplay-Black.ttf",      # giant numbers
    "serif": "IBMPlexSerif-Bold.ttf",         # quoted headlines on news cards
    "serif_semi": "IBMPlexSerif-SemiBold.ttf",
}

# --- Layout (px on the 1080x1920 canvas) --------------------------------------
MARGIN = 90                 # left/right gutter for charts
CAPTION_TOP = 1440          # top of the caption block
CAPTION_WIDTH = 900
CAPTION_SIZE = 50
SOURCE_Y = 1700             # source line under the caption
CHART_TITLE_Y = 330         # chart-scene title baseline area
CHART_TOP = 470             # top of the chart drawing area
CHART_BOTTOM = 1300         # bottom of the chart drawing area

# --- Motion --------------------------------------------------------------------
CROSSFADE = 0.3             # seconds of crossfade into each scene
CAPTION_FADE = 0.18
DEFAULT_WPM = 170           # narration pace used to time scenes

BRAND = "American Inequality"
BRAND_URL = "americaninequality.substack.com"
