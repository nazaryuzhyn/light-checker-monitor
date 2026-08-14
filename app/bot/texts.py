"""Every line the bot says, in one place.

Keeping the copy here means the wording stays consistent between a button
press and a push notification, and it can be read without digging through
handler plumbing.
"""

from datetime import datetime

from app.core.timeutil import format_clock, format_duration, now_kyiv, to_kyiv
from app.services.schedule import DaySchedule, build_headline, group_label
from app.services.schedule.models import SLOTS_PER_DAY, slot_label, slot_of
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
    return f"{lead}\n\nНапишу, щойно світло зникне або зʼявиться."


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


def schedule_caption(schedule: DaySchedule, *, now: datetime | None = None) -> str:
    headline = build_headline(schedule, now or now_kyiv())
    label = "Сьогодні" if schedule.is_today else "Завтра"
    return (
        f"*{headline.plain}*\n"
        f"{headline.detail}\n\n"
        f"_{label} · група {group_label(schedule.group)} · "
        f"оновлено {schedule.updated_label}_"
    )


def schedule_missing(day: Day) -> str:
    if day == "tomorrow":
        return (
            "📅 Графік на завтра ще не опубліковано.\n\n"
            "Зазвичай він зʼявляється ввечері — спробуй пізніше."
        )
    return "📅 Графік на сьогодні ще не опубліковано."


def schedule_missing_short(day: Day) -> str:
    return f"Графік на {DAY_NAMES[day]} ще не опубліковано"


def schedule_unavailable() -> str:
    return "⚠️ Не вдалось отримати графік. Спробуй ще раз за хвилину."


# ── notifications ─────────────────────────────────────────────────────────


def _restoration_hint(schedule: DaySchedule | None, now: datetime) -> str:
    if schedule is None:
        return "Графік зараз недоступний"

    outage = schedule.outage_at(slot_of(now))
    if outage is None:
        return "За графіком відключення на цей час не планували"

    _, last = outage.anchor
    if last >= SLOTS_PER_DAY:
        return "За графіком світла не буде до кінця доби"
    return f"За графіком увімкнуть о {slot_label(last)}"


def _next_outage_hint(schedule: DaySchedule | None, now: datetime) -> str:
    if schedule is None:
        return ""

    slot = slot_of(now)
    ongoing = schedule.outage_at(slot)
    if ongoing:
        _, last = ongoing.anchor
        if last < SLOTS_PER_DAY:
            return f"За графіком відключення триває до {slot_label(last)}"
        return "За графіком світла не буде до кінця доби"

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
