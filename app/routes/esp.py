import logging

from fastapi import APIRouter, Depends

from app.deps import verify_api_key
from app.state import power_state

log = logging.getLogger(__name__)
router = APIRouter()

# ESP.getResetInfoPtr()->reason on the ESP8266.
RESET_REASONS = {
    0: "power on",
    1: "hardware watchdog",
    2: "exception",
    3: "software watchdog",
    4: "software restart",
    5: "deep-sleep wake",
    6: "external reset",
}


@router.get("/ping", dependencies=[Depends(verify_api_key)])
async def ping(
    # What the ESP went through since its last good ping. Older firmware sends
    # none of these, and the defaults keep it silent.
    boots: int = 0,
    wifi_down: int = 0,
    http_fail: int = 0,
    last_http: int | None = None,
    rst: int | None = None,
    rssi: int | None = None,
    up: int | None = None,
):
    await power_state.record_ping_and_save()
    log.info("Ping received")
    if boots or wifi_down or http_fail:
        log.warning(
            "ESP back after silence: boots=%d wifi_down=%d http_fail=%d "
            "last_http=%s reset=%s rssi=%s up=%ss",
            boots,
            wifi_down,
            http_fail,
            last_http,
            RESET_REASONS.get(rst, rst),
            rssi,
            up,
        )
    return {"status": "ok"}
