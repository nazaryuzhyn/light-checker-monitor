"""Design tokens for the rendered schedule.

The day is one horizontal 24-hour bar: green where power is on, red where it is
cut, amber for the half hours the utility has not committed to. The palette and
the bar geometry are the original ones; what is new is everything around the
bar — a headline that answers the question in words, an axis you can read at
phone size, and the outage times spelled out underneath.
"""

# ── Canvas ────────────────────────────────────────────────────────────────
WIDTH = 1000
HEIGHT_BASE = 520  # one row of outage times; the canvas grows for each extra row
MARGIN = 56
CONTENT_RIGHT = WIDTH - MARGIN
SUPERSAMPLE = 2  # shapes are drawn at 2× and downsampled; text is drawn at 1×

# ── Palette ───────────────────────────────────────────────────────────────
BG = (13, 14, 19)
TRACK = (26, 28, 35)
AXIS = (38, 41, 50)
TICK_MAJOR = (90, 94, 108)
TICK_MINOR = (58, 62, 74)

TEXT_STRONG = (232, 234, 240)
TEXT_MAJOR = (161, 165, 176)
TEXT_MINOR = (90, 94, 108)
LEGEND_TEXT = (156, 163, 175)
NOW_LINE = (255, 255, 255)

ON = (16, 185, 129)
OFF = (239, 68, 68)
MAYBE = (245, 158, 11)

SHEEN = 30  # alpha of the highlight along the top of the bar
GLOW_STRENGTH = 110  # bloom cast by the outage segments
GLOW_RADIUS = 10

# ── Layout ────────────────────────────────────────────────────────────────
EYEBROW_Y = 46
TITLE_Y = 74

HERO_Y = 140
HERO_DETAIL_Y = 182

BAR_X = MARGIN
BAR_W = CONTENT_RIGHT - MARGIN  # 888 → 18.5 px per half hour
BAR_Y = 252
BAR_H = 56
BAR_RADIUS = 14

NOW_TOP = 228  # where the "now" marker starts, above the bar
NOW_LABEL_Y = 220

AXIS_Y = BAR_Y + BAR_H + 24
TICK_MINOR_LEN = 6
TICK_MAJOR_LEN = 12
AXIS_LABEL_Y = AXIS_Y + 20

OUTAGES_Y = 400
OUTAGES_ROW_H = 32
OUTAGES_MAX_ROWS = 3

LEGEND_FROM_BOTTOM = 42

# ── Type ──────────────────────────────────────────────────────────────────
EYEBROW_SIZE = 18
EYEBROW_TRACKING = 3.0
TITLE_SIZE = 34
HERO_SIZE = 30
HERO_MIN_SIZE = 22
HERO_DETAIL_SIZE = 20
NOW_SIZE = 18
AXIS_SIZE = 19
OUTAGE_LABEL_SIZE = 20
OUTAGE_TIME_SIZE = 23
LEGEND_SIZE = 19
