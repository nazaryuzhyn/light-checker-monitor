"""Turns a DaySchedule into the one sentence a person actually came for.

Both the image and the chat messages read this, so the picture and the text can
never disagree about what happens next.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.core.timeutil import (
    format_duration,
    format_duration_display,
    format_duration_long,
    plural,
)
from app.services.schedule.models import (
    MINUTES_PER_SLOT,
    SLOTS_PER_DAY,
    DaySchedule,
    Outage,
    minutes_of,
    slot_label,
    slot_of,
)


class Tone(StrEnum):
    """What the headline is about — the renderer maps this to a colour."""

    LIGHT_ON = "on"
    LIGHT_OFF = "off"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True, slots=True)
class Headline:
    lead: str
    accent: str  # the time or duration worth setting apart; may be empty
    detail: str
    tone: Tone

    @property
    def plain(self) -> str:
        return f"{self.lead}{self.accent}".strip()


def _join(*parts: str) -> str:
    return " · ".join(p for p in parts if p)


def _count_label(count: int) -> str:
    return f"{count} {plural(count, ('відключення', 'відключення', 'відключень'))}"


def _minutes_until(slot: int, now: datetime) -> int:
    return slot * MINUTES_PER_SLOT - minutes_of(now)


def _upcoming(outage: Outage, now: datetime) -> Headline:
    first, last = outage.anchor
    waiting = f"через {format_duration(_minutes_until(first, now))}"

    if not outage.is_certain:
        return Headline(
            "Можуть вимкнути о ",
            slot_label(first),
            _join(waiting, f"на {format_duration_long(outage.minutes)}"),
            Tone.UNCERTAIN,
        )

    early = (
        f"можливо вже з {slot_label(outage.start)}" if outage.start < first else ""
    )
    return Headline(
        "Вимкнуть о ",
        slot_label(first),
        _join(waiting, f"на {format_duration_long(outage.minutes)}", early),
        Tone.LIGHT_OFF,
    )


def _ongoing(outage: Outage, now: datetime, slot: int) -> Headline:
    first, last = outage.anchor

    if not outage.in_core(slot):
        # We are in one of the uncertain half hours around the outage.
        detail = (
            f"основне відключення з {slot_label(first)}"
            if slot < first
            else f"до {slot_label(outage.end)}"
        )
        return Headline("Можливе відключення", "", detail, Tone.UNCERTAIN)

    if last >= SLOTS_PER_DAY:
        return Headline(
            "Світла не буде до кінця доби",
            "",
            f"Відключення почалось о {slot_label(first)}",
            Tone.LIGHT_OFF,
        )

    left = f"залишилось {format_duration(_minutes_until(last, now))}"
    if outage.end > last:
        return Headline(
            "Орієнтовно увімкнуть о ",
            slot_label(last),
            _join(left, f"можливо до {slot_label(outage.end)}"),
            Tone.UNCERTAIN,
        )
    return Headline("Увімкнуть о ", slot_label(last), left, Tone.LIGHT_ON)


def _today_headline(schedule: DaySchedule, now: datetime) -> Headline:
    slot = slot_of(now)

    ongoing = schedule.outage_at(slot)
    if ongoing:
        return _ongoing(ongoing, now, slot)

    upcoming = schedule.next_outage(slot)
    if upcoming:
        return _upcoming(upcoming, now)

    if schedule.has_outages:
        return Headline(
            "Відключень більше не буде",
            "",
            f"Сьогодні без світла було {format_duration_long(schedule.outage_minutes)}",
            Tone.LIGHT_ON,
        )
    return Headline(
        "Сьогодні без відключень",
        "",
        "За графіком світло має бути цілу добу",
        Tone.LIGHT_ON,
    )


def _future_headline(schedule: DaySchedule) -> Headline:
    if not schedule.has_outages:
        return Headline(
            "Відключень не заплановано",
            "",
            "За графіком світло має бути цілу добу",
            Tone.LIGHT_ON,
        )

    first = schedule.outages[0]
    return Headline(
        "Без світла ",
        format_duration_display(schedule.outage_minutes),
        _join(
            _count_label(len(schedule.outages)),
            f"перше о {slot_label(first.anchor[0])}",
        ),
        Tone.LIGHT_OFF,
    )


def build_headline(schedule: DaySchedule, now: datetime) -> Headline:
    return (
        _today_headline(schedule, now)
        if schedule.is_today
        else _future_headline(schedule)
    )
