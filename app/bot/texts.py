"""Every line the bot says, in one place.

Keeping the copy here means the wording stays consistent between a button
press and a push notification, and it can be read without digging through
handler plumbing.
"""

import re
from datetime import datetime

from app.core.timeutil import format_clock, format_duration, now_kyiv, to_kyiv
from app.services.schedule import DaySchedule, build_headline, group_label
from app.services.schedule.models import SLOTS_PER_DAY, Outage, slot_label, slot_of
from app.services.schedule.source import Day
from app.state import PowerStateManager

DAY_NAMES: dict[Day, str] = {"today": "сьогодні", "tomorrow": "завтра"}


# ── onboarding ────────────────────────────────────────────────────────────


def greeting(is_new: bool) -> str:
    lead = (
        "👋 Вітаю! Ти підписаний на сповіщення про світло."
        if is_new
        else "👋 Ти вже підписаний."
    )
    return (
        f"{lead}\n\nНапишу, щойно світло зникне або зʼявиться. "
        "Сповіщення про графік і нагадування можна вимкнути в ⚙️ Налаштуваннях."
    )


def farewell() -> str:
    return "🔕 Сповіщення вимкнено.\n\nНапиши /start, щоб підписатись знову."


# ── live power state ──────────────────────────────────────────────────────


def power_status(state: PowerStateManager, *, now: datetime | None = None) -> str:
    moment = now or now_kyiv()

    if state.power_is_on:
        last = format_clock(to_kyiv(state.last_ping))
        elapsed = int((moment.timestamp() - state.last_ping) / 60)
        ago = f" ({elapsed} хв тому)" if elapsed else ""
        return f"✅ *Світло є*\n\nОстанній сигнал: {last}{ago}"

    if not state.power_off_time:
        return "❌ *Світла немає*"

    since = format_clock(to_kyiv(state.power_off_time))
    duration = int((moment.timestamp() - state.power_off_time) / 60)
    return (
        f"❌ *Світла немає*\n\n"
        f"Зникло о {since}\n"
        f"Вже {format_duration(duration)} без світла"
    )


def power_details(state: PowerStateManager, *, now: datetime | None = None) -> str:
    moment = now or now_kyiv()
    last = to_kyiv(state.last_ping).strftime("%d.%m %H:%M:%S")
    status = "✅ Електроенергія є" if state.power_is_on else "❌ Електроенергії немає"

    lines = ["📊 *Детальніше*", "", f"Стан: {status}", f"Останній сигнал: {last}"]
    if not state.power_is_on and state.power_off_time:
        off = to_kyiv(state.power_off_time).strftime("%d.%m %H:%M")
        duration = int((moment.timestamp() - state.power_off_time) / 60)
        lines += ["", f"Відключено: {off}", f"Тривалість: {format_duration(duration)}"]
    return "\n".join(lines)


# ── schedule ──────────────────────────────────────────────────────────────


def _plain(feed_text: str) -> str:
    # Legacy Markdown cannot escape inside _italics_; a stray mark would fail the send.
    return re.sub(r"[_*`\[]", "", feed_text)


def schedule_caption(schedule: DaySchedule, *, now: datetime | None = None) -> str:
    headline = build_headline(schedule, now or now_kyiv())
    label = "Сьогодні" if schedule.is_today else "Завтра"
    return (
        f"*{headline.plain}*\n"
        f"{headline.detail}\n\n"
        f"_{label} · група {group_label(schedule.group)} · "
        f"оновлено {_plain(schedule.updated_label)}_"
    )


def schedule_missing(day: Day) -> str:
    if day == "tomorrow":
        return (
            "📅 Графік на завтра ще не опубліковано.\n\n"
            "Зазвичай він зʼявляється ввечері — спробуй пізніше."
        )
    return "📅 Графік на сьогодні ще не опубліковано."


def schedule_unavailable() -> str:
    return "⚠️ Не вдалось отримати графік. Спробуй ще раз за хвилину."


# ── notifications ─────────────────────────────────────────────────────────


