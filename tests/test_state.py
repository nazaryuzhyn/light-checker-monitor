import asyncio
import contextlib
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app import state


def test_restart_keeps_the_last_ping_from_the_database(monkeypatch):
    last_ping = datetime(2026, 11, 20, 11, 41, 50, tzinfo=timezone.utc)
    row = SimpleNamespace(
        power_is_on=True, last_ping_at=last_ping, power_off_at=None, power_on_at=None
    )
    monkeypatch.setattr(state, "async_session", contextlib.nullcontext)
    monkeypatch.setattr(state, "get_power_state", AsyncMock(return_value=row))
    manager = state.PowerStateManager()

    asyncio.run(manager.load_from_db())

    assert manager.last_ping == last_ping.timestamp()
