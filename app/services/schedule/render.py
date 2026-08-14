"""Renders a day of the schedule as a PNG for Telegram.

Two passes: shapes are drawn supersampled and downsampled for smooth edges,
then every glyph is drawn once at final size so text stays crisp on a phone.
"""

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from app.core.timeutil import format_day, format_duration, now_kyiv
from app.services.schedule import fonts, theme
from app.services.schedule.models import (
    SLOTS_PER_DAY,
    DaySchedule,
    PowerLevel,
    minutes_of,
)
from app.services.schedule.source import group_label
from app.services.schedule.summary import Headline, Tone, build_headline

MINUTES_PER_DAY = 24 * 60
HOUR_LABEL_STEP = 3

STATE_COLOR = {
    PowerLevel.ON: theme.ON,
    PowerLevel.OFF: theme.OFF,
    PowerLevel.MAYBE: theme.MAYBE,
}

TONE_COLOR = {
    Tone.LIGHT_ON: theme.ON,
    Tone.LIGHT_OFF: theme.OFF,
    Tone.UNCERTAIN: theme.MAYBE,
}

LEGEND = (
    (PowerLevel.ON, "світло є"),
    (PowerLevel.OFF, "відключення"),
    (PowerLevel.MAYBE, "можливе відключення"),
)


# ── geometry ──────────────────────────────────────────────────────────────


def _slot_x(slot: int) -> float:
    return theme.BAR_X + theme.BAR_W * slot / SLOTS_PER_DAY


def _moment_x(moment: datetime) -> float:
    return theme.BAR_X + theme.BAR_W * minutes_of(moment) / MINUTES_PER_DAY


# ── shape helpers ─────────────────────────────────────────────────────────


def _aa_dot(radius: int, color: tuple[int, int, int], factor: int = 4) -> Image.Image:
    size = radius * 2
    big = Image.new("RGBA", (size * factor, size * factor), (0, 0, 0, 0))
    ImageDraw.Draw(big).ellipse(
        (0, 0, size * factor - 1, size * factor - 1), fill=(*color, 255)
    )
    return big.resize((size, size), Image.LANCZOS)


def _sheen(size: tuple[int, int]) -> Image.Image:
    """A soft highlight down the top of the bar, so it reads as a solid object."""
    w, h = size
    overlay = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    alpha = Image.new("L", (1, h))
    alpha.putdata(
        [
            max(0, round(theme.SHEEN * (1 - y / (h * 0.55)))) if y < h * 0.55 else 0
            for y in range(h)
        ]
    )
    overlay.putalpha(alpha.resize((w, h), Image.NEAREST))
    return overlay


def _build_bar(schedule: DaySchedule, scale: int) -> Image.Image:
    w, h = theme.BAR_W * scale, theme.BAR_H * scale
    bar = Image.new("RGB", (w, h), theme.TRACK)

    for segment in schedule.segments:
        x0 = round(w * segment.start / SLOTS_PER_DAY)
        x1 = round(w * segment.end / SLOTS_PER_DAY)
        bar.paste(STATE_COLOR[segment.level], (x0, 0, x1, h))

    bar = bar.convert("RGBA")
    bar.alpha_composite(_sheen((w, h)))

    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, w - 1, h - 1), radius=theme.BAR_RADIUS * scale, fill=255
    )
    bar.putalpha(mask)
    return bar


def _bloom(  # noqa: D401
    schedule: DaySchedule, scale: int, size: tuple[int, int]
) -> Image.Image:
    """A low glow under the cut hours — the one thing the eye should find first."""
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    for segment in schedule.segments:
        if segment.level is not PowerLevel.OFF:
            continue
        draw.rectangle(
            (
                _slot_x(segment.start) * scale,
                theme.BAR_Y * scale,
                _slot_x(segment.end) * scale,
                (theme.BAR_Y + theme.BAR_H) * scale,
            ),
            fill=theme.GLOW_STRENGTH,
        )
    mask = mask.filter(ImageFilter.GaussianBlur(theme.GLOW_RADIUS * scale))
    return ImageChops.multiply(Image.new("RGB", size, theme.OFF), mask.convert("RGB"))


