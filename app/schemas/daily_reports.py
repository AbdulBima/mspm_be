"""app.schemas.daily_reports — a team member's end-of-day report."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.schemas.enums import CheckinFlag


class DailyReportSubmitRequest(BaseModel):
    report_date: date | None = None
    summary: str = Field(min_length=10, max_length=5000)
    task_ids: list[str] = Field(default_factory=list, max_length=50)
    blockers: str | None = Field(None, max_length=2000)
    plan_tomorrow: str | None = Field(None, max_length=2000)
    flag: CheckinFlag = CheckinFlag.ON_TRACK

    @field_validator("summary")
    @classmethod
    def _strip_summary(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 10:
            raise ValueError("Tell us a bit more about what you did today (at least 10 characters).")
        return value

    @field_validator("blockers", "plan_tomorrow")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None
