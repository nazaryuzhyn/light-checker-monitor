"""Keyboards and the callback vocabulary they speak."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from app.services.schedule.source import Day

BTN_CHECK = "🔍 Перевірити стан"
BTN_DETAILS = "📊 Детальніше"
BTN_SCHEDULE = "📅 Графік"

CALLBACK_PREFIX = "schedule:"
DAY_BY_CALLBACK: dict[str, Day] = {
    f"{CALLBACK_PREFIX}today": "today",
    f"{CALLBACK_PREFIX}tomorrow": "tomorrow",
}


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[BTN_CHECK, BTN_DETAILS], [BTN_SCHEDULE]],
        resize_keyboard=True,
    )


def day_switch_keyboard(current: Day) -> InlineKeyboardMarkup:
    """Both days stay one tap away; the day on screen is marked."""
    labels: dict[Day, str] = {"today": "Сьогодні", "tomorrow": "Завтра"}
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"● {label}" if day == current else label,
                    callback_data=f"{CALLBACK_PREFIX}{day}",
                )
                for day, label in labels.items()
            ]
        ]
    )
