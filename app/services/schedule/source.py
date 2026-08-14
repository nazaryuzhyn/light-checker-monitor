"""Fetching and parsing the upstream outage feed."""

import asyncio
import logging
import time
from datetime import datetime
from typing import Literal

import httpx

from app.config import settings
from app.core.timeutil import KYIV_TZ, now_kyiv
from app.services.schedule.models import (
    SLOTS_PER_DAY,
    DaySchedule,
    PowerLevel,
)

log = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10
CACHE_TTL = 300  # the feed is refreshed a few times a day; polling it harder is waste

Day = Literal["today", "tomorrow"]
SECONDS_PER_DAY = 86400

# One hourly status from the feed expands into two half-hour slots.
_HOURLY_MAP: dict[str, tuple[PowerLevel, PowerLevel]] = {
    "yes": (PowerLevel.ON, PowerLevel.ON),
    "no": (PowerLevel.OFF, PowerLevel.OFF),
    "mfirst": (PowerLevel.MAYBE, PowerLevel.ON),
    "msecond": (PowerLevel.ON, PowerLevel.MAYBE),
}

_cached: dict | None = None
_cached_at: float = 0.0
_lock = asyncio.Lock()


async def fetch_raw(*, force: bool = False) -> dict | None:
    """Return the raw feed, reusing a recent response when possible."""
    global _cached, _cached_at

    async with _lock:
        fresh = _cached is not None and time.monotonic() - _cached_at < CACHE_TTL
        if fresh and not force:
            return _cached

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(settings.SCHEDULE_URL)
                response.raise_for_status()
                _cached = response.json()
                _cached_at = time.monotonic()
        except Exception:
            log.exception("Failed to fetch outage schedule")
            return _cached  # stale beats nothing

        return _cached


def primary_group() -> str | None:
    return settings.outage_group


def group_label(group: str) -> str:
    """'GPV5.2' → '5.2' — the number is what people actually know."""
    return group.removeprefix("GPV") or group


def _day_key(raw: dict, day: Day) -> str | None:
    """Feed key (a unix timestamp) for the requested day, if it is published."""
    fact = raw.get("fact") or {}
    today_key = fact.get("today")
    if not today_key:
        return None

    key_date = datetime.fromtimestamp(int(today_key), tz=KYIV_TZ).date()
    if key_date != now_kyiv().date():
        return None  # feed is stale — do not pass yesterday off as today

    if day == "today":
        return str(today_key)

    tomorrow_key = str(int(today_key) + SECONDS_PER_DAY)
    return tomorrow_key if tomorrow_key in (fact.get("data") or {}) else None


def _expand_hours(hours: dict) -> tuple[PowerLevel, ...]:
    levels: list[PowerLevel] = []
    for hour in range(1, 25):
        status = hours.get(str(hour), "yes")
        first, second = _HOURLY_MAP.get(status, (PowerLevel.ON, PowerLevel.ON))
        levels.append(first)
        levels.append(second)
    return tuple(levels)


def parse_day(raw: dict, day: Day = "today") -> DaySchedule | None:
    """Build a DaySchedule, or None when this day is not published for our group."""
    group = primary_group()
    if not group:
        log.warning("OUTAGE_GROUPS is empty — cannot resolve a schedule")
        return None

    key = _day_key(raw, day)
    if not key:
        return None

    hours = ((raw.get("fact") or {}).get("data") or {}).get(key, {}).get(group)
    if not hours:
        return None

    levels = _expand_hours(hours)
    if len(levels) != SLOTS_PER_DAY:
        log.warning("Unexpected slot count %d for %s", len(levels), key)
        return None

    return DaySchedule(
        day=datetime.fromtimestamp(int(key), tz=KYIV_TZ).date(),
        group=group,
        levels=levels,
        updated_at=(raw.get("fact") or {}).get("update", ""),
        is_today=day == "today",
    )


async def get_day(day: Day = "today", *, force: bool = False) -> DaySchedule | None:
    raw = await fetch_raw(force=force)
    return parse_day(raw, day) if raw else None


def reset_cache() -> None:
    """Drop the cached feed — used by tests."""
    global _cached, _cached_at
    _cached, _cached_at = None, 0.0


__all__ = [
    "Day",
    "SECONDS_PER_DAY",
    "fetch_raw",
    "get_day",
    "group_label",
    "parse_day",
    "primary_group",
    "reset_cache",
]
