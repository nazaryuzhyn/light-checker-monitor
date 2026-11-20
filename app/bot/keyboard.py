"""Keyboards and the callback vocabulary they speak."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from app.models import Notice
from app.services.schedule.source import Day

BTN_CHECK = "🔍 Перевірити стан"
BTN_DETAILS = "📊 Детальніше"
BTN_SCHEDULE = "📅 Графік"
BTN_SETTINGS = "⚙️ Налаштування"

CALLBACK_PREFIX = "schedule:"
DAY_BY_CALLBACK: dict[str, Day] = {
    f"{CALLBACK_PREFIX}today": "today",
    f"{CALLBACK_PREFIX}tomorrow": "tomorrow",
}

SETTINGS_PREFIX = "settings:"
NOTICE_BY_CALLBACK: dict[str, Notice] = {f"{SETTINGS_PREFIX}{n}": n for n in Notice}
NOTICE_LABELS: dict[Notice, str] = {
    Notice.SCHEDULE_CHANGES: "📅 Зміни графіка",
    Notice.REMINDERS: "⏰ Нагадування перед відключенням",
}


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[BTN_CHECK, BTN_DETAILS], [BTN_SCHEDULE, BTN_SETTINGS]],
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


def settings_keyboard(muted: set[Notice]) -> InlineKeyboardMarkup:
    """One toggle per optional notice; the mark shows its current state."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"{'🔕' if notice in muted else '✅'} {label}",
                    callback_data=f"{SETTINGS_PREFIX}{notice}",
                )
            ]
            for notice, label in NOTICE_LABELS.items()
        ]
    )