def _expected_end(outage: Outage, slot: int) -> tuple[int, bool]:
    """When the light should return, and whether that is only a possibility."""
    _, last = outage.anchor
    if slot >= last:  # past the certain core, in the half hour that may still be off
        return outage.end, True
    return last, False


def _restoration_hint(schedule: DaySchedule | None, now: datetime) -> str:
    if schedule is None:
        return "Графік зараз недоступний"

    slot = slot_of(now)
    outage = schedule.outage_at(slot)
    if outage is None:
        return "За графіком відключення на цей час не планували"

    end, possibly = _expected_end(outage, slot)
    if end >= SLOTS_PER_DAY:
        return "За графіком світла не буде до кінця доби"
    if possibly:
        return f"За графіком світло може зʼявитися до {slot_label(end)}"
    return f"За графіком увімкнуть о {slot_label(end)}"


def _next_outage_hint(schedule: DaySchedule | None, now: datetime) -> str:
    if schedule is None:
        return ""

    slot = slot_of(now)
    ongoing = schedule.outage_at(slot)
    if ongoing:
        end, possibly = _expected_end(ongoing, slot)
        if end >= SLOTS_PER_DAY:
            return "За графіком світла не буде до кінця доби"
        if possibly:
            return f"За графіком можливе відключення до {slot_label(end)}"
        return f"За графіком відключення триває до {slot_label(end)}"

    upcoming = schedule.next_outage(slot)
    if upcoming is None:
        return "Наступних відключень сьогодні за графіком немає"

    first, _ = upcoming.anchor
    prefix = "Наступне відключення" if upcoming.is_certain else "Можливе відключення"
    return f"{prefix} о {slot_label(first)}"


def power_lost(schedule: DaySchedule | None, *, now: datetime | None = None) -> str:
    moment = now or now_kyiv()
    return f"🔴 *Світло зникло*\n\n{_restoration_hint(schedule, moment)}"


def power_restored(
    schedule: DaySchedule | None, outage_minutes: int, *, now: datetime | None = None
) -> str:
    moment = now or now_kyiv()
    lines = ["💡 *Світло зʼявилось*", "", f"Не було {format_duration(outage_minutes)}"]
    hint = _next_outage_hint(schedule, moment)
    if hint:
        lines += ["", hint]
    return "\n".join(lines)


# ── schedule watch ────────────────────────────────────────────────────────


def _outage_line(outage: Outage) -> str:
    if not outage.is_certain:
        return f"{outage.range_label} · можливе"
    if outage.fuzzy_label:
        return f"{outage.range_label} · {outage.fuzzy_label}"
    return outage.range_label


def _outage_list(schedule: DaySchedule) -> str:
    if not schedule.has_outages:
        return "Відключень не заплановано"
    return "\n".join(f"• {_outage_line(outage)}" for outage in schedule.outages)


def _day_name(schedule: DaySchedule) -> str:
    return DAY_NAMES["today" if schedule.is_today else "tomorrow"]


def schedule_published(schedule: DaySchedule) -> str:
    return f"📅 *Зʼявився графік на {_day_name(schedule)}*\n\n{_outage_list(schedule)}"


def schedule_changed(schedule: DaySchedule) -> str:
    return f"🔄 *Графік на {_day_name(schedule)} змінився*\n\n{_outage_list(schedule)}"


def outage_reminder(outage: Outage) -> str:
    title = "Скоро відключення" if outage.is_certain else "Скоро можливе відключення"
    return f"⏰ *{title}*\n\nЗа графіком {_outage_line(outage)}"


# ── settings ──────────────────────────────────────────────────────────────


def settings_intro() -> str:
    return (
        "⚙️ *Налаштування сповіщень*\n\n"
        "Про те, що світло зникло чи зʼявилось, я пишу завжди. "
        "Додаткові сповіщення можна вимкнути — натисни, щоб перемкнути."
    )


def notice_toggled(label: str, now_on: bool) -> str:
    return f"{label}: {'увімкнено' if now_on else 'вимкнено'}"
