"""
app.services.sprint_calendar
=============================
Working-day math for the 10-working-day (default) sprint cadence: which
"Day N" a calendar date falls on, and the inverse.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta


def _as_date(value: date | datetime) -> date:
    return value.date() if isinstance(value, datetime) else value


def sprint_day_number(sprint: dict, as_of: date | None = None) -> dict[str, int]:
    """
    Working-day counter, e.g. "Day 4 of 10". Weekends are skipped, matching
    the two-week / 10-working-day sprint cadence. Returns day_number clamped
    to [0, working_days], where 0 means "not started yet".
    """
    as_of = as_of or date.today()
    start = _as_date(sprint["start_date"])
    working_days = sprint.get("working_days", 10)

    if as_of < start:
        return {"day_number": 0, "working_days": working_days}

    count = 0
    d = start
    while d <= as_of:
        if d.weekday() < 5:  # Mon-Fri
            count += 1
        d += timedelta(days=1)
    return {"day_number": min(count, working_days), "working_days": working_days}


def working_date_for_day(sprint: dict, day_number: int) -> date:
    """Inverse of sprint_day_number: which calendar date is 'Day N' of the sprint."""
    start = _as_date(sprint["start_date"])
    d = start
    counted = 0
    while counted < day_number:
        if d.weekday() < 5:
            counted += 1
            if counted == day_number:
                break
        d += timedelta(days=1)
    return d
