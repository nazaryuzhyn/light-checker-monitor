from dataclasses import replace
from datetime import date, datetime

from conftest import MAYBE, OFF, ON, at, schedule

from app.core.timeutil import KYIV_TZ

from app.services.schedule_watch import due_reminders, schedule_notices

# Group 5.2 on 20.11.2026: possible 13:00–13:30, outage 13:30–17:30, possible 17:30–18:00.
DAY = schedule((ON, 13), (MAYBE, 0.5), (OFF, 4), (MAYBE, 0.5), (ON, 6))


def test_a_new_day_is_announced_once():
    seen = {}

    assert schedule_notices(seen, [DAY]) == [
        "📅 *Зʼявився графік на сьогодні*\n\n• 13:30 – 17:30 · можливо з 13:00 до 18:00"
    ]
    assert schedule_notices(seen, [DAY]) == []


def test_a_changed_day_is_announced():
    seen = {DAY.day: schedule((ON, 24)).levels}

    assert schedule_notices(seen, [DAY]) == [
        "🔄 *Графік на сьогодні змінився*\n\n• 13:30 – 17:30 · можливо з 13:00 до 18:00"
    ]


def test_a_day_without_outages_says_so():
    assert schedule_notices({}, [schedule((ON, 24), is_today=False)]) == [
        "📅 *Зʼявився графік на завтра*\n\nВідключень не заплановано"
    ]


def test_the_reminder_is_due_half_an_hour_before_the_earliest_possible_start():
    assert due_reminders([DAY], at(12, 0), at(12, 29)) == []
    assert [o.start for o in due_reminders([DAY], at(12, 29), at(12, 30))] == [26]
    assert due_reminders([DAY], at(12, 30), at(12, 31)) == []


def test_a_late_check_still_sends_the_reminder():
    # A slow round of notices can push the next check well past the reminder time.
    assert [o.start for o in due_reminders([DAY], at(12, 29), at(12, 34))] == [26]


def test_the_hour_repeated_when_clocks_go_back_reminds_once():
    # 25.10.2026: 03:00–03:59 happens twice. An outage at 04:00 is reminded 30 real
    # minutes before it, which is the second 03:30 — and only then.
    day = replace(schedule((ON, 4), (OFF, 2), (ON, 18)), day=date(2026, 10, 25))
    def kyiv(minute: int, fold: int) -> datetime:
        return datetime(2026, 10, 25, 3, minute, tzinfo=KYIV_TZ, fold=fold)

    assert due_reminders([day], kyiv(29, fold=0), kyiv(31, fold=0)) == []
    assert len(due_reminders([day], kyiv(29, fold=1), kyiv(31, fold=1))) == 1


def test_no_reminder_once_the_outage_has_begun():
    # A check delayed past 13:00 (the earliest possible start) would warn too late.
    assert due_reminders([DAY], at(12, 29), at(13, 1)) == []
