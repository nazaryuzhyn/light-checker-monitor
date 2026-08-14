"""Font loading for the schedule renderer.

Both faces are vendored so the image looks identical on a laptop and in the
container. JetBrains Mono sets every number — its tabular figures keep the hour
axis on an even rhythm; Manrope sets every word.
"""

import logging
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

log = logging.getLogger(__name__)

FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"
MONO_FONT = FONT_DIR / "JetBrainsMono.ttf"
TEXT_FONT = FONT_DIR / "Manrope.ttf"

_FALLBACKS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
)


@lru_cache(maxsize=64)
def _load(path: str, size: int, weight: int) -> ImageFont.FreeTypeFont:
    for candidate in (path, *_FALLBACKS):
        if not Path(candidate).exists():
            continue
        try:
            font = ImageFont.truetype(candidate, size)
        except OSError:
            continue
        try:
            font.set_variation_by_axes([weight])
        except (OSError, AttributeError):
            pass  # static face — the default instance is fine
        return font

    log.warning("No usable font found for %s; falling back to the bitmap default", path)
    return ImageFont.load_default(size)


def mono(size: int, weight: int = 600) -> ImageFont.FreeTypeFont:
    return _load(str(MONO_FONT), size, weight)


def text(size: int, weight: int = 500) -> ImageFont.FreeTypeFont:
    return _load(str(TEXT_FONT), size, weight)
