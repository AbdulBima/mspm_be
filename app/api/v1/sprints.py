"""
Sprint Tracker (RPM Ops) — Sprint & Goal Routes
==================================================
Sprints are the top-level container ("Sprint 35", 10 working days). Goals are
the stated objectives for that sprint — every task should ideally map to one,
which is what powers the alignment view (GET /sprints/{id}/alignment).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pymongo import ReturnDocument

from app.api.deps import get_current_manager
from app.db.collections import (
    goals_col,
    meetings_col,
    members_col,
    risks_col,
    sprints_col,
    task_notes_col,
    tasks_col,
)
from app.schemas.enums import SprintStatus
from app.schemas.sprints import (
    CarryOverRequest,
    GoalCreateRequest,
    GoalUpdateRequest,
    SprintCreateRequest,
    SprintUpdateRequest,
)
from app.services.alignment import alignment_breakdown
from app.services.burndown import build_burndown
from app.services.clock import now, to_datetime
from app.services.ids import gen_id
from app.services.sprint_calendar import sprint_day_number
from app.services.task_flags import is_overdue, is_stale

router = APIRouter(prefix="/api/pm/sprints", tags=["pm-tracker:sprints"])


async def _get_sprint_or_404(sprint_id: str) -> dict:
    sprint = await sprints_col.find_one({"sprint_id": sprint_id}, {"_id": 0})
    if not sprint:
        raise HTTPException(404, "Sprint not found")
    return sprint


# ─────────────────────────────────────────────────────────────────────────────
# SPRINT CRUD
# ─────────────────────────────────────────────────────────────────────────────


@router.post("", status_code=201)
async def create_sprint(
    payload: SprintCreateRequest, current_manager: dict = Depends(get_current_manager)
) -> dict:
    sprint_id = gen_id("SPR")
    ts = now()
    doc = {
        "sprint_id": sprint_id,
        "name": payload.name,
        "theme": payload.theme,
        "start_date": to_datetime(payload.start_date),
        "working_days": payload.working_days,
        "status": SprintStatus.PLANNING.value,
        "success_measures": payload.success_measures,
        "critical_path": payload.critical_path,
        "out_of_scope": payload.out_of_scope,
        "notes": "",
        "created_by": current_manager["manager_id"],
        "created_at": ts,
        "updated_at": ts,
    }
    await sprints_col.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("")
async def list_sprints(current_manager: dict = Depends(get_current_manager)) -> list[dict]:
    cursor = sprints_col.find({}, {"_id": 0}).sort("start_date", -1)
    return await cursor.to_list(length=200)


@router.get("/active")
async def get_active_sprint(current_manager: dict = Depends(get_current_manager)) -> dict:
    sprint = await sprints_col.find_one({"status": SprintStatus.ACTIVE.value}, {"_id": 0})
    if not sprint:
        # fall back to the most recently created sprint so a fresh install isn't a dead end
        sprint = await sprints_col.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
    if not sprint:
        raise HTTPException(404, "No sprints exist yet. Create one to get started.")
    return sprint


@router.get("/{sprint_id}")
async def get_sprint(sprint_id: str, current_manager: dict = Depends(get_current_manager)) -> dict:
    return await _get_sprint_or_404(sprint_id)


@router.patch("/{sprint_id}")
async def update_sprint(
    sprint_id: str, payload: SprintUpdateRequest, current_manager: dict = Depends(get_current_manager)
) -> dict:
    await _get_sprint_or_404(sprint_id)

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No fields provided to update")

    if "status" in updates:
        updates["status"] = (
            updates["status"].value if hasattr(updates["status"], "value") else updates["status"]
        )
        if updates["status"] == SprintStatus.ACTIVE.value:
            # demote any other active sprint — only one sprint is "the current one"
            await sprints_col.update_many(
                {"sprint_id": {"$ne": sprint_id}, "status": SprintStatus.ACTIVE.value},
                {"$set": {"status": SprintStatus.COMPLETED.value, "updated_at": now()}},
            )
    updates["updated_at"] = now()

    updated = await sprints_col.find_one_and_update(
        {"sprint_id": sprint_id},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not updated:
        raise HTTPException(404, "Sprint not found")
    return updated


@router.delete("/{sprint_id}", status_code=204)
async def delete_sprint(sprint_id: str, current_manager: dict = Depends(get_current_manager)) -> None:
    await _get_sprint_or_404(sprint_id)
    await sprints_col.delete_one({"sprint_id": sprint_id})
    await goals_col.delete_many({"sprint_id": sprint_id})
    await tasks_col.delete_many({"sprint_id": sprint_id})
    return None


# ─────────────────────────────────────────────────────────────────────────────
# GOALS
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/{sprint_id}/goals", status_code=201)
async def create_goal(
    sprint_id: str, payload: GoalCreateRequest, current_manager: dict = Depends(get_current_manager)
) -> dict:
    await _get_sprint_or_404(sprint_id)
    goal_id = gen_id("GOAL")
    ts = now()
    order = payload.order
    if order is None:
        order = await goals_col.count_documents({"sprint_id": sprint_id})
    doc = {
        "goal_id": goal_id,
        "sprint_id": sprint_id,
        "title": payload.title,
        "description": payload.description,
        "order": order,
        "created_at": ts,
        "updated_at": ts,
    }
    await goals_col.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/{sprint_id}/goals")
async def list_goals(sprint_id: str, current_manager: dict = Depends(get_current_manager)) -> list[dict]:
    cursor = goals_col.find({"sprint_id": sprint_id}, {"_id": 0}).sort("order", 1)
    return await cursor.to_list(length=200)


@router.patch("/goals/{goal_id}")
async def update_goal(
    goal_id: str, payload: GoalUpdateRequest, current_manager: dict = Depends(get_current_manager)
) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No fields provided to update")
    updates["updated_at"] = now()

    goal = await goals_col.find_one_and_update(
        {"goal_id": goal_id}, {"$set": updates}, return_document=ReturnDocument.AFTER, projection={"_id": 0}
    )
    if not goal:
        raise HTTPException(404, "Goal not found")
    return goal


@router.delete("/goals/{goal_id}", status_code=204)
async def delete_goal(goal_id: str, current_manager: dict = Depends(get_current_manager)) -> None:
    await goals_col.delete_one({"goal_id": goal_id})
    await tasks_col.update_many({"goal_id": goal_id}, {"$set": {"goal_id": None}})
    return None


# ─────────────────────────────────────────────────────────────────────────────
# COMPUTED VIEWS — health, alignment, burndown
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/{sprint_id}/health")
async def sprint_health(sprint_id: str, current_manager: dict = Depends(get_current_manager)) -> dict:
    """
    The first thing the PM should see every morning: where are we in the
    sprint, what's moving, what's stuck, what's gone quiet, what's overdue —
    straight from the RPM playbook's daily checklist.
    """
    sprint = await _get_sprint_or_404(sprint_id)
    tasks = await tasks_col.find({"sprint_id": sprint_id}, {"_id": 0}).to_list(length=5000)
    members = await members_col.find({}, {"_id": 0}).to_list(length=500)
    member_by_id = {m["member_id"]: m for m in members}

    # This view is about progress against the sprint's stated goals, so tasks
    # with no goal_id (not yet triaged into the RPM plan) don't count toward
    # any of these numbers. Unaligned work is still visible via the alignment
    # view, which is specifically built to surface it.
    tasks = [t for t in tasks if t.get("goal_id")]

    day_info = sprint_day_number(sprint)

    status_counts: dict = {}
    for t in tasks:
        status_counts[t["status"]] = status_counts.get(t["status"], 0) + 1

    stale = [t for t in tasks if is_stale(t)]
    overdue = [t for t in tasks if is_overdue(t)]
    blocked = [t for t in tasks if t["status"] == "blocked"]
    waiting_review = [t for t in tasks if t["status"] == "in_review"]

    open_risks = await risks_col.count_documents({"sprint_id": sprint_id, "status": "open"})

    # per-member rollup so "no one becomes invisible"
    per_member: dict = {}
    for t in tasks:
        mid = t.get("member_id")
        if mid not in per_member:
            m = member_by_id.get(mid, {})
            per_member[mid] = {
                "member_id": mid,
                "name": m.get("name", "Unknown"),
                "role_title": m.get("role_title", ""),
                "task_count": 0,
                "done_count": 0,
                "in_review_count": 0,
                "blocked_count": 0,
                "stale_count": 0,
                "overdue_count": 0,
            }
        bucket = per_member[mid]
        bucket["task_count"] += 1
        if t["status"] == "done":
            bucket["done_count"] += 1
        if t["status"] == "in_review":
            bucket["in_review_count"] += 1
        if t["status"] == "blocked":
            bucket["blocked_count"] += 1
        if is_stale(t):
            bucket["stale_count"] += 1
        if is_overdue(t):
            bucket["overdue_count"] += 1

    total = len(tasks)
    done = status_counts.get("done", 0)
    in_review_total = status_counts.get("in_review", 0)
    blocked_total = len(blocked)
    # In-review work is finished from the doer's side and just waiting on
    # sign-off, so it counts the same as "done" toward completion. Blocked
    # tasks are excluded from the denominator entirely: they're stuck
    # waiting on someone else, not a sign the team hasn't done the work, so
    # they shouldn't silently depress the percentage on top of being
    # flagged separately below.
    non_blocked_total = total - blocked_total
    completed_weight = done + in_review_total

    def _brief(t: dict) -> dict:
        return {
            "task_id": t["task_id"],
            "title": t["title"],
            "member_id": t.get("member_id"),
            "status": t["status"],
        }

    return {
        "sprint_id": sprint_id,
        "day_number": day_info["day_number"],
        "working_days": day_info["working_days"],
        "status": sprint["status"],
        "total_tasks": total,
        "completion_pct": round((completed_weight / non_blocked_total) * 100) if non_blocked_total else 0,
        "status_counts": status_counts,
        "open_risks": open_risks,
        "stale_tasks": [_brief(t) for t in stale],
        "overdue_tasks": [_brief(t) for t in overdue],
        "blocked_tasks": [_brief(t) for t in blocked],
        "waiting_review_tasks": [_brief(t) for t in waiting_review],
        "per_member": list(per_member.values()),
    }


@router.get("/{sprint_id}/alignment")
async def sprint_alignment(sprint_id: str, current_manager: dict = Depends(get_current_manager)) -> dict:
    """How well day-to-day activity maps to the sprint's stated goals."""
    await _get_sprint_or_404(sprint_id)
    goals = await goals_col.find({"sprint_id": sprint_id}, {"_id": 0}).sort("order", 1).to_list(length=200)
    tasks = await tasks_col.find({"sprint_id": sprint_id}, {"_id": 0}).to_list(length=5000)
    return alignment_breakdown(goals, tasks)


