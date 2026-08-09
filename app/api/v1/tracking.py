"""
Sprint Tracker (RPM Ops) — Tracking Routes
=============================================
Four small logs, each pulled straight from the RPM playbook's "Weekly
Deliverables": daily check-ins (standup capture), the risk/blocker register,
the product decisions log, and meeting notes with action items.

Check-ins additionally carry `committed_task_ids` — the specific tasks a
member promised to move during standup, as opposed to `today_plan` which is
free-text narrative. The accountability endpoint below is what makes that
distinction useful: it classifies each commitment against what actually
happened to the task afterward (app.services.commitments.classify_commitment,
shared with the AI standup summary in api/v1/ai.py so the two never
disagree), and flags tasks promised more than once without progress in
between.

Standup attendance is tracked separately from check-ins: check-ins capture
what a member says (plan, blockers, commitments); attendance captures
whether and when they actually showed up, one document per (sprint_id,
attendance_date). Both attendance write paths are single atomic upserts (no
separate read-then-write), so two concurrent requests can't interleave and
silently drop an entry.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo import ReturnDocument

from app.api.deps import get_current_manager
from app.db.collections import (
    checkins_col,
    decisions_col,
    meetings_col,
    members_col,
    risks_col,
    standup_attendance_col,
    tasks_col,
)
from app.schemas.enums import RiskStatus
from app.schemas.tracking import (
    AttendanceBulkMarkRequest,
    AttendanceMarkRequest,
    CheckinCreateRequest,
    DecisionCreateRequest,
    MeetingCreateRequest,
    MeetingUpdateRequest,
    RiskCreateRequest,
    RiskUpdateRequest,
)
from app.services.clock import now, to_datetime
from app.services.commitments import classify_commitment
from app.services.ids import gen_id

router = APIRouter(prefix="/api/pm", tags=["pm-tracker:tracking"])


def _unwrap_enum(value: Any) -> Any:
    """Schemas hand us enum members; Mongo wants their plain string value."""
    return value.value if isinstance(value, Enum) else value


# ─────────────────────────────────────────────────────────────────────────────
# DAILY CHECK-INS
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/checkins", status_code=201)
async def create_checkin(
    payload: CheckinCreateRequest, current_manager: dict = Depends(get_current_manager)
) -> dict:
    checkin_date_dt = to_datetime(payload.checkin_date)
    existing = await checkins_col.find_one(
        {"sprint_id": payload.sprint_id, "member_id": payload.member_id, "checkin_date": checkin_date_dt},
        {"_id": 0, "checkin_id": 1},
    )
    ts = now()

    # Only fields actually present in the request body get applied — this is what
    # lets one page log just committed_task_ids and another log just today_plan/flag
    # against the same day's check-in without either one wiping the other's data.
    provided = payload.model_dump(exclude_unset=True, exclude={"sprint_id", "member_id", "checkin_date"})
    if "flag" in provided:
        provided["flag"] = _unwrap_enum(provided["flag"])

    if existing:
        checkin_id = existing["checkin_id"]
        if provided:
            await checkins_col.update_one(
                {"checkin_id": checkin_id}, {"$set": {**provided, "updated_at": ts}}
            )
    else:
        checkin_id = gen_id("CHK")
        doc = {
            "checkin_id": checkin_id,
            "sprint_id": payload.sprint_id,
            "member_id": payload.member_id,
            "checkin_date": checkin_date_dt,
            "yesterday": payload.yesterday,
            "today_plan": payload.today_plan,
            "blockers": payload.blockers,
            "needs_from_pm": payload.needs_from_pm,
            "committed_task_ids": payload.committed_task_ids,
            "flag": _unwrap_enum(payload.flag),
            "created_at": ts,
            "updated_at": ts,
        }
        await checkins_col.insert_one(doc)

    # Runs for both branches — an existing check-in was just updated (or left
    # as-is if nothing was provided), a new one was just inserted either way
    # `checkin_id` now points at a real document.
    result = await checkins_col.find_one({"checkin_id": checkin_id}, {"_id": 0})
    assert result is not None, f"checkin {checkin_id} vanished immediately after write"
    return result


@router.get("/checkins")
async def list_checkins(
    sprint_id: str,
    checkin_date: date | None = Query(None),
    member_id: str | None = Query(None),
    current_manager: dict = Depends(get_current_manager),
) -> list[dict]:
    query: dict[str, Any] = {"sprint_id": sprint_id}
    if checkin_date:
        query["checkin_date"] = to_datetime(checkin_date)
    if member_id:
        query["member_id"] = member_id
    cursor = checkins_col.find(query, {"_id": 0}).sort("checkin_date", -1)
    return await cursor.to_list(length=1000)


@router.get("/checkins/accountability")
async def checkin_accountability(
    sprint_id: str, current_manager: dict = Depends(get_current_manager)
) -> dict:
    """
    For every standup commitment (a check-in's committed_task_ids), classify
    what happened to that task afterward, and separately surface any task
    that's been promised more than once without progress in between.
    """
    checkins = (
        await checkins_col.find({"sprint_id": sprint_id}, {"_id": 0})
        .sort("checkin_date", 1)
        .to_list(length=2000)
    )
    tasks = await tasks_col.find({"sprint_id": sprint_id}, {"_id": 0}).to_list(length=5000)
    task_by_id = {t["task_id"]: t for t in tasks}
    members = await members_col.find({}, {"_id": 0}).to_list(length=500)
    member_by_id = {m["member_id"]: m for m in members}
    now_ts = now()

    entries = []
    history_by_pair: defaultdict[tuple[str, str], list[dict]] = defaultdict(list)

    for c in checkins:
        member = member_by_id.get(c["member_id"])
        commitment_date = c["checkin_date"]
        committed_tasks = []
        for tid in c.get("committed_task_ids") or []:
            task = task_by_id.get(tid)
            status = classify_commitment(task, commitment_date, now_ts)
            committed_tasks.append(
                {"task_id": tid, "title": task["title"] if task else "Deleted task", "status": status}
            )
            history_by_pair[(c["member_id"], tid)].append({"checkin_date": commitment_date, "status": status})

        entries.append(
            {
                "checkin_id": c["checkin_id"],
                "member_id": c["member_id"],
                "member_name": member["name"] if member else "Unknown",
                "member_color": member["color_tag"] if member else None,
                "checkin_date": commitment_date,
                "today_plan": c.get("today_plan"),
                "flag": c.get("flag"),
                "committed_tasks": committed_tasks,
            }
        )

    flags = []
    for (member_id, task_id), history in history_by_pair.items():
        if len(history) < 2:
            continue
        latest = history[-1]
        if latest["status"] == "done":
            continue
        member = member_by_id.get(member_id)
        task = task_by_id.get(task_id)
        flags.append(
            {
                "member_id": member_id,
                "member_name": member["name"] if member else "Unknown",
                "member_color": member["color_tag"] if member else None,
                "task_id": task_id,
                "task_title": task["title"] if task else "Deleted task",
                "times_committed": len(history),
                "first_committed": history[0]["checkin_date"],
                "latest_status": latest["status"],
            }
        )
    flags.sort(key=lambda f: (-f["times_committed"], f["first_committed"]))

    return {"entries": entries, "flags": flags}


# ─────────────────────────────────────────────────────────────────────────────
# STANDUP ATTENDANCE
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/attendance/bulk", status_code=200)
async def bulk_mark_attendance(
    payload: AttendanceBulkMarkRequest, current_manager: dict = Depends(get_current_manager)
) -> dict:
    day = to_datetime(payload.attendance_date)
    ts = now()
    entries = [
        {
            "member_id": e.member_id,
            "status": e.status.value,
            "joined_at": e.joined_at,
            "today_plan": e.today_plan,
            "task_ids": e.task_ids,
            "note": e.note,
            "marked_at": ts,
        }
        for e in payload.entries
    ]

    return await standup_attendance_col.find_one_and_update(
        {"sprint_id": payload.sprint_id, "attendance_date": day},
        {
            "$set": {"entries": entries, "updated_at": ts},
            "$setOnInsert": {
                "attendance_id": gen_id("ATT"),
                "sprint_id": payload.sprint_id,
                "attendance_date": day,
                "created_at": ts,
            },
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )


@router.post("/attendance/mark", status_code=200)
async def mark_attendance(
    payload: AttendanceMarkRequest, current_manager: dict = Depends(get_current_manager)
) -> dict:
    """
    Upserts a single member's entry for the day, replacing any prior entry
    for that member. One atomic aggregation-pipeline update — filter the
    member's old entry out of `entries`, append the new one, all in the same
    operation — rather than a separate pull then push, which left a window
    for a concurrent request to interleave and lose an entry.
    """
    day = to_datetime(payload.attendance_date)
    ts = now()
    new_entry = {
        "member_id": payload.member_id,
        "status": payload.status.value,
        "joined_at": payload.joined_at,
        "today_plan": payload.today_plan,
        "task_ids": payload.task_ids,
        "note": payload.note,
        "marked_at": ts,
    }

    return await standup_attendance_col.find_one_and_update(
        {"sprint_id": payload.sprint_id, "attendance_date": day},
        [
            {
                "$set": {
                    "attendance_id": {"$ifNull": ["$attendance_id", gen_id("ATT")]},
                    "created_at": {"$ifNull": ["$created_at", ts]},
                    "sprint_id": payload.sprint_id,
                    "attendance_date": day,
                    "entries": {
                        "$concatArrays": [
                            {
                                "$filter": {
                                    "input": {"$ifNull": ["$entries", []]},
                                    "cond": {"$ne": ["$$this.member_id", payload.member_id]},
                                }
                            },
                            [new_entry],
                        ]
                    },
                    "updated_at": ts,
                }
            }
        ],
        upsert=True,
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )


@router.get("/attendance")
async def list_attendance(
    sprint_id: str,
    attendance_date: date | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    current_manager: dict = Depends(get_current_manager),
) -> list[dict]:
    query: dict[str, Any] = {"sprint_id": sprint_id}
    if attendance_date:
        query["attendance_date"] = to_datetime(attendance_date)
    elif start_date or end_date:
        rng: dict[str, Any] = {}
        if start_date:
            rng["$gte"] = to_datetime(start_date)
        if end_date:
            rng["$lte"] = to_datetime(end_date)
        query["attendance_date"] = rng
    cursor = standup_attendance_col.find(query, {"_id": 0}).sort("attendance_date", -1)
    return await cursor.to_list(length=1000)


@router.get("/attendance/stats")
async def attendance_stats(sprint_id: str, current_manager: dict = Depends(get_current_manager)) -> dict:
    """Per-member session counts and attendance rate across the whole sprint, for spotting who keeps missing standup."""
    days = await standup_attendance_col.find({"sprint_id": sprint_id}, {"_id": 0}).to_list(length=1000)
    members = await members_col.find({"active": True}, {"_id": 0, "member_id": 1, "name": 1}).to_list(
        length=1000
    )

    per_member = {
        m["member_id"]: {
            "member_id": m["member_id"],
            "name": m["name"],
            "present": 0,
            "late": 0,
            "absent": 0,
            "excused": 0,
            "sessions": 0,
        }
        for m in members
    }
    for d in days:
        for e in d.get("entries", []):
            bucket = per_member.get(e["member_id"])
            if not bucket:
                continue
            bucket["sessions"] += 1
            bucket[e["status"]] = bucket.get(e["status"], 0) + 1

    summary = []
    for b in per_member.values():
        rate = round((b["present"] + b["late"]) / b["sessions"] * 100) if b["sessions"] else None
        summary.append({**b, "attendance_rate": rate})

    return {"sessions_logged": len(days), "per_member": sorted(summary, key=lambda x: x["name"])}


# ─────────────────────────────────────────────────────────────────────────────
# RISK / BLOCKER REGISTER
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/risks", status_code=201)
async def create_risk(
    payload: RiskCreateRequest, current_manager: dict = Depends(get_current_manager)
) -> dict:
    risk_id = gen_id("RSK")
    ts = now()
    doc = {
        "risk_id": risk_id,
        "sprint_id": payload.sprint_id,
        "title": payload.title,
        "description": payload.description,
        "kind": payload.kind.value,
        "severity": payload.severity.value,
        "owner_member_id": payload.owner_member_id,
        "related_task_id": payload.related_task_id,
        "status": "open",
        "raised_at": ts,
        "resolved_at": None,
    }
    await risks_col.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/risks")
async def list_risks(
    sprint_id: str, status: str | None = Query(None), current_manager: dict = Depends(get_current_manager)
) -> list[dict]:
    query: dict[str, Any] = {"sprint_id": sprint_id}
    if status:
        query["status"] = status
    risks = await risks_col.find(query, {"_id": 0}).sort("raised_at", -1).to_list(length=1000)
    now_ts = now()
    for r in risks:
        raised = r.get("raised_at")
        r["days_open"] = (now_ts - raised).days if raised and r["status"] == "open" else None
    return risks


@router.patch("/risks/{risk_id}")
async def update_risk(
    risk_id: str, payload: RiskUpdateRequest, current_manager: dict = Depends(get_current_manager)
) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No fields provided to update")
    if "severity" in updates:
        updates["severity"] = _unwrap_enum(updates["severity"])
    if "status" in updates:
        updates["status"] = _unwrap_enum(updates["status"])
        if updates["status"] == RiskStatus.RESOLVED.value:
            updates["resolved_at"] = now()

    risk = await risks_col.find_one_and_update(
        {"risk_id": risk_id}, {"$set": updates}, return_document=ReturnDocument.AFTER, projection={"_id": 0}
    )
    if not risk:
        raise HTTPException(404, "Risk not found")
    return risk


@router.delete("/risks/{risk_id}", status_code=204)
async def delete_risk(risk_id: str, current_manager: dict = Depends(get_current_manager)) -> None:
    await risks_col.delete_one({"risk_id": risk_id})
    return None


# ─────────────────────────────────────────────────────────────────────────────
# DECISIONS LOG
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/decisions", status_code=201)
async def create_decision(
    payload: DecisionCreateRequest, current_manager: dict = Depends(get_current_manager)
) -> dict:
    decision_id = gen_id("DEC")
    ts = now()
    doc = {
        "decision_id": decision_id,
        "sprint_id": payload.sprint_id,
        "decision": payload.decision,
        "context": payload.context,
        "made_by": payload.made_by or current_manager.get("name"),
        "related_goal_id": payload.related_goal_id,
        "decided_on": to_datetime(payload.decided_on) if payload.decided_on else ts,
        "created_at": ts,
    }
    await decisions_col.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/decisions")
async def list_decisions(sprint_id: str, current_manager: dict = Depends(get_current_manager)) -> list[dict]:
    cursor = decisions_col.find({"sprint_id": sprint_id}, {"_id": 0}).sort("decided_on", -1)
    return await cursor.to_list(length=1000)


@router.delete("/decisions/{decision_id}", status_code=204)
async def delete_decision(decision_id: str, current_manager: dict = Depends(get_current_manager)) -> None:
    await decisions_col.delete_one({"decision_id": decision_id})
    return None


# ─────────────────────────────────────────────────────────────────────────────
# MEETINGS
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/meetings", status_code=201)
async def create_meeting(
    payload: MeetingCreateRequest, current_manager: dict = Depends(get_current_manager)
) -> dict:
    meeting_id = gen_id("MTG")
    ts = now()
    doc = {
        "meeting_id": meeting_id,
        "sprint_id": payload.sprint_id,
        "meeting_type": payload.meeting_type.value,
        "meeting_date": to_datetime(payload.meeting_date),
        "notes": payload.notes,
        "action_items": [ai.model_dump() for ai in payload.action_items],
        "created_at": ts,
        "updated_at": ts,
    }
    await meetings_col.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/meetings")
async def list_meetings(
    sprint_id: str,
    meeting_type: str | None = Query(None),
    current_manager: dict = Depends(get_current_manager),
) -> list[dict]:
    query: dict[str, Any] = {"sprint_id": sprint_id}
    if meeting_type:
        query["meeting_type"] = meeting_type
    cursor = meetings_col.find(query, {"_id": 0}).sort("meeting_date", -1)
    return await cursor.to_list(length=1000)


@router.patch("/meetings/{meeting_id}")
async def update_meeting(
    meeting_id: str, payload: MeetingUpdateRequest, current_manager: dict = Depends(get_current_manager)
) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No fields provided to update")
    if "action_items" in updates:
        updates["action_items"] = [
            ai if isinstance(ai, dict) else ai.model_dump() for ai in updates["action_items"]
        ]
    updates["updated_at"] = now()

    meeting = await meetings_col.find_one_and_update(
        {"meeting_id": meeting_id},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    return meeting


@router.delete("/meetings/{meeting_id}", status_code=204)
async def delete_meeting(meeting_id: str, current_manager: dict = Depends(get_current_manager)) -> None:
    await meetings_col.delete_one({"meeting_id": meeting_id})
    return None
