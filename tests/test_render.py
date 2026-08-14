from io import BytesIO

import pytest
from conftest import MAYBE, OFF, ON, at, schedule
from PIL import Image

from app.services.schedule import theme
from app.services.schedule.render import render_day_png

CASES = {
    "typical": schedule((ON, 8.5), (MAYBE, 0.5), (OFF, 3), (MAYBE, 0.5), (ON, 11.5)),
    "clear": schedule((ON, 24)),
    "all-day-outage": schedule((OFF, 24)),
    "fragmented": schedule(
        (OFF, 3), (ON, 3), (OFF, 3), (ON, 2), (OFF, 4),
        (ON, 2), (OFF, 3), (ON, 1), (OFF, 2), (ON, 1),
    ),
    "tomorrow": schedule((ON, 7), (OFF, 4), (ON, 13), is_today=False),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_every_shape_of_day_renders_a_readable_canvas(name):
    png = render_day_png(CASES[name], now=at(13, 5))

    image = Image.open(BytesIO(png))
    assert image.format == "PNG"
    assert image.width == theme.WIDTH
    assert (
        theme.HEIGHT_BASE - theme.OUTAGES_ROW_H
        <= image.height
        <= theme.HEIGHT_BASE + theme.OUTAGES_ROW_H * (theme.OUTAGES_MAX_ROWS - 1)
    )


def test_the_canvas_grows_only_when_the_outage_list_needs_a_second_row():
    short = Image.open(BytesIO(render_day_png(CASES["typical"], now=at(13, 5))))
    long = Image.open(BytesIO(render_day_png(CASES["fragmented"], now=at(13, 5))))

    assert short.height == theme.HEIGHT_BASE
    assert long.height > short.height


def test_output_stays_small_enough_to_send_as_a_photo():
    png = render_day_png(CASES["fragmented"], now=at(13, 5))
    assert len(png) < 1_000_000
