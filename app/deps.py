from fastapi import Header, HTTPException, Query

from app.config import settings


async def verify_api_key(
    api_key: str | None = Query(None),
    x_api_key: str | None = Header(None),
) -> None:
    key = api_key or x_api_key
    if not key or key != settings.ESP_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
