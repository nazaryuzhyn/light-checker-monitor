"""Domain model for a single day of the outage schedule.

The upstream feed publishes 24 hourly statuses per group. Two of those statuses
("maybe in the first / second half") only make sense at half-hour resolution, so
the whole day is normalised to 48 half-hour slots. Everything downstream — text,
notifications, the rendered image — reads this model and never the raw JSON.
"""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from functools import cached_property

MINUTES_PER_SLOT = 30
SLOTS_PER_HOUR = 60 // MINUTES_PER_SLOT
SLOTS_PER_DAY = 24 * SLOTS_PER_HOUR


class PowerLevel(StrEnum):
    ON = "on"
    OFF = "off"
    MAYBE = "maybe"

    @property
    def is_outage(self) -> bool:
        return self is not PowerLevel.ON


def slot_label(slot: int) -> str:
    """Slot boundary as 'HH:MM'. Slot 0 is 00:00, slot 48 is 24:00."""
    hour, half = divmod(slot, SLOTS_PER_HOUR)
    return f"{hour:02d}:{'30' if half else '00'}"


def slot_of(moment: datetime) -> int:
    return moment.hour * SLOTS_PER_HOUR + moment.minute // MINUTES_PER_SLOT


def minutes_of(moment: datetime) -> int:
    return moment.hour * 60 + moment.minute


@dataclass(frozen=True, slots=True)
class Segment:
    """A run of consecutive slots sharing one power level."""

    start: int
    end: int  # exclusive
    level: PowerLevel

    @property
    def minutes(self) -> int:
        return (self.end - self.start) * MINUTES_PER_SLOT

    @property
    def start_label(self) -> str:
        return slot_label(self.start)

    @property
    def end_label(self) -> str:
        return slot_label(self.end)

    @property
    def range_label(self) -> str:
        return f"{self.start_label} – {self.end_label}"

    def contains(self, slot: int) -> bool:
        return self.start <= slot < self.end


@dataclass(frozen=True, slots=True)
class Outage:
    """One stretch without power, including the half hours it may spill into.

    The feed marks the edges of an outage as "maybe" when the utility has not
    committed to them. Those half hours belong to the same event a person
    experiences, so they are carried here as a fuzzy extent around a certain
    core rather than shown as separate outages.
    """

    start: int  # earliest possible slot
    end: int  # latest possible slot, exclusive
    certain_start: int | None
    certain_end: int | None

    @property
    def is_certain(self) -> bool:
        return self.certain_start is not None

    @property
    def anchor(self) -> tuple[int, int]:
        """The span the callout speaks about: the core when there is one."""
        if self.certain_start is None or self.certain_end is None:
            return self.start, self.end
        return self.certain_start, self.certain_end

    @property
    def minutes(self) -> int:
        first, last = self.anchor
        return (last - first) * MINUTES_PER_SLOT

    @property
    def possible_minutes(self) -> int:
        return (self.end - self.start) * MINUTES_PER_SLOT

    @property
    def range_label(self) -> str:
        first, last = self.anchor
        return f"{slot_label(first)} – {slot_label(last)}"

    @property
    def fuzzy_label(self) -> str:
        """'можливо з 08:30 до 12:30' — only the halves that are uncertain."""
        first, last = self.anchor
        parts = []
        if self.start < first:
            parts.append(f"з {slot_label(self.start)}")
        if self.end > last:
            parts.append(f"до {slot_label(self.end)}")
        return f"можливо {' '.join(parts)}" if parts else ""

    def contains(self, slot: int) -> bool:
        return self.start <= slot < self.end

    def in_core(self, slot: int) -> bool:
        return (
            self.certain_start is not None
            and self.certain_end is not None
            and self.certain_start <= slot < self.certain_end
        )


@dataclass(frozen=True)
class DaySchedule:
    day: date
    group: str
    levels: tuple[PowerLevel, ...]
    updated_at: str
    is_today: bool

    @cached_property
    def segments(self) -> tuple[Segment, ...]:
        out: list[Segment] = []
        start = 0
        for slot in range(1, len(self.levels) + 1):
            at_end = slot == len(self.levels)
            if at_end or self.levels[slot] is not self.levels[start]:
                out.append(Segment(start, slot, self.levels[start]))
                start = slot
        return tuple(out)

    @cached_property
    def outages(self) -> tuple[Outage, ...]:
        """Consecutive non-powered slots collapsed into the events people live through."""
        events: list[Outage] = []
        slot = 0
        while slot < len(self.levels):
            if not self.levels[slot].is_outage:
                slot += 1
                continue
            end = slot
            while end < len(self.levels) and self.levels[end].is_outage:
                end += 1
            core = [i for i in range(slot, end) if self.levels[i] is PowerLevel.OFF]
            events.append(
                Outage(
                    start=slot,
                    end=end,
                    certain_start=core[0] if core else None,
                    certain_end=core[-1] + 1 if core else None,
                )
            )
            slot = end
        return tuple(events)

    @cached_property
    def outage_minutes(self) -> int:
        """Time the utility has committed to cutting — the number worth quoting."""
        return sum(
            s.minutes for s in self.segments if s.level is PowerLevel.OFF
        )

    @property
    def has_outages(self) -> bool:
        return bool(self.outages)

    @property
    def updated_label(self) -> str:
        """'01.07.2026 17:27' → '01.07 о 17:27'; the year is never the question."""
        parts = self.updated_at.strip().split()
        if len(parts) != 2:
            return self.updated_at.strip()
        day, clock = parts
        return f"{'.'.join(day.split('.')[:2])} о {clock}"

    def level_at(self, slot: int) -> PowerLevel:
        return self.levels[min(max(slot, 0), len(self.levels) - 1)]

    def segment_at(self, slot: int) -> Segment:
        return next(s for s in self.segments if s.contains(slot))

    def outage_at(self, slot: int) -> Outage | None:
        return next((o for o in self.outages if o.contains(slot)), None)

    def next_outage(self, slot: int) -> Outage | None:
        return next((o for o in self.outages if o.start > slot), None)
