import asyncio
from unittest.mock import AsyncMock

from conftest import midnight_today_ts

from app.bot import handlers
from app.services.schedule.source import SECONDS_PER_DAY

HOURS_ALL_ON = {str(h): "yes" for h in range(1, 25)}


def feed_with(data: dict) -> dict:
    return {"fact": {"today": str(midnight_today_ts()), "update": "20.11.2026 10:36", "data": data}}


def test_schedule_button_opens_tomorrow_when_today_is_missing(monkeypatch):
    tomorrow_key = str(midnight_today_ts() + SECONDS_PER_DAY)
    raw = feed_with({tomorrow_key: {"GPV5.2": dict(HOURS_ALL_ON)}})
    monkeypatch.setattr(handlers, "fetch_raw", AsyncMock(return_value=raw))
    message = AsyncMock()

    asyncio.run(handlers._reply_schedule(message))

    buttons = message.reply_photo.await_args.kwargs["reply_markup"].inline_keyboard[0]
    assert [b.text for b in buttons] == ["Сьогодні", "● Завтра"]


def test_schedule_button_explains_when_neither_day_is_published(monkeypatch):
    monkeypatch.setattr(handlers, "fetch_raw", AsyncMock(return_value=feed_with({})))
    message = AsyncMock()

    asyncio.run(handlers._reply_schedule(message))

    message.reply_photo.assert_not_awaited()
    assert "ще не опубліковано" in message.reply_text.await_args.args[0]
