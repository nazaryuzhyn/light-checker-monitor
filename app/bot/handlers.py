"""Telegram handlers. Each one resolves state, then delegates copy to texts."""

import logging
from collections.abc import Awaitable, Callable
from io import BytesIO

from telegram import InputMediaPhoto, Message, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from app.bot import texts
from app.bot.keyboard import (
    BTN_CHECK,
    BTN_DETAILS,
    BTN_SCHEDULE,
    DAY_BY_CALLBACK,
    day_switch_keyboard,
    main_keyboard,
)
from app.database import async_session
from app.services.schedule import DaySchedule, render_day_png
from app.services.schedule.source import Day, fetch_raw, parse_day
from app.services.subscriber import add_subscriber, remove_subscriber
from app.state import power_state

log = logging.getLogger(__name__)


async def _resolve(day: Day) -> tuple[DaySchedule | None, str | None]:
    """Return the day's schedule, or the reason there is nothing to show."""
    raw = await fetch_raw()
    if raw is None:
        return None, texts.schedule_unavailable()

    schedule = parse_day(raw, day)
    if schedule is None:
        return None, texts.schedule_missing(day)
    return schedule, None


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with async_session() as session:
        is_new = await add_subscriber(session, update.effective_chat.id)

    await update.message.reply_text(
        texts.greeting(is_new), reply_markup=main_keyboard(), parse_mode="Markdown"
    )


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with async_session() as session:
        await remove_subscriber(session, update.effective_chat.id)

    await update.message.reply_text(texts.farewell())


async def _reply_status(message: Message) -> None:
    await message.reply_text(texts.power_status(power_state), parse_mode="Markdown")


async def _reply_details(message: Message) -> None:
    await message.reply_text(texts.power_details(power_state), parse_mode="Markdown")


async def _reply_schedule(message: Message) -> None:
    day: Day = "today"
    schedule, problem = await _resolve(day)
    if schedule is None:
        await message.reply_text(problem, parse_mode="Markdown")
        return

    await message.reply_photo(
        photo=BytesIO(render_day_png(schedule)),
        caption=texts.schedule_caption(schedule),
        parse_mode="Markdown",
        reply_markup=day_switch_keyboard(day),
    )


BUTTONS: dict[str, Callable[[Message], Awaitable[None]]] = {
    BTN_CHECK: _reply_status,
    BTN_DETAILS: _reply_details,
    BTN_SCHEDULE: _reply_schedule,
}


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    action = BUTTONS.get(update.message.text)
    if action:
        await action(update.message)


async def schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    day = DAY_BY_CALLBACK.get(query.data)
    if day is None:
        await query.answer()
        return

    schedule, _ = await _resolve(day)
    if schedule is None:
        await query.answer(texts.schedule_missing_short(day), show_alert=True)
        return

    await query.answer()
    try:
        await query.edit_message_media(
            media=InputMediaPhoto(
                media=BytesIO(render_day_png(schedule)),
                caption=texts.schedule_caption(schedule),
                parse_mode="Markdown",
            ),
            reply_markup=day_switch_keyboard(day),
        )
    except BadRequest as error:
        # "Message is not modified" is the common, harmless case here.
        log.debug("Could not update the schedule photo: %s", error)
