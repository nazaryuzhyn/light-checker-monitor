import logging

from fastapi import APIRouter, Depends

from app.deps import verify_api_key
from app.state import power_state

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/ping", dependencies=[Depends(verify_api_key)])
async def ping():
    await power_state.record_ping_and_save()
    log.info("Ping received")
    return {"status": "ok"}
