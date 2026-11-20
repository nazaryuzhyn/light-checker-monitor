"""Telegram handlers. Each one resolves state, then delegates copy to texts."""

import asyncio
import contextlib
import logging
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import partial

from telegram import InputMediaPhoto, Message, Update
from telegram.constants import ChatAction
from telegram.error import BadRequest, TelegramError
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
from app.core.timeutil import now_kyiv
from app.database import async_session
from app.services.schedule import DaySchedule, render_day_png
from app.services.schedule.source import Day, fetch_raw, parse_day
from app.services.subscriber import add_subscriber, remove_subscriber
from app.state import power_state

log = logging.getLogger(__name__)

# Telegram sometimes takes longer than the 5 s default to take a photo in.
PHOTO_TIMEOUT = 20
MAX_REMEMBERED_PHOTOS = 32

# One worker: renders share cached FreeType fonts, not documented as thread-safe.
_renderer = ThreadPoolExecutor(max_workers=1, thread_name_prefix="render")

# Telegram keeps every uploaded photo; sending its file_id again skips the upload.
_file_ids: OrderedDict[tuple, str] = OrderedDict()


def _photo_key(schedule: DaySchedule, moment: datetime) -> tuple:
    # Today's picture marks the current minute; tomorrow's changes only with the feed.
    return schedule, moment.strftime("%H:%M") if schedule.is_today else None


async def _render(schedule: DaySchedule, moment: datetime) -> bytes:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_renderer, partial(render_day_png, schedule, now=moment))


def _remember(key: tuple, sent: Message | bool) -> None:
    if isinstance(sent, bool) or not sent.photo:
        return
    _file_ids[key] = sent.photo[-1].file_id
    _file_ids.move_to_end(key)
    if len(_file_ids) > MAX_REMEMBERED_PHOTOS:
        _file_ids.popitem(last=False)


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
    schedule, problem = await _resolve("today")
    if schedule is None:
        # Today may be unpublished while tomorrow already is.
        schedule, _ = await _resolve("tomorrow")
    if schedule is None:
        await message.reply_text(problem, parse_mode="Markdown")
        return

    moment = now_kyiv()
    key = _photo_key(schedule, moment)
    photo = _file_ids.get(key)
    if photo is None:
        with contextlib.suppress(TelegramError):
            await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        photo = await _render(schedule, moment)

    day: Day = "today" if schedule.is_today else "tomorrow"
    sent = await message.reply_photo(
        photo=photo,
        caption=texts.schedule_caption(schedule, now=moment),
        parse_mode="Markdown",
        reply_markup=day_switch_keyboard(day),
        read_timeout=PHOTO_TIMEOUT,
    )
    _remember(key, sent)


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
    moment = now_kyiv()
    key = _photo_key(schedule, moment)
    try:
        sent = await query.edit_message_media(
            media=InputMediaPhoto(
                media=_file_ids.get(key) or await _render(schedule, moment),
                caption=texts.schedule_caption(schedule, now=moment),
                parse_mode="Markdown",
            ),
            reply_markup=day_switch_keyboard(day),
            read_timeout=PHOTO_TIMEOUT,
        )
    except BadRequest as error:
        # "Message is not modified" is the common, harmless case here.
        log.debug("Could not update the schedule photo: %s", error)
        return
    _remember(key, sent)
