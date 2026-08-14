"""Render the schedule image for a set of scenarios without touching Telegram.

    python -m scripts.preview_schedule [output-dir]

Writes one PNG per scenario so the design can be reviewed side by side.
"""

import sys
from datetime import date, datetime
from pathlib import Path

from app.core.timeutil import KYIV_TZ
from app.services.schedule import DaySchedule
from app.services.schedule.models import PowerLevel
from app.services.schedule.render import render_day_png
from app.services.schedule.source import parse_day

ON, OFF, MAYBE = PowerLevel.ON, PowerLevel.OFF, PowerLevel.MAYBE


def build(pattern: list[tuple[PowerLevel, int]], *, is_today: bool = True) -> DaySchedule:
    """pattern: [(level, hours), ...] adding up to 24 hours."""
    levels: list[PowerLevel] = []
    for level, hours in pattern:
        levels.extend([level] * int(hours * 2))
    assert len(levels) == 48, f"expected 48 slots, got {len(levels)}"
    return DaySchedule(
        day=date(2026, 8, 14 if is_today else 15),
        group="GPV5.2",
        levels=tuple(levels),
        updated_at="14.08.2026 07:40",
        is_today=is_today,
    )


SCENARIOS: dict[str, tuple[DaySchedule, datetime]] = {
    "01-typical": (
        build([(ON, 8.5), (MAYBE, 0.5), (OFF, 3), (MAYBE, 0.5), (ON, 4.5), (OFF, 3), (ON, 4)]),
        datetime(2026, 8, 14, 6, 45, tzinfo=KYIV_TZ),
    ),
    "02-outage-now": (
        build([(ON, 8.5), (MAYBE, 0.5), (OFF, 3), (MAYBE, 0.5), (ON, 4.5), (OFF, 3), (ON, 4)]),
        datetime(2026, 8, 14, 10, 20, tzinfo=KYIV_TZ),
    ),
    "03-clear-day": (
        build([(ON, 24)]),
        datetime(2026, 8, 14, 13, 5, tzinfo=KYIV_TZ),
    ),
    "04-heavy-day": (
        build([
            (OFF, 3), (ON, 3), (OFF, 3), (ON, 2), (OFF, 4),
            (ON, 2), (OFF, 3), (ON, 1), (OFF, 2), (ON, 1),
        ]),
        datetime(2026, 8, 14, 16, 10, tzinfo=KYIV_TZ),
    ),
    "05-tomorrow": (
        build([(ON, 7), (OFF, 4), (ON, 3), (MAYBE, 1), (OFF, 3), (ON, 6)], is_today=False),
        datetime(2026, 8, 14, 21, 30, tzinfo=KYIV_TZ),
    ),
    "06-evening-tail": (
        build([(ON, 20), (OFF, 4)]),
        datetime(2026, 8, 14, 22, 40, tzinfo=KYIV_TZ),
    ),
}


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "preview")
    out.mkdir(parents=True, exist_ok=True)

    for name, (schedule, moment) in SCENARIOS.items():
        (out / f"{name}.png").write_bytes(render_day_png(schedule, now=moment))
        print(f"→ {out / f'{name}.png'}")

    feed = Path("feed.json")
    if feed.exists():
        import json

        schedule = parse_day(json.loads(feed.read_text()), "today")
        if schedule:
            (out / "00-live.png").write_bytes(render_day_png(schedule))
            print(f"→ {out / '00-live.png'} (live feed)")


if __name__ == "__main__":
    main()
