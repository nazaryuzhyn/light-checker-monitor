from dataclasses import replace

from conftest import MAYBE, OFF, ON, at, schedule

from app.bot import texts


def test_outage_notification_quotes_the_planned_restoration():
    day = schedule((ON, 8), (OFF, 3), (ON, 13))
    assert "За графіком увімкнуть о 11:00" in texts.power_lost(day, now=at(9, 10))


def test_outage_notification_is_honest_when_nothing_was_planned():
    day = schedule((ON, 24))
    assert "не планували" in texts.power_lost(day, now=at(9, 10))


def test_outage_notification_survives_a_missing_feed():
    assert "недоступний" in texts.power_lost(None, now=at(9, 10))


def test_restore_notification_points_at_the_next_outage():
    day = schedule((ON, 8), (OFF, 3), (ON, 6), (OFF, 2), (ON, 5))
    message = texts.power_restored(day, 95, now=at(11, 5))

    assert "Не було 1 год 35 хв" in message
    assert "Наступне відключення о 17:00" in message


def test_restore_notification_flags_an_uncertain_next_outage():
    day = schedule((ON, 8), (OFF, 3), (ON, 6), (MAYBE, 1), (ON, 6))
    message = texts.power_restored(day, 60, now=at(11, 5))

    assert "Можливе відключення о 17:00" in message


def test_caption_repeats_what_the_image_says():
    day = schedule((ON, 8), (OFF, 3), (ON, 13))
    caption = texts.schedule_caption(day, now=at(6, 45))

    assert "*Вимкнуть о 08:00*" in caption
    assert "група 5.2" in caption
    assert "оновлено 14.08 о 07:40" in caption


def test_feed_text_cannot_break_the_caption_markup():
    day = replace(schedule((ON, 24)), updated_at="20.11.2026 10:36_beta*")
    caption = texts.schedule_caption(day, now=at(9, 10))
    assert caption.endswith("оновлено 20.11 о 10:36beta_")


def test_hints_in_the_uncertain_tail_quote_its_end():
    # Possible 13:00–13:30, outage 13:30–17:30, possible 17:30–18:00; now 17:40.
    day = schedule((ON, 13), (MAYBE, 0.5), (OFF, 4), (MAYBE, 0.5), (ON, 6))

    assert "За графіком світло може зʼявитися до 18:00" in texts.power_lost(day, now=at(17, 40))
    assert "За графіком можливе відключення до 18:00" in texts.power_restored(day, 10, now=at(17, 40))
    assert "За графіком увімкнуть о 17:30" in texts.power_lost(day, now=at(15, 0))
