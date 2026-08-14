from conftest import midnight_today_ts

from app.services.schedule.models import PowerLevel
from app.services.schedule.source import SECONDS_PER_DAY, group_label, parse_day

HOURS_ALL_ON = {str(h): "yes" for h in range(1, 25)}


def feed(*, today_ts: int | None = None, groups: dict | None = None, extra: dict | None = None):
    key = str(today_ts if today_ts is not None else midnight_today_ts())
    data = {key: groups if groups is not None else {"GPV5.2": dict(HOURS_ALL_ON)}}
    data.update(extra or {})
    return {"fact": {"today": key, "update": "14.08.2026 07:40", "data": data}}


def test_hourly_statuses_expand_into_half_hour_slots():
    # Feed key N covers the hour ending at N:00 — key "9" is 08:00–09:00.
    hours = dict(HOURS_ALL_ON) | {"9": "mfirst", "10": "no", "11": "msecond"}
    day = parse_day(feed(groups={"GPV5.2": hours}), "today")

    assert day is not None
    assert day.levels[16] is PowerLevel.MAYBE  # 08:00 — first half of hour 9
    assert day.levels[17] is PowerLevel.ON  # 08:30
    assert day.levels[18] is PowerLevel.OFF  # 09:00 — hour 10 is "no"
    assert day.levels[19] is PowerLevel.OFF  # 09:30
    assert day.levels[20] is PowerLevel.ON  # 10:00
    assert day.levels[21] is PowerLevel.MAYBE  # 10:30 — second half of hour 11


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
