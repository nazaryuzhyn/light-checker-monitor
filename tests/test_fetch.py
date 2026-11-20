import asyncio

import httpx

from app.services.schedule import source


def test_a_failed_fetch_is_not_retried_on_every_request(monkeypatch):
    calls = 0

    class DownClient:
        def __init__(self, **_):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def get(self, url):
            nonlocal calls
            calls += 1
            raise httpx.ConnectTimeout("feed is down")

    monkeypatch.setattr(source.httpx, "AsyncClient", DownClient)

    assert asyncio.run(source.fetch_raw()) is None
    assert asyncio.run(source.fetch_raw()) is None
    assert calls == 1

    monkeypatch.setattr(source, "_failed_at", source._failed_at - source.RETRY_AFTER_FAILURE)
    asyncio.run(source.fetch_raw())
    assert calls == 2
