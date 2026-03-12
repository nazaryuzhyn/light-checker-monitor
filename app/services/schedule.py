import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from app.config import settings

log = logging.getLogger(__name__)

KYIV_TZ = ZoneInfo("Europe/Kyiv")
SCHEDULE_URL = (
    "https://raw.githubusercontent.com/yaroslav2901/OE_OUTAGE_DATA"
    "/main/data/Ternopiloblenerho.json"
)

STATUS_ICONS = {
    "yes": "✅",
    "no": "❌",
    "mfirst": "🟡",
    "msecond": "🟠",
}


async def fetch_schedule() -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(SCHEDULE_URL)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        log.exception("Failed to fetch outage schedule")
        return None


def _get_day_key(data: dict, day: str = "today") -> str | None:
    fact = data.get("fact", {})
    today_key = fact.get("today")
    if not today_key:
        return None
    if day == "tomorrow":
        return str(int(today_key) + 86400)
    return str(today_key)


def format_schedule_text(data: dict, day: str = "today") -> str:
    fact = data.get("fact", {})
    day_key = _get_day_key(data, day)
    if not day_key:
        return "⚠️ Графік недоступний"

    day_data = fact.get("data", {}).get(day_key, {})
    if not day_data:
        label = "сьогодні" if day == "today" else "завтра"
        return f"⚠️ Графік на {label} не знайдено"

    day_date = datetime.fromtimestamp(int(day_key), tz=KYIV_TZ)
    label = "сьогодні" if day == "today" else "завтра"
    lines = [f"📅 *Графік на {label} ({day_date.strftime('%d.%m.%Y')})*\n"]

    for group in settings.OUTAGE_GROUPS:
        hours = day_data.get(group)
        if not hours:
            lines.append(f"\n*{group}*: дані відсутні")
            continue

        lines.append(f"\n*{group}:*")
        line = ""
        for h in range(1, 25):
            status = hours.get(str(h), "yes")
            icon = STATUS_ICONS.get(status, "❓")
            line += f"{icon}"
            if h % 6 == 0:
                start_h = h - 5
                lines.append(f"`{start_h:02d}-{h:02d}` {line}")
                line = ""

    lines.append(f"\nОновлено: {fact.get('update', '?')}")
    lines.append("\n✅ є | ❌ немає | 🟡🟠 можливо")
    return "\n".join(lines)


def get_next_on_time(data: dict) -> str | None:
    fact = data.get("fact", {})
    today_key = _get_today_key(data)
    if not today_key:
        return None

    day_data = fact.get("data", {}).get(today_key, {})
    if not day_data:
        return None

    now = datetime.now(KYIV_TZ)
    current_hour = now.hour + 1  # schedule uses 1-24

    for group in settings.OUTAGE_GROUPS:
        hours = day_data.get(group)
        if not hours:
            continue

        for h in range(current_hour, 25):
            status = hours.get(str(h), "yes")
            if status == "yes":
                on_time = f"{h - 1:02d}:00"
                return f"~{on_time} ({group})"

    return None