def _render_shapes(schedule: DaySchedule, height: int) -> Image.Image:
    scale = theme.SUPERSAMPLE
    size = (theme.WIDTH * scale, height * scale)

    canvas = Image.new("RGB", size, theme.BG)
    canvas = ImageChops.add(canvas, _bloom(schedule, scale, size))

    bar = _build_bar(schedule, scale)
    canvas.paste(bar, (theme.BAR_X * scale, theme.BAR_Y * scale), bar)

    return canvas.resize((theme.WIDTH, height), Image.LANCZOS)


# ── text helpers ──────────────────────────────────────────────────────────


def _tracked_width(draw: ImageDraw.ImageDraw, body: str, font, tracking: float) -> float:
    if not body:
        return 0.0
    return sum(draw.textlength(c, font=font) for c in body) + tracking * (len(body) - 1)


def _draw_tracked(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    body: str,
    font,
    fill,
    tracking: float,
    anchor: str = "lt",
) -> float:
    x, y = xy
    width = _tracked_width(draw, body, font, tracking)
    if anchor[0] == "r":
        x -= width
    elif anchor[0] == "m":
        x -= width / 2
    for char in body:
        draw.text((x, y), char, font=font, fill=fill, anchor=f"l{anchor[1]}")
        x += draw.textlength(char, font=font) + tracking
    return width


def _fit_size(
    draw: ImageDraw.ImageDraw, runs: list[tuple[str, Any]], size: int, minimum: int, limit: float
) -> int:
    """Largest size at which the given (text, font-maker) runs still fit on one line."""
    while size > minimum:
        width = sum(draw.textlength(body, font=maker(size)) for body, maker in runs)
        if width <= limit:
            return size
        size -= 2
    return minimum


# ── page sections ─────────────────────────────────────────────────────────


def _draw_header(draw: ImageDraw.ImageDraw, schedule: DaySchedule) -> None:
    _draw_tracked(
        draw,
        (theme.MARGIN, theme.EYEBROW_Y),
        "ГРАФІК ВІДКЛЮЧЕНЬ",
        fonts.text(theme.EYEBROW_SIZE, 700),
        theme.TEXT_MINOR,
        theme.EYEBROW_TRACKING,
    )
    group_font = fonts.mono(theme.EYEBROW_SIZE, 700)
    group = group_label(schedule.group)
    draw.text(
        (theme.CONTENT_RIGHT, theme.EYEBROW_Y),
        group,
        font=group_font,
        fill=theme.TEXT_MAJOR,
        anchor="rt",
    )
    _draw_tracked(
        draw,
        (theme.CONTENT_RIGHT - draw.textlength(group, font=group_font) - 10, theme.EYEBROW_Y),
        "ГРУПА",
        fonts.text(theme.EYEBROW_SIZE, 700),
        theme.TEXT_MINOR,
        theme.EYEBROW_TRACKING,
        anchor="rt",
    )

    when = "Сьогодні" if schedule.is_today else "Завтра"
    draw.text(
        (theme.MARGIN, theme.TITLE_Y),
        f"{when}, {format_day(schedule.day)}",
        font=fonts.text(theme.TITLE_SIZE, 800),
        fill=theme.TEXT_STRONG,
        anchor="lt",
    )


def _draw_hero(draw: ImageDraw.ImageDraw, headline: Headline) -> None:
    limit = theme.CONTENT_RIGHT - theme.MARGIN
    color = TONE_COLOR[headline.tone]
    lead = headline.lead
    # Mono is for clock times; a duration like "7 годин" is words and gets the text face.
    is_clock = ":" in headline.accent
    accent_font = (
        (lambda s: fonts.mono(s, 700)) if is_clock else (lambda s: fonts.text(s, 800))
    )

    runs: list[tuple[str, Any]] = [(lead, lambda s: fonts.text(s, 700))]
    if headline.accent:
        runs.append((headline.accent, accent_font))

    size = _fit_size(draw, runs, theme.HERO_SIZE, theme.HERO_MIN_SIZE, limit)
    x = theme.MARGIN
    lead_font = fonts.text(size, 700)
    draw.text(
        (x, theme.HERO_Y),
        lead,
        font=lead_font,
        fill=theme.TEXT_STRONG if headline.accent else color,
        anchor="lt",
    )
    if headline.accent:
        x += draw.textlength(lead, font=lead_font)
        draw.text(
            (x, theme.HERO_Y),
            headline.accent,
            font=accent_font(size),
            fill=color,
            anchor="lt",
        )

    if headline.detail:
        draw.text(
            (theme.MARGIN, theme.HERO_DETAIL_Y),
            headline.detail,
            font=fonts.text(theme.HERO_DETAIL_SIZE, 500),
            fill=theme.TEXT_MINOR,
            anchor="lt",
        )


