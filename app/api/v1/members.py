"""
Sprint Tracker (RPM Ops) — Team Member Routes
=================================================
Team members are engineers/designers/QA/interns — the people whose work is
being coordinated. They don't log in; the PM manages their tasks and notes
on their behalf, mirroring how the RPM playbook describes reviewing "every
team member" each morning.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pymongo import ReturnDocument

from app.api.deps import get_current_manager
from app.db.collections import checkins_col, goals_col, members_col, sprints_col, task_notes_col, tasks_col
from app.schemas.members import MemberCreateRequest, MemberUpdateRequest
from app.services.clock import now
from app.services.ids import gen_id
from app.services.pdf import build_member_open_tasks_pdf
from app.services.slugs import slugify
from app.services.sprint_calendar import sprint_day_number, working_date_for_day
from app.services.task_flags import is_overdue, is_stale

router = APIRouter(prefix="/api/pm/members", tags=["pm-tracker:team"])

_PALETTE = ["#F2A93B", "#5B8DEF", "#34D399", "#A78BFA", "#EF5B5B", "#38BDF8", "#F472B6", "#FBBF24"]


async def _get_member_or_404(member_id: str) -> dict:
    member = await members_col.find_one({"member_id": member_id}, {"_id": 0})
    if not member:
        raise HTTPException(404, "Team member not found")
    return member


@router.post("", status_code=201)
async def create_member(
    payload: MemberCreateRequest, current_manager: dict = Depends(get_current_manager)
) -> dict:
    member_id = gen_id("MEM")
    ts = now()
    existing_count = await members_col.count_documents({})
    color = payload.color_tag or _PALETTE[existing_count % len(_PALETTE)]
    doc = {
        "member_id": member_id,
        "name": payload.name,
        "role_title": payload.role_title,
        "discipline": payload.discipline.value,
        "email": payload.email,
        "color_tag": color,
        "active": True,
        "created_at": ts,
        "updated_at": ts,
    }
    await members_col.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("")
async def list_members(current_manager: dict = Depends(get_current_manager)) -> list[dict]:
    cursor = members_col.find({}, {"_id": 0}).sort("created_at", 1)
    return await cursor.to_list(length=500)


@router.get("/{member_id}")
async def get_member(member_id: str, current_manager: dict = Depends(get_current_manager)) -> dict:
    return await _get_member_or_404(member_id)


@router.patch("/{member_id}")
async def update_member(
    member_id: str, payload: MemberUpdateRequest, current_manager: dict = Depends(get_current_manager)
) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No fields provided to update")
    if "discipline" in updates and hasattr(updates["discipline"], "value"):
        updates["discipline"] = updates["discipline"].value
    updates["updated_at"] = now()

    member = await members_col.find_one_and_update(
        {"member_id": member_id},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not member:
        raise HTTPException(404, "Team member not found")
    return member


@router.delete("/{member_id}", status_code=204)
async def delete_member(member_id: str, current_manager: dict = Depends(get_current_manager)) -> None:
    await _get_member_or_404(member_id)
    await members_col.delete_one({"member_id": member_id})
    return None


@router.get("/{member_id}/dashboard")
async def member_dashboard(
    member_id: str, sprint_id: str, current_manager: dict = Depends(get_current_manager)
) -> dict:
    """
    Everything the PM needs on one screen for a single person: their tasks
    (with expectation + goal alignment), notes, recent check-ins, and any
    flags (stale / overdue / blocked).
    """
    member = await _get_member_or_404(member_id)
    tasks = (
        await tasks_col.find({"member_id": member_id, "sprint_id": sprint_id}, {"_id": 0})
        .sort("priority", 1)
        .to_list(length=1000)
    )

    task_ids = [t["task_id"] for t in tasks]
    notes = (
        await task_notes_col.find({"task_id": {"$in": task_ids}}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(length=500)
        if task_ids
        else []
    )
    notes_by_task: dict = {}
    for n in notes:
        notes_by_task.setdefault(n["task_id"], []).append(n)

    for t in tasks:
        t["notes"] = notes_by_task.get(t["task_id"], [])
        t["is_stale"] = is_stale(t)
        t["is_overdue"] = is_overdue(t)

    checkins = (
        await checkins_col.find({"member_id": member_id, "sprint_id": sprint_id}, {"_id": 0})
        .sort("checkin_date", -1)
        .to_list(length=30)
    )

    return {"member": member, "tasks": tasks, "recent_checkins": checkins}


@router.get("/{member_id}/open-tasks-pdf")
async def member_open_tasks_pdf(
    member_id: str, sprint_id: str, current_manager: dict = Depends(get_current_manager)
) -> Response:
    """
    A member-facing handout: every task Sprint Ops has on record as
    not-yet-done for this person in this sprint, rendered as a PDF meant to
    be handed directly to them. Same deterministic tasks_col query as the
    dashboard — nothing here is AI-generated.
    """
    member = await _get_member_or_404(member_id)
    sprint = await sprints_col.find_one({"sprint_id": sprint_id}, {"_id": 0})
    if not sprint:
        raise HTTPException(404, "Sprint not found")

    tasks = (
        await tasks_col.find(
            {"member_id": member_id, "sprint_id": sprint_id, "status": {"$ne": "done"}},
            {"_id": 0},
        )
        .sort("priority", 1)
        .to_list(length=1000)
    )

    goal_ids = [t["goal_id"] for t in tasks if t.get("goal_id")]
    goals = (
        await goals_col.find({"goal_id": {"$in": goal_ids}}, {"_id": 0}).to_list(length=200)
        if goal_ids
        else []
    )
    goal_title_by_id = {g["goal_id"]: g["title"] for g in goals}

    for t in tasks:
        t["is_stale"] = is_stale(t)
        t["is_overdue"] = is_overdue(t)
        t["goal_title"] = goal_title_by_id.get(t.get("goal_id"))

    day_info = sprint_day_number(sprint)
    working_days = sprint.get("working_days", 10)
    sprint_end_date = working_date_for_day(sprint, working_days)

    pdf_bytes = build_member_open_tasks_pdf(
        member=member,
        sprint=sprint,
        tasks=tasks,
        day_number=day_info["day_number"],
        working_days=working_days,
        sprint_end_date=sprint_end_date,
        manager_name=current_manager.get("name"),
        manager_email=current_manager.get("email"),
    )

    filename = f"{slugify(member['name'])}-open-tasks-{slugify(sprint['name'])}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
