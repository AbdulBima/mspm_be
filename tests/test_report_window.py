"""Tests for app.services.report_window — the midnight cutoff for daily reports."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.services.report_window import (
    is_open,
    iso_utc,
    local_today,
    recent_working_days,
    window_for,
)

LAGOS = ZoneInfo("Africa/Lagos")


def test_local_today_rolls_over_at_local_midnight() -> None:
    assert local_today(LAGOS, datetime(2026, 10, 25, 22, 59)) == date(2026, 10, 25)
    assert local_today(LAGOS, datetime(2026, 10, 25, 23, 0)) == date(2026, 10, 26)


def test_window_closes_at_local_midnight() -> None:
    opens, closes = window_for(date(2026, 10, 26), LAGOS)
    assert iso_utc(opens) == "2026-10-25T23:00:00Z"
    assert iso_utc(closes) == "2026-10-26T23:00:00Z"


def test_report_open_until_one_second_before_midnight() -> None:
    day = date(2026, 10, 26)
    assert is_open(day, LAGOS, datetime(2026, 10, 26, 22, 59, 59))
    assert not is_open(day, LAGOS, datetime(2026, 10, 26, 23, 0, 0))
    assert not is_open(day, LAGOS, datetime(2026, 10, 25, 22, 59, 59))


def test_recent_working_days_skips_weekends() -> None:
    days = recent_working_days(date(2026, 10, 26), 3)  # Monday
    assert days == [date(2026, 10, 26), date(2026, 10, 23), date(2026, 10, 22)]