def _draw_axis(draw: ImageDraw.ImageDraw) -> None:
    right = theme.BAR_X + theme.BAR_W
    draw.line((theme.BAR_X, theme.AXIS_Y, right, theme.AXIS_Y), fill=theme.AXIS, width=2)

    font = fonts.mono(theme.AXIS_SIZE, 500)
    for hour in range(25):
        x = _slot_x(hour * 2)
        major = hour % HOUR_LABEL_STEP == 0
        length = theme.TICK_MAJOR_LEN if major else theme.TICK_MINOR_LEN
        draw.line(
            (x, theme.AXIS_Y, x, theme.AXIS_Y + length),
            fill=theme.TICK_MAJOR if major else theme.TICK_MINOR,
            width=2,
        )
        if not major:
            continue
        anchor = "lt" if hour == 0 else "rt" if hour == 24 else "mt"
        draw.text(
            (x, theme.AXIS_LABEL_Y),
            f"{hour:02d}:00",
            font=font,
            fill=theme.TEXT_MAJOR,
            anchor=anchor,
        )


def _draw_now(draw: ImageDraw.ImageDraw, moment: datetime) -> None:
    x = _moment_x(moment)
    bottom = theme.BAR_Y + theme.BAR_H + 8

    y = theme.NOW_TOP
    while y < bottom:  # dashed, so it never reads as a segment boundary
        draw.line((x, y, x, min(y + 5, bottom)), fill=theme.NOW_LINE, width=2)
        y += 9

    draw.polygon(
        [(x, theme.NOW_TOP + 8), (x - 5, theme.NOW_TOP), (x + 5, theme.NOW_TOP)],
        fill=theme.NOW_LINE,
    )

    font = fonts.mono(theme.NOW_SIZE, 700)
    label = f"зараз {moment.strftime('%H:%M')}"
    half = draw.textlength(label, font=font) / 2
    label_x = min(max(x, theme.MARGIN + half), theme.CONTENT_RIGHT - half)
    draw.text(
        (label_x, theme.NOW_LABEL_Y), label, font=font, fill=theme.NOW_LINE, anchor="mb"
    )


@dataclass(frozen=True, slots=True)
class _Entry:
    time: str
    meta: str
    color: tuple[int, int, int]


def _outage_entries(schedule: DaySchedule) -> list[_Entry]:
    entries = []
    for outage in schedule.outages:
        certain = outage.is_certain
        entries.append(
            _Entry(
                time=outage.range_label,
                meta=f"· {format_duration(outage.minutes)}" if certain else "· можливо",
                color=theme.OFF if certain else theme.MAYBE,
            )
        )
    return entries


@dataclass(frozen=True, slots=True)
class _OutagePlan:
    """How the outage times will be laid out — measured before the canvas is sized."""

    rows: list[list[_Entry]]
    hidden: int
    size: int
    prefix_w: float

    @property
    def extra_rows(self) -> int:
        return max(0, len(self.rows) - 1)


def _plan_outages(schedule: DaySchedule) -> _OutagePlan | None:
    if not schedule.has_outages:
        return None

    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    entries = _outage_entries(schedule)
    prefix_w = draw.textlength(
        "Без світла:", font=fonts.text(theme.OUTAGE_LABEL_SIZE, 600)
    ) + 14
    limit = theme.CONTENT_RIGHT - theme.MARGIN - prefix_w

    size = theme.OUTAGE_TIME_SIZE
    rows = _wrap(draw, entries, size, limit)
    while len(rows) > theme.OUTAGES_MAX_ROWS and size > theme.OUTAGE_TIME_SIZE - 4:
        size -= 2
        rows = _wrap(draw, entries, size, limit)

    shown = rows[: theme.OUTAGES_MAX_ROWS]
    hidden = len(entries) - sum(len(row) for row in shown)
    return _OutagePlan(rows=shown, hidden=hidden, size=size, prefix_w=prefix_w)


