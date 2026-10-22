import logging
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes import esp


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(esp.power_state, "record_ping_and_save", AsyncMock())
    app = FastAPI()
    app.include_router(esp.router)
    return TestClient(app)


def _reports(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]


def test_plain_ping_logs_no_report(client, caplog):
    """Older firmware sends no diagnostics and must not look like trouble."""
    with caplog.at_level(logging.INFO):
        response = client.get("/ping", params={"api_key": "test-key"})

    assert response.status_code == 200
    assert _reports(caplog) == []


def test_quiet_counters_log_no_report(client, caplog):
    params = {"api_key": "test-key", "boots": 0, "wifi_down": 0, "http_fail": 0,
              "last_http": 0, "rst": 4, "rssi": -60, "up": 86400}
    with caplog.at_level(logging.INFO):
        client.get("/ping", params=params)

    assert _reports(caplog) == []


def test_report_after_silence(client, caplog):
    params = {"api_key": "test-key", "boots": 7, "wifi_down": 0, "http_fail": 164,
              "last_http": -1, "rst": 4, "rssi": -58, "up": 12}
    with caplog.at_level(logging.INFO):
        client.get("/ping", params=params)

    assert _reports(caplog) == [
        "ESP back after silence: boots=7 wifi_down=0 http_fail=164 "
        "last_http=-1 reset=software restart rssi=-58 up=12s"
    ]


def test_unknown_reset_reason_is_kept_as_code(client, caplog):
    params = {"api_key": "test-key", "boots": 1, "rst": 42}
    with caplog.at_level(logging.INFO):
        client.get("/ping", params=params)

    assert "reset=42" in _reports(caplog)[0]


def test_ping_requires_key(client):
    assert client.get("/ping").status_code == 401
