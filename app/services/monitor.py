import asyncio
import logging
import time

from telegram import Bot

from app.bot.notifications import notify_all
from app.config import settings
from app.services.schedule import fetch_schedule, get_next_on_time
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
                log.warning("No ping for %.0fs (missed %d/%d)", elapsed, missed_checks, required_misses)
                if missed_checks < required_misses:
                    continue
                missed_checks = 0
                power_state.power_is_on = False
                power_state.power_off_time = time.time()
                await power_state.save_to_db()
                msg = "🔴 *Світло зникло!*\n\nESP перестав виходити на зв'язок. ☹️"
                data = await fetch_schedule()
                if data:
                    next_on = get_next_on_time(data)
                    if next_on:
                        msg += f"\n\n🕐 Планове увімкнення: {next_on}"
                await notify_all(bot, msg)

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
            else:
                missed_checks = 0
        except Exception:
            log.exception("monitor_power error")
