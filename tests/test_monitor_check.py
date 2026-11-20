import asyncio
from unittest.mock import AsyncMock

import pytest

from app.services import monitor

TIMEOUT = monitor.settings.PING_TIMEOUT


@pytest.fixture
def check(monkeypatch):
    """Run one monitor check at a given silence; returns (misses, alerts sent)."""
    state = monitor.power_state
    monkeypatch.setattr(state, "power_is_on", True)
    monkeypatch.setattr(state, "power_off_time", None)
    monkeypatch.setattr(state, "power_on_time", None)
    monkeypatch.setattr(state, "save_to_db", AsyncMock())
    monkeypatch.setattr(monitor, "get_day", AsyncMock(return_value=None))
    sent: list[str] = []

    async def notify(_bot, text):
        sent.append(text)

    monkeypatch.setattr(monitor, "notify_all", notify)

    def run(silence: float, misses: int = 0) -> int:
        monkeypatch.setattr(state, "last_ping", 1_000.0)
        monkeypatch.setattr(monitor.time, "time", lambda: 1_000.0 + silence)
        return asyncio.run(monitor._check(AsyncMock(), misses))

    run.sent = sent
    return run


def test_three_misses_in_a_row_announce_the_outage(check):
    assert check(TIMEOUT + 1) == 1
    assert check(TIMEOUT + 6, misses=1) == 2
    assert check.sent == []
    assert check(TIMEOUT + 11, misses=2) == 0
    assert len(check.sent) == 1 and "Світло зникло" in check.sent[0]
    assert monitor.power_state.power_is_on is False


def test_a_fresh_ping_resets_the_counter(check):
    assert check(TIMEOUT + 1) == 1
    assert check(2, misses=1) == 0
    assert check.sent == []


def test_the_first_fresh_ping_after_an_outage_restores_once(check, monkeypatch):
    monkeypatch.setattr(monitor.power_state, "power_is_on", False)
    monkeypatch.setattr(monitor.power_state, "power_off_time", 400.0)

    check(2)
    check(3)

    assert len(check.sent) == 1 and "Світло зʼявилось" in check.sent[0]


def test_a_long_silence_while_already_off_sends_nothing(check, monkeypatch):
    monkeypatch.setattr(monitor.power_state, "power_is_on", False)

    assert check(TIMEOUT * 10) == 0
    assert check.sent == []
