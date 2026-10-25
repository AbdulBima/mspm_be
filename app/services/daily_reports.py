"""
app.services.daily_reports
===========================
Shared logic for member daily reports: the submission window, the active
sprint lookup, and shaping report documents for both the member's own view
and the manager's team view.
"""

from __future__ import annotations

from datetime import date, datetime

from app.core.config import settings
from app.db.collections import sprints_col, tasks_col
from app.schemas.enums import SprintStatus
from app.services import report_window
from app.services.clock import now, to_datetime


def today_local() -> date:
    return report_window.local_today(settings.team_tz, now())


def window_payload(day: date) -> dict:
    opens, closes = report_window.window_for(day, settings.team_tz)
    return {
        "report_date": day.isoformat(),
        "timezone": settings.team_timezone,
        "opens_at": report_window.iso_utc(opens),
        "closes_at": report_window.iso_utc(closes),
        "server_now": report_window.iso_utc(now()),
        "is_open": report_window.is_open(day, settings.team_tz, now()),
        "is_working_day": report_window.is_working_day(day),
    }


async def active_sprint() -> dict | None:
    return await sprints_col.find_one({"status": SprintStatus.ACTIVE.value}, {"_id": 0})


def report_day(value: datetime | date) -> date:
    return value.date() if isinstance(value, datetime) else value


def serialize(report: dict) -> dict:
    out = {k: v for k, v in report.items() if k != "_id"}
    out["report_date"] = report_day(report["report_date"]).isoformat()
    return out


async def attach_tasks(reports: list[dict]) -> list[dict]:
    task_ids = list({tid for r in reports for tid in r.get("task_ids") or []})
    tasks = (
        await tasks_col.find(
            {"task_id": {"$in": task_ids}}, {"_id": 0, "task_id": 1, "title": 1, "status": 1}
        ).to_list(length=1000)
        if task_ids
        else []
    )
    by_id = {t["task_id"]: t for t in tasks}
    for r in reports:
        r["tasks"] = [by_id[tid] for tid in r.get("task_ids") or [] if tid in by_id]
    return reports


def day_key(day: date) -> datetime:
    return to_datetime(day)
