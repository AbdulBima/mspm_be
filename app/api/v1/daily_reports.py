"""
Sprint Tracker (RPM Ops) — Daily Report Routes (manager view)
===============================================================
Who filed their end-of-day report for a given date, what they said, and
who is still missing. Members file reports through api/v1/me.py.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_manager
from app.core.config import settings
from app.db.collections import daily_reports_col, member_accounts_col, members_col
from app.services import daily_reports, member_accounts, report_window

router = APIRouter(prefix="/api/pm/daily-reports", tags=["pm-tracker:daily-reports"])


def _member_brief(member: dict, account: dict | None) -> dict:
    return {
        "member_id": member["member_id"],
        "name": member["name"],
        "role_title": member.get("role_title"),
        "discipline": member.get("discipline"),
        "color_tag": member.get("color_tag"),
        "login_status": member_accounts.login_status(account),
    }


@router.get("")
async def reports_for_day(
    report_date: date | None = Query(None), current_manager: dict = Depends(get_current_manager)
) -> dict:
    day = report_date or daily_reports.today_local()
    _, closes = report_window.window_for(day, settings.team_tz)
    members = (
        await members_col.find(
            {"active": {"$ne": False}, "created_at": {"$lt": closes.replace(tzinfo=None)}}, {"_id": 0}
        )
        .sort("name", 1)
        .to_list(length=500)
    )
    accounts = await member_accounts_col.find({}, {"_id": 0}).to_list(length=500)
    account_by_id = {a["member_id"]: a for a in accounts}

    reports = (
        await daily_reports_col.find({"report_date": daily_reports.day_key(day)}, {"_id": 0})
        .sort("submitted_at", 1)
        .to_list(length=500)
    )
    await daily_reports.attach_tasks(reports)

    member_by_id = {m["member_id"]: m for m in members}
    submitted = [
        {
            **daily_reports.serialize(r),
            "member": _member_brief(member_by_id[r["member_id"]], account_by_id.get(r["member_id"])),
        }
        for r in reports
        if r["member_id"] in member_by_id
    ]
    reported_ids = {r["member_id"] for r in reports}
    missing = [
        _member_brief(m, account_by_id.get(m["member_id"]))
        for m in members
        if m["member_id"] not in reported_ids
    ]

    return {
        **daily_reports.window_payload(day),
        "submitted": submitted,
        "missing": missing,
        "totals": {"expected": len(members), "submitted": len(submitted), "missing": len(missing)},
    }


@router.get("/members/{member_id}")
async def member_report_history(
    member_id: str,
    days: int = Query(14, ge=1, le=60),
    current_manager: dict = Depends(get_current_manager),
) -> list[dict]:
    today = daily_reports.today_local()
    oldest = report_window.recent_working_days(today, days)[-1]
    reports = (
        await daily_reports_col.find(
            {"member_id": member_id, "report_date": {"$gte": daily_reports.day_key(oldest)}}, {"_id": 0}
        )
        .sort("report_date", -1)
        .to_list(length=200)
    )
    await daily_reports.attach_tasks(reports)
    return [daily_reports.serialize(r) for r in reports]
