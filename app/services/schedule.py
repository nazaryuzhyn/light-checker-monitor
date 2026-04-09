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

STATUS_LABELS = {
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

    # Verify the "today" key actually matches today's date
    key_date = datetime.fromtimestamp(int(today_key), tz=KYIV_TZ).date()
    actual_today = datetime.now(KYIV_TZ).date()

    if day == "today":
        if key_date != actual_today:
            return None
        return str(today_key)
    else:
        tomorrow_key = str(int(today_key) + 86400)
        if key_date != actual_today:
            return None
        # Check if tomorrow's data exists
        if tomorrow_key not in fact.get("data", {}):
            return None
        return tomorrow_key


def format_schedule_text(data: dict, day: str = "today") -> str:
    fact = data.get("fact", {})
    label = "сьогодні" if day == "today" else "завтра"
    day_key = _get_day_key(data, day)
    if not day_key:
        update = fact.get("update", "?")
        return f"⚠️ Графік на {label} ще не опубліковано\n\nОстаннє оновлення графіку: {update}"

    day_data = fact.get("data", {}).get(day_key, {})
    if not day_data:
        return f"⚠️ Графік на {label} не знайдено"

    day_date = datetime.fromtimestamp(int(day_key), tz=KYIV_TZ)

    groups = settings.OUTAGE_GROUPS
    group_data = {g: day_data.get(g) for g in groups}

    if len(groups) >= 2 and all(group_data.values()):
        header = "         " + "  ".join(f"{g:>6}" for g in groups)
        lines = [f"📅 *Графік на {label} ({day_date.strftime('%d.%m.%Y')})*\n"]
        lines.append(f"`{header}`")
        for h in range(1, 25):
            end = "00" if h == 24 else f"{h:02d}"
            row = f"{h - 1:02d}-{end}    "
            for g in groups:
                status = group_data[g].get(str(h), "yes")
                icon = STATUS_LABELS.get(status, "❓")
                row += f" {icon}    "
            lines.append(f"`{row.rstrip()}`")
    else:
        lines = [f"📅 *Графік на {label} ({day_date.strftime('%d.%m.%Y')})*\n"]
        for g in groups:
            hours = group_data.get(g)
            if not hours:
                lines.append(f"\n*{g}*: дані відсутні")
                continue
            for h in range(1, 25):
                status = hours.get(str(h), "yes")
                icon = STATUS_LABELS.get(status, "❓")
                end = "00:00" if h == 24 else f"{h:02d}:00"
                lines.append(f"`{h - 1:02d}:00-{end}` {icon}")

    lines.append(f"\nГрафік оновлено: {fact.get('update', '?')}")
    return "\n".join(lines)


def _get_active_group(day_data: dict, current_hour: int) -> str | None:
    """Determine which group is currently causing the outage."""
    for group in settings.OUTAGE_GROUPS:
        hours = day_data.get(group)
        if not hours:
            continue
        status = hours.get(str(current_hour), "yes")
        if status in ("no", "mfirst", "msecond"):
            return group
    return None


def get_next_on_time(data: dict) -> str | None:
    fact = data.get("fact", {})
    today_key = _get_day_key(data)
    if not today_key:
        return None

    day_data = fact.get("data", {}).get(today_key, {})
    if not day_data:
        return None

    now = datetime.now(KYIV_TZ)
    current_hour = now.hour + 1  # schedule uses 1-24
    next_hour = current_hour + 1  # skip current slot — power is already off now

    active_group = _get_active_group(day_data, current_hour)
    search_groups = [active_group] if active_group else settings.OUTAGE_GROUPS

    for group in search_groups:
        hours = day_data.get(group)
        if not hours:
            continue

        for h in range(next_hour, 25):
            status = hours.get(str(h), "yes")
            if status != "no":
                return f"{h - 1:02d}:00-{h - 1:02d}:30"

    return None


def get_next_off_text(data: dict) -> str:
    fact = data.get("fact", {})
    today_key = _get_day_key(data)
    if not today_key:
        return "🕐 Наступне відключення сьогодні: невідомо"

    day_data = fact.get("data", {}).get(today_key, {})
    if not day_data:
        return "🕐 Наступне відключення сьогодні: невідомо"

    now = datetime.now(KYIV_TZ)
    next_hour = now.hour + 2  # schedule uses 1-24, skip current slot

    parts = []
    for group in settings.OUTAGE_GROUPS:
        hours = day_data.get(group)
        if not hours:
            continue

        for h in range(next_hour, 25):
            status = hours.get(str(h), "yes")
            if status == "no":
                parts.append(f"{h - 1:02d}:00-{h - 1:02d}:30")
                break

    if not parts:
        return "🕐 Наступне відключення сьогодні: не планується"

    return f"🕐 Наступне відключення сьогодні: {' або '.join(parts)}"
