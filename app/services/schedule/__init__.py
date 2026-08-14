"""Outage schedule: fetching, domain model, headline copy and image rendering."""

from app.services.schedule.models import (
    DaySchedule,
    PowerLevel,
    Segment,
    slot_label,
    slot_of,
)
from app.services.schedule.render import render_day_png
from app.services.schedule.source import (
    Day,
    get_day,
    group_label,
    parse_day,
    primary_group,
    reset_cache,
)
from app.services.schedule.summary import Headline, Tone, build_headline

__all__ = [
    "Day",
    "DaySchedule",
    "Headline",
    "PowerLevel",
    "Segment",
    "Tone",
    "build_headline",
    "get_day",
    "group_label",
    "parse_day",
    "primary_group",
    "render_day_png",
    "reset_cache",
    "slot_label",
    "slot_of",
]
