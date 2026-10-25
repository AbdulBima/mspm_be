"""
app.services.report_window
===========================
Daily report submission window. A report for day D opens at 00:00 and
closes at midnight (00:00 of D+1) in the team's timezone; after that it
can no longer be submitted or edited.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc


def _aware_utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)


def local_today(tz: ZoneInfo, moment: datetime) -> date:
    return _aware_utc(moment).astimezone(tz).date()


def window_for(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    opens = datetime.combine(day, time.min, tzinfo=tz)
    closes = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
    return opens.astimezone(UTC), closes.astimezone(UTC)


def is_open(day: date, tz: ZoneInfo, moment: datetime) -> bool:
    opens, closes = window_for(day, tz)
    current = _aware_utc(moment)
    return opens <= current < closes


def is_working_day(day: date) -> bool:
    return day.weekday() < 5


def recent_working_days(end: date, count: int) -> list[date]:
    days: list[date] = []
    d = end
    while len(days) < count:
        if is_working_day(d):
            days.append(d)
        d -= timedelta(days=1)
    return days


def iso_utc(moment: datetime) -> str:
    return _aware_utc(moment).isoformat().replace("+00:00", "Z")
