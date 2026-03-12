import time
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.bot.keyboard import BTN_CHECK, BTN_DETAILS, BTN_SCHEDULE, get_keyboard, get_status_text
from app.services.schedule import fetch_schedule, format_schedule_text
from app.database import async_session
from app.services.subscriber import add_subscriber, remove_subscriber
from app.state import power_state

KYIV_TZ = ZoneInfo("Europe/Kyiv")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id

    async with async_session() as session:
        is_new = await add_subscriber(session, chat_id)

    greeting = (
        "👋 Вітаю! Ти підписаний на сповіщення про світло."
        if is_new
        else "👋 Ти вже підписаний!"
    )

    await update.message.reply_text(
        f"{greeting}\n\n🏠 *Моніторинг світла*",
        reply_markup=get_keyboard(),
        parse_mode="Markdown",
    )


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id

    async with async_session() as session:
        await remove_subscriber(session, chat_id)

    await update.message.reply_text(
        "🔕 Ти відписаний від сповіщень.\n\nНапиши `/start` щоб підписатись знову."
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message.text

    if msg == BTN_CHECK:
        await update.message.reply_text(
            text=get_status_text(), parse_mode="Markdown"
        )

    elif msg == BTN_DETAILS:
        last = datetime.fromtimestamp(power_state.last_ping, tz=KYIV_TZ).strftime(
            "%d.%m %H:%M:%S"
        )
        status = (
            "✅ Електроенергія є"
            if power_state.power_is_on
            else "❌ Електроенергії немає"
        )
        text = (
            f"📊 *Детальна інформація*\n\n"
            f"Стан: {status}\n"
            f"Останній пінг: {last}\n"
        )
        if not power_state.power_is_on and power_state.power_off_time:
            off = datetime.fromtimestamp(
                power_state.power_off_time, tz=KYIV_TZ
            ).strftime("%d.%m %H:%M")
            duration = int((time.time() - power_state.power_off_time) / 60)
            text += f"\nВідключено: {off}\nТривалість: {duration} хв"

        await update.message.reply_text(text=text, parse_mode="Markdown")

    elif msg == BTN_SCHEDULE:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📅 На сьогодні", callback_data="schedule_today"),
                InlineKeyboardButton("📅 На завтра", callback_data="schedule_tomorrow"),
            ]
        ])
        await update.message.reply_text(
            "Обери день:", reply_markup=keyboard
        )


async def schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    day = "today" if query.data == "schedule_today" else "tomorrow"
    data = await fetch_schedule()
    if data:
        text = format_schedule_text(data, day=day)
    else:
        text = "⚠️ Не вдалось отримати графік"
    await query.edit_message_text(text=text, parse_mode="Markdown")
