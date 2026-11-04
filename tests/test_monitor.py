import asyncio
from unittest.mock import AsyncMock

from app.services import monitor


def test_outage_is_counted_from_the_last_ping(monkeypatch):
    """The alert fires ~67 s into the silence; the restore must not report "0 хв"."""
    state = monitor.power_state
    monkeypatch.setattr(state, "power_is_on", True)
    monkeypatch.setattr(state, "last_ping", 1_000.0)
    monkeypatch.setattr(state, "power_off_time", None)
    monkeypatch.setattr(state, "power_on_time", None)
    monkeypatch.setattr(state, "save_to_db", AsyncMock())
    notify = AsyncMock()
    monkeypatch.setattr(monitor, "notify_all", notify)
    monkeypatch.setattr(monitor, "get_day", AsyncMock(return_value=None))
    bot = AsyncMock()

    monkeypatch.setattr(monitor.time, "time", lambda: 1_067.0)
    asyncio.run(monitor._announce_outage(bot))
    monkeypatch.setattr(monitor.time, "time", lambda: 1_077.0)
    asyncio.run(monitor._announce_restore(bot))

    assert state.power_off_time == 1_000.0
    assert "Не було 1 хв" in notify.await_args.args[1]
