import os
from datetime import date, datetime, time

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("ESP_API_KEY", "test-key")
os.environ.setdefault("OUTAGE_GROUPS", '["GPV5.2"]')

import pytest  # noqa: E402

from app.core.timeutil import KYIV_TZ  # noqa: E402
from app.services.schedule.models import DaySchedule, PowerLevel  # noqa: E402

ON, OFF, MAYBE = PowerLevel.ON, PowerLevel.OFF, PowerLevel.MAYBE


def levels(*pattern: tuple[PowerLevel, float]) -> tuple[PowerLevel, ...]:
    """levels((ON, 8), (OFF, 3), (ON, 13)) → 48 half-hour slots."""
    out: list[PowerLevel] = []
    for level, hours in pattern:
        out.extend([level] * int(hours * 2))
    assert len(out) == 48, f"expected 48 slots, got {len(out)}"
    return tuple(out)


def schedule(*pattern: tuple[PowerLevel, float], is_today: bool = True) -> DaySchedule:
    return DaySchedule(
        day=date(2026, 8, 14),
        group="GPV5.2",
        levels=levels(*pattern),
        updated_at="14.08.2026 07:40",
        is_today=is_today,
    )


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 8, 14, hour, minute, tzinfo=KYIV_TZ)


def midnight_today_ts() -> int:
    return int(datetime.combine(date.today(), time(0, 0), tzinfo=KYIV_TZ).timestamp())


@pytest.fixture(autouse=True)
def _clear_feed_cache():
    from app.services.schedule.source import reset_cache

    reset_cache()
    yield
    reset_cache()