@router.get("/{sprint_id}/burndown")
async def sprint_burndown(sprint_id: str, current_manager: dict = Depends(get_current_manager)) -> dict:
    sprint = await _get_sprint_or_404(sprint_id)
    tasks = await tasks_col.find({"sprint_id": sprint_id}, {"_id": 0}).to_list(length=5000)
    return {"series": build_burndown(sprint, tasks)}


# ─────────────────────────────────────────────────────────────────────────────
# HANDOVER — end-of-sprint summary + carry-over into the next sprint
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/{sprint_id}/handover")
async def sprint_handover(sprint_id: str, current_manager: dict = Depends(get_current_manager)) -> dict:
    """
    Everything the Friday 'Sprint handover' deliverable needs: what's still
    open, what's still at risk, and what action items never got closed — so
    nothing quietly falls out of scope between sprints.
    """
    sprint = await _get_sprint_or_404(sprint_id)
    members = await members_col.find({}, {"_id": 0}).to_list(length=500)
    member_by_id = {m["member_id"]: m for m in members}

    tasks = (
        await tasks_col.find({"sprint_id": sprint_id, "status": {"$ne": "done"}}, {"_id": 0})
        .sort("priority", 1)
        .to_list(length=5000)
    )

    open_risks = (
        await risks_col.find({"sprint_id": sprint_id, "status": "open"}, {"_id": 0})
        .sort("severity", -1)
        .to_list(length=1000)
    )

    meetings = await meetings_col.find({"sprint_id": sprint_id}, {"_id": 0}).to_list(length=500)
    open_action_items = [
        {
            **ai,
            "meeting_id": m["meeting_id"],
            "meeting_type": m["meeting_type"],
            "meeting_date": m["meeting_date"].isoformat(),
        }
        for m in meetings
        for ai in m.get("action_items", [])
        if not ai.get("done")
    ]

    incomplete_tasks = [
        {
            "task_id": t["task_id"],
            "title": t["title"],
            "status": t["status"],
            "member_id": t["member_id"],
            "member_name": member_by_id.get(t["member_id"], {}).get("name", "Unknown"),
            "goal_id": t.get("goal_id"),
            "is_stale": is_stale(t),
            "is_overdue": is_overdue(t),
        }
        for t in tasks
    ]

    return {
        "sprint_id": sprint_id,
        "sprint_name": sprint["name"],
        "incomplete_tasks": incomplete_tasks,
        "open_risks": [
            {"risk_id": r["risk_id"], "title": r["title"], "severity": r["severity"], "kind": r["kind"]}
            for r in open_risks
        ],
        "open_action_items": open_action_items,
    }


