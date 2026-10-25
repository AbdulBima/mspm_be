"""
Sprint Tracker (RPM Ops) — Team Member Self-Service Routes
============================================================
What a signed-in team member can see and do: their profile, their tasks in
the active sprint, and today's daily report. A report can only be filed or
edited until midnight (team timezone) of the day it covers.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo import ReturnDocument

from app.api.deps import get_current_member
from app.core.config import settings
from app.db.collections import daily_reports_col, member_accounts_col, tasks_col
from app.schemas.daily_reports import DailyReportSubmitRequest
from app.services import daily_reports, member_accounts, report_window
from app.services.clock import now
from app.services.ids import gen_id
from app.services.sprint_calendar import sprint_day_number
from app.services.task_flags import is_overdue, is_stale

router = APIRouter(prefix="/api/pm/me", tags=["pm-tracker:me"])

_TASK_FIELDS = {
    "_id": 0,
    "task_id": 1,
    "title": 1,
    "status": 1,
    "priority": 1,
    "due_date": 1,
    "expectation": 1,
    "description": 1,
    "goal_id": 1,
    "last_progress_at": 1,
    "updated_at": 1,
    "created_at": 1,
}


def _sprint_brief(sprint: dict | None) -> dict | None:
    if not sprint:
        return None
    day = sprint_day_number(sprint, as_of=daily_reports.today_local())
    return {
        "sprint_id": sprint["sprint_id"],
        "name": sprint["name"],
        "theme": sprint.get("theme"),
        "status": sprint.get("status"),
        "day_number": day["day_number"],
        "working_days": day["working_days"],
    }


@router.get("")
async def my_profile(member: dict = Depends(get_current_member)) -> dict:
    sprint = await daily_reports.active_sprint()
    return {**member_accounts.member_profile(member), "sprint": _sprint_brief(sprint)}


@router.get("/tasks")
async def my_tasks(member: dict = Depends(get_current_member)) -> list[dict]:
    sprint = await daily_reports.active_sprint()
    if not sprint:
        return []
    tasks = (
        await tasks_col.find(
            {"member_id": member["member_id"], "sprint_id": sprint["sprint_id"]}, _TASK_FIELDS
        )
        .sort("priority", 1)
        .to_list(length=500)
    )
    for t in tasks:
        t["is_stale"] = is_stale(t)
        t["is_overdue"] = is_overdue(t)
    return tasks


@router.get("/daily-report")
async def todays_report(member: dict = Depends(get_current_member)) -> dict:
    today = daily_reports.today_local()
    report = await daily_reports_col.find_one(
        {"member_id": member["member_id"], "report_date": daily_reports.day_key(today)}, {"_id": 0}
    )
    if report:
        await daily_reports.attach_tasks([report])
    return {
        **daily_reports.window_payload(today),
        "report": daily_reports.serialize(report) if report else None,
    }


@router.put("/daily-report")
async def submit_report(
    payload: DailyReportSubmitRequest, member: dict = Depends(get_current_member)
) -> dict:
    today = daily_reports.today_local()
    day = payload.report_date or today
    if day < today:
        raise HTTPException(
            403, f"Reports for {day.strftime('%a %d %b')} closed at midnight and can no longer be submitted."
        )
    if day > today:
        raise HTTPException(400, "You can only submit a report for today.")

    task_ids = list(dict.fromkeys(payload.task_ids))
    if task_ids:
        owned = await tasks_col.count_documents(
            {"task_id": {"$in": task_ids}, "member_id": member["member_id"]}
        )
        if owned != len(task_ids):
            raise HTTPException(400, "Some of the selected tasks aren't assigned to you.")

    sprint = await daily_reports.active_sprint()
    ts = now()
    report = await daily_reports_col.find_one_and_update(
        {"member_id": member["member_id"], "report_date": daily_reports.day_key(day)},
        {
            "$set": {
                "summary": payload.summary,
                "task_ids": task_ids,
                "blockers": payload.blockers,
                "plan_tomorrow": payload.plan_tomorrow,
                "flag": payload.flag.value,
                "updated_at": ts,
            },
            "$setOnInsert": {
                "report_id": gen_id("DRP"),
                "member_id": member["member_id"],
                "report_date": daily_reports.day_key(day),
                "sprint_id": sprint["sprint_id"] if sprint else None,
                "submitted_at": ts,
            },
            "$inc": {"revision": 1},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    await daily_reports.attach_tasks([report])
    return {**daily_reports.window_payload(day), "report": daily_reports.serialize(report)}


@router.get("/daily-reports")
async def my_report_history(
    days: int = Query(14, ge=1, le=60), member: dict = Depends(get_current_member)
) -> dict:
    today = daily_reports.today_local()
    working_days = report_window.recent_working_days(today, days)
    oldest = working_days[-1]
    reports = (
        await daily_reports_col.find(
            {"member_id": member["member_id"], "report_date": {"$gte": daily_reports.day_key(oldest)}},
            {"_id": 0},
        )
        .sort("report_date", -1)
        .to_list(length=200)
    )
    await daily_reports.attach_tasks(reports)
    by_day = {daily_reports.report_day(r["report_date"]): daily_reports.serialize(r) for r in reports}

    account = await member_accounts_col.find_one({"member_id": member["member_id"]}, {"_id": 0})
    tracked_from = report_window.local_today(
        settings.team_tz, (account or {}).get("activated_at") or member.get("created_at") or now()
    )

    timeline = []
    for d in working_days:
        if d in by_day:
            status = "submitted"
        elif d == today:
            status = "open"
        elif d < tracked_from:
            status = "not_tracked"
        else:
            status = "missed"
        timeline.append({"date": d.isoformat(), "status": status, "report": by_day.get(d)})

    weekend_reports = [r for d, r in by_day.items() if not report_window.is_working_day(d)]
    submitted = sum(1 for t in timeline if t["status"] == "submitted")
    missed = sum(1 for t in timeline if t["status"] == "missed")

    streak = 0
    for t in timeline:
        if t["status"] == "open":
            continue
        if t["status"] != "submitted":
            break
        streak += 1

    return {
        "timeline": timeline,
        "weekend_reports": weekend_reports,
        "stats": {"submitted": submitted, "missed": missed, "streak": streak},
    }
