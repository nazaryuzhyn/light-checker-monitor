"""Background watcher that tells subscribers about schedule changes and upcoming outages."""

import asyncio
import logging
from datetime import date, datetime, time, timedelta

from telegram import Bot

from app.bot import texts
from app.bot.notifications import notify_all
from app.core.timeutil import KYIV_TZ, now_kyiv
from app.services.schedule import DaySchedule
from app.services.schedule.models import MINUTES_PER_SLOT, Outage, PowerLevel
from app.services.schedule.source import fetch_raw, parse_day
from app.state import power_state

log = logging.getLogger(__name__)

CHECK_INTERVAL = 60
REMINDER_LEAD = timedelta(minutes=30)

Levels = tuple[PowerLevel, ...]


def outage_start(schedule: DaySchedule, outage: Outage) -> datetime:
    midnight = datetime.combine(schedule.day, time(), tzinfo=KYIV_TZ)
    return midnight + timedelta(minutes=outage.start * MINUTES_PER_SLOT)


def schedule_notices(seen: dict[date, Levels], schedules: list[DaySchedule]) -> list[str]:
    """Messages for days that appeared or changed since the last look; updates `seen`."""
    notices = []
    for schedule in schedules:
        before = seen.get(schedule.day)
        if before is None:
            notices.append(texts.schedule_published(schedule))
        elif before != schedule.levels:
            notices.append(texts.schedule_changed(schedule))
        seen[schedule.day] = schedule.levels
    return notices


def due_reminders(schedules: list[DaySchedule], since: datetime, now: datetime) -> list[Outage]:
    """Outages whose reminder time fell between the previous check and this one.

    An outage that has already begun is skipped: after a long gap between checks a
    "soon" would come too late.
    """
    # Compared as instants: with one tzinfo Python compares wall clocks, and the
    # hour repeated when clocks go back would remind twice.
    due = []
    for schedule in schedules:
        for outage in schedule.outages:
            starts = outage_start(schedule, outage).timestamp()
            opens = starts - REMINDER_LEAD.total_seconds()
            if since.timestamp() < opens <= now.timestamp() < starts:
                due.append(outage)
    return due


async def watch_schedule(bot: Bot) -> None:
    seen: dict[date, Levels] | None = None
    # Starting from the start time means a restart never repeats a reminder.
    checked_at = now_kyiv()
    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        try:
            raw = await fetch_raw()
            if raw is None:
                continue  # a failed download says nothing about the schedule
            schedules = [s for s in (parse_day(raw, "today"), parse_day(raw, "tomorrow")) if s]

            if seen is None:
                seen = {s.day: s.levels for s in schedules}  # first look after a start
            else:
                for notice in schedule_notices(seen, schedules):
                    await notify_all(bot, notice)

            now = now_kyiv()
            due = due_reminders(schedules, checked_at, now)
            checked_at = now
            # Already dark: "an outage is coming" would only confuse.
            if power_state.power_is_on:
                for outage in due:
                    await notify_all(bot, texts.outage_reminder(outage))

            seen = {day: levels for day, levels in seen.items() if day >= now.date()}
        except Exception:
            log.exception("watch_schedule iteration failed")