@router.post("/{sprint_id}/carry-over")
async def carry_over(
    sprint_id: str, payload: CarryOverRequest, current_manager: dict = Depends(get_current_manager)
) -> dict:
    """
    Moves unfinished work from this sprint into the named target sprint —
    the thing a 10-day sprint boundary otherwise has no answer for. Tasks
    keep their status and history; their goal_id is cleared since goals are
    scoped to the sprint they were defined under (re-link from the new
    sprint's Goals page). Open risks can optionally carry over too.
    """
    from_sprint = await _get_sprint_or_404(sprint_id)
    to_sprint = await sprints_col.find_one({"sprint_id": payload.to_sprint_id})
    if not to_sprint:
        raise HTTPException(404, "Target sprint not found")
    if payload.to_sprint_id == sprint_id:
        raise HTTPException(400, "Target sprint must be different from the source sprint")

    query: dict = {"sprint_id": sprint_id, "status": {"$ne": "done"}}
    if payload.task_ids:
        query["task_id"] = {"$in": payload.task_ids}
    tasks_to_move = await tasks_col.find(query, {"_id": 0, "task_id": 1}).to_list(length=5000)
    task_ids = [t["task_id"] for t in tasks_to_move]

    ts = now()
    if task_ids:
        await tasks_col.update_many(
            {"task_id": {"$in": task_ids}},
            {"$set": {"sprint_id": payload.to_sprint_id, "goal_id": None, "updated_at": ts}},
        )
        note_docs = [
            {
                "note_id": gen_id("NOTE"),
                "task_id": tid,
                "author": current_manager.get("name", "PM"),
                "note_type": "update",
                "content": f"Carried over from {from_sprint['name']}.",
                "created_at": ts,
            }
            for tid in task_ids
        ]
        await task_notes_col.insert_many(note_docs)

    risks_moved = 0
    if payload.carry_open_risks:
        result = await risks_col.update_many(
            {"sprint_id": sprint_id, "status": "open"},
            {"$set": {"sprint_id": payload.to_sprint_id}},
        )
        risks_moved = result.modified_count

    return {
        "from_sprint": from_sprint["name"],
        "to_sprint": to_sprint["name"],
        "tasks_carried": len(task_ids),
        "risks_carried": risks_moved,
    }