def _draw_outages(draw: ImageDraw.ImageDraw, plan: _OutagePlan | None) -> None:
    if plan is None:
        return  # the headline and an unbroken green bar already say it

    draw.text(
        (theme.MARGIN, theme.OUTAGES_Y + 3),
        "Без світла:",
        font=fonts.text(theme.OUTAGE_LABEL_SIZE, 600),
        fill=theme.TEXT_MINOR,
        anchor="lt",
    )

    time_font = fonts.mono(plan.size, 700)
    meta_font = fonts.text(plan.size - 4, 500)
    x = theme.MARGIN + plan.prefix_w
    for row_index, row in enumerate(plan.rows):
        x = theme.MARGIN + plan.prefix_w
        y = theme.OUTAGES_Y + row_index * theme.OUTAGES_ROW_H
        for entry in row:
            draw.text((x, y), entry.time, font=time_font, fill=entry.color, anchor="lt")
            x += draw.textlength(entry.time, font=time_font) + 8
            draw.text(
                (x, y + 4), entry.meta, font=meta_font, fill=theme.TEXT_MAJOR, anchor="lt"
            )
            x += draw.textlength(entry.meta, font=meta_font) + 26

    # Never let a truncated list read as the whole list.
    if plan.hidden:
        draw.text(
            (x, theme.OUTAGES_Y + plan.extra_rows * theme.OUTAGES_ROW_H + 4),
            f"+ ще {plan.hidden}",
            font=meta_font,
            fill=theme.TEXT_MINOR,
            anchor="lt",
        )


def _wrap(
    draw: ImageDraw.ImageDraw, entries: list[_Entry], size: int, limit: float
) -> list[list[_Entry]]:
    time_font = fonts.mono(size, 700)
    meta_font = fonts.text(size - 4, 500)

    rows: list[list[_Entry]] = [[]]
    used = 0.0
    for entry in entries:
        width = (
            draw.textlength(entry.time, font=time_font)
            + 8
            + draw.textlength(entry.meta, font=meta_font)
            + 26
        )
        if rows[-1] and used + width > limit:
            rows.append([])
            used = 0.0
        rows[-1].append(entry)
        used += width
    return rows


def _draw_legend(
    draw: ImageDraw.ImageDraw, image: Image.Image, schedule: DaySchedule, y: int
) -> None:
    font = fonts.text(theme.LEGEND_SIZE, 500)
    radius = 5
    x = theme.MARGIN

    for level, label in LEGEND:
        dot = _aa_dot(radius, STATE_COLOR[level])
        image.paste(dot, (x, y - radius), dot)
        x += radius * 2 + 9
        draw.text((x, y), label, font=font, fill=theme.LEGEND_TEXT, anchor="lm")
        x += round(draw.textlength(label, font=font)) + 26

    if schedule.updated_label:
        draw.text(
            (theme.CONTENT_RIGHT, y),
            f"оновлено {schedule.updated_label}",
            font=fonts.mono(theme.LEGEND_SIZE - 2, 400),
            fill=theme.TEXT_MINOR,
            anchor="rm",
        )


# ── entry point ───────────────────────────────────────────────────────────


def render_day_png(schedule: DaySchedule, *, now: datetime | None = None) -> bytes:
    moment = now or now_kyiv()

    plan = _plan_outages(schedule)
    # A day with nothing to list drops that row instead of leaving a hole.
    extra = plan.extra_rows if plan else -1
    height = theme.HEIGHT_BASE + extra * theme.OUTAGES_ROW_H

    image = _render_shapes(schedule, height)
    draw = ImageDraw.Draw(image)

    _draw_header(draw, schedule)
    _draw_hero(draw, build_headline(schedule, moment))
    _draw_axis(draw)
    if schedule.is_today:
        _draw_now(draw, moment)
    _draw_outages(draw, plan)
    _draw_legend(draw, image, schedule, height - theme.LEGEND_FROM_BOTTOM)

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
