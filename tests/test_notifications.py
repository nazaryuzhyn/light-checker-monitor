import asyncio
import contextlib
from unittest.mock import AsyncMock

from telegram.error import BadRequest, Forbidden, RetryAfter, TimedOut

from app.bot import notifications


def test_only_chats_that_are_gone_are_unsubscribed(monkeypatch):
    errors = {
        1: TimedOut(),
        2: Forbidden("bot was blocked by the user"),
        3: BadRequest("Chat not found"),
        4: BadRequest("Can't parse entities"),
        5: None,
    }

    async def send_message(chat_id, **_):
        if errors[chat_id]:
            raise errors[chat_id]

    removed = AsyncMock()
    monkeypatch.setattr(notifications.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(notifications, "async_session", contextlib.nullcontext)
    monkeypatch.setattr(notifications, "get_all_subscribers", AsyncMock(return_value=list(errors)))
    monkeypatch.setattr(notifications, "remove_subscribers", removed)
    bot = AsyncMock()
    bot.send_message.side_effect = send_message

    asyncio.run(notifications.notify_all(bot, "🔴 Світло зникло"))

    removed.assert_awaited_once()
    assert removed.await_args.args[1] == [2, 3]


def test_flood_control_waits_and_retries(monkeypatch):
    monkeypatch.setattr(notifications.asyncio, "sleep", AsyncMock())
    bot = AsyncMock()
    bot.send_message.side_effect = [RetryAfter(3), None]

    assert asyncio.run(notifications._send(bot, 1, "text")) is True
    assert bot.send_message.await_count == 2


def test_an_alert_still_goes_out_while_the_database_is_down(monkeypatch):
    monkeypatch.setattr(notifications, "_last_known_subscribers", [7])

    def broken_session():
        raise OSError("db down")

    monkeypatch.setattr(notifications, "async_session", broken_session)
    bot = AsyncMock()

    asyncio.run(notifications.notify_all(bot, "🔴 Світло зникло"))

    assert bot.send_message.await_args.kwargs["chat_id"] == 7


def test_a_network_blip_is_retried(monkeypatch):
    monkeypatch.setattr(notifications.asyncio, "sleep", AsyncMock())
    bot = AsyncMock()
    bot.send_message.side_effect = [TimedOut(), None]

    assert asyncio.run(notifications._send(bot, 1, "text")) is True
    assert bot.send_message.await_count == 2
