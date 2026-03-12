from datetime import datetime
from zoneinfo import ZoneInfo

import time

from telegram import ReplyKeyboardMarkup

from app.state import power_state

KYIV_TZ = ZoneInfo("Europe/Kyiv")

BTN_CHECK = "🔍 Перевірити стан"
BTN_DETAILS = "📊 Детальніше"
BTN_SCHEDULE = "📅 Графік"


def get_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[BTN_CHECK, BTN_DETAILS], [BTN_SCHEDULE]],
        resize_keyboard=True,
    )


def get_status_text() -> str:
    if power_state.power_is_on:
        last = datetime.fromtimestamp(power_state.last_ping, tz=KYIV_TZ).strftime(
            "%H:%M:%S"
        )
        elapsed = int((time.time() - power_state.last_ping) / 60)
        ago_text = f"\n({elapsed} хв тому)" if elapsed > 0 else ""
        return f"✅ *Світло є.*\n\n⏰ Останній сигнал: {last}{ago_text}"
    else:
        off_time = datetime.fromtimestamp(
            power_state.power_off_time, tz=KYIV_TZ
        ).strftime("%H:%M")
        duration = int((time.time() - power_state.power_off_time) / 60)
        hours = duration // 60
        minutes = duration % 60
        dur_text = f"{hours} год {minutes} хв" if hours > 0 else f"{minutes} хв"
        return (
            f"❌ *Світла немає.*\n\n"
            f"⏰ Зникло о: {off_time}\n"
            f"⏳ Вже {dur_text} без світла"
        )
