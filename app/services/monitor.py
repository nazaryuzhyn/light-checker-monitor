"""Background watcher that turns ESP silence into a power-outage notification."""

import asyncio
import logging
import time

from telegram import Bot

from app.bot import texts
from app.bot.notifications import notify_all
from app.config import settings
from app.services.schedule import get_day
from app.state import power_state

log = logging.getLogger(__name__)

STARTUP_GRACE = 15  # let the ESP report in before judging it
POLL_INTERVAL = 5
REQUIRED_MISSES = 3  # a single slow ping is not an outage


async def _announce_outage(bot: Bot) -> None:
    power_state.power_is_on = False
    power_state.power_off_time = time.time()
    await power_state.save_to_db()
    await notify_all(bot, texts.power_lost(await get_day("today")))


async def _announce_restore(bot: Bot) -> None:
    power_state.power_is_on = True
    power_state.power_on_time = time.time()
    minutes = int((power_state.power_on_time - (power_state.power_off_time or 0)) / 60)
    await power_state.save_to_db()
    await notify_all(bot, texts.power_restored(await get_day("today"), minutes))


async def _check(bot: Bot, misses: int) -> int:
    """Advance the miss counter, acting on a confirmed state change. Returns the counter."""
    elapsed = time.time() - power_state.last_ping

    if elapsed > settings.PING_TIMEOUT and power_state.power_is_on:
        misses += 1
        log.warning(
            "No ping for %.0fs (missed %d/%d)", elapsed, misses, REQUIRED_MISSES
        )
        if misses < REQUIRED_MISSES:
            return misses
        await _announce_outage(bot)
        return 0

    if elapsed <= settings.PING_TIMEOUT and not power_state.power_is_on:
        await _announce_restore(bot)

    return 0


async def monitor_power(bot: Bot) -> None:
    await asyncio.sleep(STARTUP_GRACE)
    misses = 0
    while True:
        await asyncio.sleep(POLL_INTERVAL)
        try:
            misses = await _check(bot, misses)
        except Exception:
            log.exception("monitor_power iteration failed")
