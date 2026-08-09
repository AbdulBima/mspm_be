"""Tests for app.services.sprint_calendar — working-day math."""

from __future__ import annotations

from datetime import date, datetime

from app.services.sprint_calendar import sprint_day_number, working_date_for_day


def test_day_number_before_start_is_zero() -> None:
    sprint = {"start_date": datetime(2026, 8, 10), "working_days": 10}  # a Monday
    result = sprint_day_number(sprint, as_of=date(2026, 8, 9))
    assert result["day_number"] == 0


def test_day_number_skips_weekends() -> None:
    sprint = {"start_date": datetime(2026, 8, 10), "working_days": 10}  # Monday
    # Mon(1) Tue(2) Wed(3) Thu(4) Fri(5) Sat(-) Sun(-) Mon(6)
    result = sprint_day_number(sprint, as_of=date(2026, 8, 17))
    assert result["day_number"] == 6


def test_day_number_clamped_to_working_days() -> None:
    sprint = {"start_date": datetime(2026, 8, 10), "working_days": 5}
    result = sprint_day_number(sprint, as_of=date(2026, 9, 1))
    assert result["day_number"] == 5


def test_working_date_for_day_is_inverse_of_day_number() -> None:
    sprint = {"start_date": datetime(2026, 8, 10), "working_days": 10}
    d = working_date_for_day(sprint, 6)
    assert sprint_day_number(sprint, as_of=d)["day_number"] == 6
