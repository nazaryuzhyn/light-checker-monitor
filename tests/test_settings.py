import asyncio
import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sqlalchemy.dialects import postgresql

from app.bot import handlers
from app.bot.keyboard import settings_keyboard
from app.models import Notice
from app.services import subscriber


def _labels(markup) -> list[str]:
    return [row[0].text for row in markup.inline_keyboard]


def test_the_keyboard_shows_each_notice_state():
    assert _labels(settings_keyboard({Notice.REMINDERS})) == [
        "✅ 📅 Зміни графіка",
        "🔕 ⏰ Нагадування перед відключенням",
    ]


def test_a_tap_toggles_the_notice_and_redraws_the_keyboard(monkeypatch):
    toggle = AsyncMock(return_value=False)
    monkeypatch.setattr(handlers, "async_session", contextlib.nullcontext)
    monkeypatch.setattr(handlers, "toggle_notice", toggle)
    monkeypatch.setattr(handlers, "get_muted", AsyncMock(return_value={Notice.SCHEDULE_CHANGES}))
    query = AsyncMock(data=f"settings:{Notice.SCHEDULE_CHANGES}")
    update = SimpleNamespace(callback_query=query, effective_chat=SimpleNamespace(id=42))

    asyncio.run(handlers.settings_callback(update, None))

    assert toggle.await_args.args[1:] == (42, Notice.SCHEDULE_CHANGES)
    assert query.answer.await_args.args[0] == "📅 Зміни графіка: вимкнено"
    markup = query.edit_message_reply_markup.await_args.kwargs["reply_markup"]
    assert _labels(markup)[0] == "🔕 📅 Зміни графіка"


def test_an_optional_notice_excludes_chats_that_muted_it():
    captured = {}

    class Session:
        async def execute(self, query):
            captured["sql"] = str(query.compile(dialect=postgresql.dialect()))
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=list))

    asyncio.run(subscriber.get_all_subscribers(Session(), Notice.REMINDERS))

    assert "NOT (EXISTS" in captured["sql"]
    assert "muted_notices.notice" in captured["sql"]
