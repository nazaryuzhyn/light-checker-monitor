"""Time helpers shared by the bot, the monitor and the schedule renderer."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

KYIV_TZ = ZoneInfo("Europe/Kyiv")

MONTHS_GENITIVE = (
    "січня", "лютого", "березня", "квітня", "травня", "червня",
    "липня", "серпня", "вересня", "жовтня", "листопада", "грудня",
)
WEEKDAYS = (
    "понеділок", "вівторок", "середа", "четвер",
    "пʼятниця", "субота", "неділя",
)


def now_kyiv() -> datetime:
    return datetime.now(KYIV_TZ)


def to_kyiv(timestamp: float) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=KYIV_TZ)


def plural(count: int, forms: tuple[str, str, str]) -> str:
    """Ukrainian plural form: (1, 2-4, 5+). E.g. ('година', 'години', 'годин')."""
    tail_100 = count % 100
    if 11 <= tail_100 <= 14:
        return forms[2]
    tail = count % 10
    if tail == 1:
        return forms[0]
    if 2 <= tail <= 4:
        return forms[1]
    return forms[2]


def format_duration(minutes: int) -> str:
    """Compact duration: '45 хв', '2 год', '3 год 30 хв'."""
    minutes = max(0, int(minutes))
    hours, mins = divmod(minutes, 60)
    if not hours:
        return f"{mins} хв"
    if not mins:
        return f"{hours} год"
    return f"{hours} год {mins} хв"


def format_duration_long(minutes: int) -> str:
    """Spelled-out duration for prose: '45 хвилин', '3 години 30 хвилин'."""
    minutes = max(0, int(minutes))
    hours, mins = divmod(minutes, 60)
    parts = []
    if hours:
        parts.append(f"{hours} {plural(hours, ('година', 'години', 'годин'))}")
    if mins or not hours:
        parts.append(f"{mins} {plural(mins, ('хвилина', 'хвилини', 'хвилин'))}")
    return " ".join(parts)


def format_duration_display(minutes: int) -> str:
    """Duration set as a headline: '7 годин', '45 хвилин', '3 год 30 хв'."""
    minutes = max(0, int(minutes))
    hours, mins = divmod(minutes, 60)
    if not hours:
        return f"{mins} {plural(mins, ('хвилина', 'хвилини', 'хвилин'))}"
    if not mins:
        return f"{hours} {plural(hours, ('година', 'години', 'годин'))}"
    return f"{hours} год {mins} хв"


def format_clock(moment: datetime) -> str:
    return moment.strftime("%H:%M")


def format_day(day: date) -> str:
    """'14 серпня'"""
    return f"{day.day} {MONTHS_GENITIVE[day.month - 1]}"


def format_weekday(day: date) -> str:
    return WEEKDAYS[day.weekday()]
