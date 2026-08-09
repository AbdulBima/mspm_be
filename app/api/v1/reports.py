"""
Sprint Tracker (RPM Ops) — Report Routes
===========================================
Compiles the raw tracker data (tasks, check-ins, risks, decisions, meetings)
for a period into the shape the RPM playbook asks a PM to hand to
leadership: a Sprint Health Report, a Risk Register snapshot, a Blocker Log,
and an Action Tracker — bundled as one "report" object per period.

If Groq is configured (app.services.narrative), a short narrative summary is
generated on top of the structured data; if it isn't, or the call fails, the
report still returns in full with `narrative: null` — the structured data
never depends on the AI call.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_manager
from app.db.collections import (
    checkins_col,
    decisions_col,
    goals_col,
    meetings_col,
    members_col,
    reports_col,
    risks_col,
    sprints_col,
    tasks_col,
)
from app.schemas.enums import ReportType
from app.schemas.reports import ReportGenerateRequest
from app.services import narrative
from app.services.clock import now, to_datetime
from app.services.ids import gen_id
from app.services.sprint_calendar import sprint_day_number

router = APIRouter(prefix="/api/pm/reports", tags=["pm-tracker:reports"])


def _period_bounds(payload: ReportGenerateRequest, sprint: dict) -> tuple[datetime, datetime]:
    if payload.report_type == ReportType.SPRINT:
        start = sprint["start_date"]
        working_days = sprint.get("working_days", 10)
        end = start + timedelta(
            days=int(working_days * 1.6) + 3
        )  # generous calendar-day ceiling covering weekends
        return start, min(end, now() + timedelta(days=1))

    if not payload.period_start:
        raise HTTPException(400, "period_start is required for daily/weekly reports")
    start = to_datetime(payload.period_start)
    if payload.report_type == ReportType.DAILY:
        end = start + timedelta(days=1)
    else:  # weekly
        end = (
            to_datetime(payload.period_end) + timedelta(days=1)
            if payload.period_end
            else start + timedelta(days=7)
        )
    return start, end


async def _compile_report_data(sprint: dict, start: datetime, end: datetime) -> dict:
    sprint_id = sprint["sprint_id"]
    goals = await goals_col.find({"sprint_id": sprint_id}, {"_id": 0}).sort("order", 1).to_list(length=200)
    members = await members_col.find({}, {"_id": 0}).to_list(length=500)
    member_by_id = {m["member_id"]: m for m in members}

    all_tasks = await tasks_col.find({"sprint_id": sprint_id}, {"_id": 0}).to_list(length=5000)

    def _touched_in_period(t: dict) -> bool:
        for h in t.get("status_history", []):
            if start <= h["changed_at"] < end:
                return True
        return start <= t.get("created_at", start) < end

    moved_this_period = [t for t in all_tasks if _touched_in_period(t)]
    done_this_period = [t for t in moved_this_period if t["status"] == "done"]

    checkins = await checkins_col.find(
        {"sprint_id": sprint_id, "checkin_date": {"$gte": start, "$lt": end}}, {"_id": 0}
    ).to_list(length=1000)

    risks = await risks_col.find({"sprint_id": sprint_id}, {"_id": 0}).to_list(length=1000)
    open_risks = [r for r in risks if r["status"] == "open"]
    resolved_this_period = [r for r in risks if r.get("resolved_at") and start <= r["resolved_at"] < end]
    raised_this_period = [r for r in risks if start <= r["raised_at"] < end]

    decisions = await decisions_col.find(
        {"sprint_id": sprint_id, "decided_on": {"$gte": start, "$lt": end}}, {"_id": 0}
    ).to_list(length=500)

    meetings = await meetings_col.find(
        {"sprint_id": sprint_id, "meeting_date": {"$gte": start, "$lt": end}}, {"_id": 0}
    ).to_list(length=500)
    action_items_open = [
        {**ai, "meeting_id": m["meeting_id"], "meeting_date": m["meeting_date"].isoformat()}
        for m in meetings
        for ai in m.get("action_items", [])
        if not ai.get("done")
    ]

    blocked_now = [t for t in all_tasks if t["status"] == "blocked"]
    at_risk_checkins = [c for c in checkins if c["flag"] in ("at_risk", "blocked")]

    day_info = sprint_day_number(sprint, as_of=min(end, now()).date() if end else None)

    def _brief(t: dict) -> dict:
        m = member_by_id.get(t.get("member_id"), {})
        return {
            "task_id": t["task_id"],
            "title": t["title"],
            "member_name": m.get("name", "Unknown"),
            "status": t["status"],
        }

    return {
        "sprint_name": sprint["name"],
        "sprint_theme": sprint.get("theme"),
        "day_number": day_info["day_number"],
        "working_days": day_info["working_days"],
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "goals": [{"goal_id": g["goal_id"], "title": g["title"]} for g in goals],
        "tasks_moved": [_brief(t) for t in moved_this_period],
        "tasks_completed": [_brief(t) for t in done_this_period],
        "tasks_blocked_now": [_brief(t) for t in blocked_now],
        "checkins_at_risk_or_blocked": [
            {
                "member_name": member_by_id.get(c["member_id"], {}).get("name", "Unknown"),
                "flag": c["flag"],
                "blockers": c.get("blockers"),
            }
            for c in at_risk_checkins
        ],
        "open_risks": [
            {"title": r["title"], "severity": r["severity"], "kind": r["kind"]} for r in open_risks
        ],
        "risks_raised_this_period": [
            {"title": r["title"], "severity": r["severity"]} for r in raised_this_period
        ],
        "risks_resolved_this_period": [{"title": r["title"]} for r in resolved_this_period],
        "decisions_this_period": [
            {"decision": d["decision"], "context": d.get("context")} for d in decisions
        ],
        "meetings_this_period": [
            {"type": m["meeting_type"], "date": m["meeting_date"].isoformat()} for m in meetings
        ],
        "open_action_items": action_items_open,
        "totals": {
            "total_tasks": len(all_tasks),
            "done_tasks": len([t for t in all_tasks if t["status"] == "done"]),
            "blocked_tasks": len(blocked_now),
            "open_risks": len(open_risks),
        },
    }


def _narrative_prompt(report_type: ReportType, data: dict, pm_notes: str | None) -> str:
    return (
        "You are helping an engineering Product Manager write a concise, plain-language "
        f"{report_type.value} status update for leadership, based on the structured sprint data below. "
        "Write 3-6 short sentences or bullet points. Be direct and specific — name real blockers and "
        "real wins, don't pad with generic filler. Do not invent facts not present in the data.\n\n"
        f"SPRINT DATA:\n{json.dumps(data, default=str, indent=2)}\n\n"
        + (f"PM'S OWN NOTES TO INCLUDE:\n{pm_notes}\n\n" if pm_notes else "")
        + "Return plain text only, no markdown headers."
    )


@router.post("/generate", status_code=201)
async def generate_report(
    payload: ReportGenerateRequest, current_manager: dict = Depends(get_current_manager)
) -> dict:
    sprint = await sprints_col.find_one({"sprint_id": payload.sprint_id}, {"_id": 0})
    if not sprint:
        raise HTTPException(404, "Sprint not found")

    start, end = _period_bounds(payload, sprint)
    data = await _compile_report_data(sprint, start, end)

    narrative_text = None
    if payload.include_ai_narrative:
        narrative_text = narrative.complete(
            user_prompt=_narrative_prompt(payload.report_type, data, payload.notes),
            temperature=0.3,
            max_tokens=500,
        )

    report_id = gen_id("RPT")
    ts = now()
    doc = {
        "report_id": report_id,
        "sprint_id": payload.sprint_id,
        "report_type": payload.report_type.value,
        "period_start": start,
        "period_end": end,
        "data": data,
        "narrative": narrative_text,
        "pm_notes": payload.notes,
        "generated_by": current_manager.get("name"),
        "created_at": ts,
    }
    await reports_col.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("")
async def list_reports(
    sprint_id: str, report_type: str | None = None, current_manager: dict = Depends(get_current_manager)
) -> list[dict]:
    query: dict = {"sprint_id": sprint_id}
    if report_type:
        query["report_type"] = report_type
    cursor = reports_col.find(query, {"_id": 0}).sort("created_at", -1)
    return await cursor.to_list(length=200)


@router.get("/{report_id}")
async def get_report(report_id: str, current_manager: dict = Depends(get_current_manager)) -> dict:
    report = await reports_col.find_one({"report_id": report_id}, {"_id": 0})
    if not report:
        raise HTTPException(404, "Report not found")
    return report


@router.delete("/{report_id}", status_code=204)
async def delete_report(report_id: str, current_manager: dict = Depends(get_current_manager)) -> None:
    await reports_col.delete_one({"report_id": report_id})
    return None
