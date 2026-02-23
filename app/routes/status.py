import time

from fastapi import APIRouter

from app.database import async_session
from app.services.subscriber import get_all_subscribers
from app.state import power_state

router = APIRouter()


@router.get("/status")
async def status():
    async with async_session() as session:
        subscribers = await get_all_subscribers(session)

    return {
        "power_is_on": power_state.power_is_on,
        "last_ping_ago_seconds": int(time.time() - power_state.last_ping),
        "subscribers": len(subscribers),
    }
