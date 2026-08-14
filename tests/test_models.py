from conftest import MAYBE, OFF, ON, at, schedule

from app.services.schedule.models import slot_label, slot_of


def test_segments_collapse_equal_slots():
    day = schedule((ON, 8), (OFF, 3), (ON, 13))
    assert [(s.start_label, s.end_label, s.level) for s in day.segments] == [
        ("00:00", "08:00", ON),
        ("08:00", "11:00", OFF),
        ("11:00", "24:00", ON),
    ]


def test_maybe_edges_join_the_outage_they_belong_to():
    day = schedule((ON, 8.5), (MAYBE, 0.5), (OFF, 3), (MAYBE, 0.5), (ON, 11.5))
    (outage,) = day.outages

    assert outage.range_label == "09:00 – 12:00"
    assert (outage.start, outage.end) == (17, 25)  # 08:30 → 12:30
    assert outage.is_certain
    assert outage.minutes == 180
    assert outage.possible_minutes == 240
    assert outage.fuzzy_label == "можливо з 08:30 до 12:30"


def test_maybe_without_a_certain_core_stays_its_own_event():
    day = schedule((ON, 8), (MAYBE, 1), (ON, 15))
    (outage,) = day.outages

    assert not outage.is_certain
    assert outage.range_label == "08:00 – 09:00"
    assert outage.fuzzy_label == ""


def test_outage_minutes_counts_only_committed_time():
    day = schedule((ON, 8.5), (MAYBE, 0.5), (OFF, 3), (MAYBE, 0.5), (ON, 11.5))
    assert day.outage_minutes == 180


def test_lookup_around_the_current_slot():
    day = schedule((ON, 8), (OFF, 3), (ON, 6), (OFF, 2), (ON, 5))

    assert day.outage_at(slot_of(at(9, 30))).range_label == "08:00 – 11:00"
    assert day.outage_at(slot_of(at(12, 0))) is None
    assert day.next_outage(slot_of(at(12, 0))).range_label == "17:00 – 19:00"
    assert day.next_outage(slot_of(at(20, 0))) is None


def test_slot_label_covers_both_ends_of_the_day():
    assert slot_label(0) == "00:00"
    assert slot_label(17) == "08:30"
    assert slot_label(48) == "24:00"


def test_updated_label_drops_the_year():
    assert schedule((ON, 24)).updated_label == "14.08 о 07:40"
