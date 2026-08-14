from conftest import MAYBE, OFF, ON, at, schedule

from app.services.schedule.summary import Tone, build_headline


def test_announces_the_next_outage_while_the_light_is_on():
    day = schedule((ON, 8), (OFF, 3), (ON, 13))
    headline = build_headline(day, at(6, 45))

    assert headline.plain == "Вимкнуть о 08:00"
    assert headline.tone is Tone.LIGHT_OFF
    assert headline.detail == "через 1 год 15 хв · на 3 години"


def test_warns_when_the_outage_may_start_earlier():
    day = schedule((ON, 8.5), (MAYBE, 0.5), (OFF, 3), (MAYBE, 0.5), (ON, 11.5))
    headline = build_headline(day, at(6, 45))

    assert headline.plain == "Вимкнуть о 09:00"
    assert "можливо вже з 08:30" in headline.detail


def test_counts_down_to_restoration_during_an_outage():
    day = schedule((ON, 8), (OFF, 3), (ON, 13))
    headline = build_headline(day, at(9, 30))

    assert headline.plain == "Увімкнуть о 11:00"
    assert headline.tone is Tone.LIGHT_ON
    assert headline.detail == "залишилось 1 год 30 хв"


def test_says_so_when_the_outage_runs_to_midnight():
    day = schedule((ON, 20), (OFF, 4))
    headline = build_headline(day, at(22, 10))

    assert headline.plain == "Світла не буде до кінця доби"
    assert headline.tone is Tone.LIGHT_OFF


def test_uncertain_half_hour_is_not_reported_as_a_fact():
    day = schedule((ON, 8.5), (MAYBE, 0.5), (OFF, 3), (ON, 12))
    headline = build_headline(day, at(8, 40))

    assert headline.plain == "Можливе відключення"
    assert headline.tone is Tone.UNCERTAIN
    assert headline.detail == "основне відключення з 09:00"


def test_reassures_once_the_day_is_clear():
    day = schedule((ON, 8), (OFF, 3), (ON, 13))
    headline = build_headline(day, at(15, 0))

    assert headline.plain == "Відключень більше не буде"
    assert headline.detail == "Сьогодні без світла було 3 години"


def test_a_day_without_outages_says_it_plainly():
    headline = build_headline(schedule((ON, 24)), at(13, 0))

    assert headline.plain == "Сьогодні без відключень"
    assert headline.tone is Tone.LIGHT_ON


def test_tomorrow_leads_with_the_total():
    day = schedule((ON, 7), (OFF, 4), (ON, 3), (OFF, 3), (ON, 7), is_today=False)
    headline = build_headline(day, at(21, 30))

    assert headline.plain == "Без світла 7 годин"
    assert headline.detail == "2 відключення · перше о 07:00"


def test_tomorrow_without_outages():
    headline = build_headline(schedule((ON, 24), is_today=False), at(21, 30))

    assert headline.plain == "Відключень не заплановано"
