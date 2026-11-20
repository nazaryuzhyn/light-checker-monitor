from conftest import MAYBE, OFF, ON, midnight_today_ts

from app.services.schedule.models import PowerLevel
from app.services.schedule.source import SECONDS_PER_DAY, group_label, parse_day

HOURS_ALL_ON = {str(h): "yes" for h in range(1, 25)}


def feed(*, today_ts: int | None = None, groups: dict | None = None, extra: dict | None = None):
    key = str(today_ts if today_ts is not None else midnight_today_ts())
    data = {key: groups if groups is not None else {"GPV5.2": dict(HOURS_ALL_ON)}}
    data.update(extra or {})
    return {"fact": {"today": key, "update": "14.08.2026 07:40", "data": data}}


def levels_of(changes: dict[str, str]) -> tuple[PowerLevel, ...]:
    day = parse_day(feed(groups={"GPV5.2": dict(HOURS_ALL_ON) | changes}), "today")
    assert day is not None
    return day.levels


def test_hourly_statuses_expand_into_half_hour_slots():
    # Feed key N covers the hour ending at N:00 — key "10" is 09:00–10:00.
    levels = levels_of({"10": "no", "12": "maybe"})
    assert levels[16:24] == (ON, ON, OFF, OFF, ON, ON, MAYBE, MAYBE)


def test_a_half_hour_code_next_to_an_outage_extends_it():
    # Group 5.2 on 20.11.2026, checked against the oblenergo's own schedule:
    # possible 13:00–13:30, outage 13:30–17:30, possible 17:30–18:00.
    levels = levels_of({"14": "mfirst", "15": "no", "16": "no", "17": "no", "18": "msecond"})
    assert levels[25:37] == (ON, MAYBE) + (OFF,) * 8 + (MAYBE, ON)


def test_a_half_hour_code_next_to_light_leaves_the_other_half_on():
    levels = levels_of({"10": "no", "11": "mfirst", "13": "msecond", "14": "no"})
    assert levels[20:22] == (MAYBE, ON)
    assert levels[24:26] == (ON, MAYBE)


def test_half_hour_outages():
    levels = levels_of({"12": "first", "14": "second"})
    assert levels[22:24] == (OFF, ON)
    assert levels[26:28] == (ON, OFF)


def test_a_stale_feed_is_refused_rather_than_shown_as_today():
    assert parse_day(feed(today_ts=midnight_today_ts() - SECONDS_PER_DAY), "today") is None


def test_missing_group_yields_nothing():
    assert parse_day(feed(groups={"GPV1.1": dict(HOURS_ALL_ON)}), "today") is None


def test_tomorrow_only_when_the_feed_actually_publishes_it():
    assert parse_day(feed(), "tomorrow") is None

    tomorrow_key = str(midnight_today_ts() + SECONDS_PER_DAY)
    raw = feed(extra={tomorrow_key: {"GPV5.2": dict(HOURS_ALL_ON)}})
    day = parse_day(raw, "tomorrow")

    assert day is not None
    assert not day.is_today


def test_group_label_drops_the_feed_prefix():
    assert group_label("GPV5.2") == "5.2"
    assert group_label("5.2") == "5.2"
