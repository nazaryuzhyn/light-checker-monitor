import asyncio
import logging
import time

from telegram import Bot

from app.bot.notifications import notify_all
from app.config import settings
from app.state import power_state

log = logging.getLogger(__name__)


async def monitor_power(bot: Bot) -> None:
    await asyncio.sleep(15)
    missed_checks = 0
    required_misses = 3
    while True:
        await asyncio.sleep(5)
        try:
            elapsed = time.time() - power_state.last_ping

            if elapsed > settings.PING_TIMEOUT and power_state.power_is_on:
                missed_checks += 1
                if missed_checks < required_misses:
                    continue
                missed_checks = 0
                power_state.power_is_on = False
                power_state.power_off_time = time.time()
                await power_state.save_to_db()
                await notify_all(
                    bot, "🔴 *Світло зникло!*\n\nESP перестав виходити на зв'язок. ☹️"
                )

            elif elapsed <= settings.PING_TIMEOUT and not power_state.power_is_on:
                missed_checks = 0
                power_state.power_is_on = True
                power_state.power_on_time = time.time()
                duration = int((power_state.power_on_time - power_state.power_off_time) / 60)
                hours = duration // 60
                minutes = duration % 60
                dur_text = f"{hours} год {minutes} хв" if hours > 0 else f"{minutes} хв"
                await power_state.save_to_db()
                await notify_all(bot, f"💡 *Світло з'явилось!*\n\nНе було: {dur_text}")
        except Exception:
            log.exception("monitor_power error")
