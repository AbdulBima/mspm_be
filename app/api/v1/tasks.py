"""
Sprint Tracker (RPM Ops) — Task Routes
=========================================
Tasks are the unit of work: one member, one sprint, ideally one goal_id so
the alignment view can tell you whether it serves a stated sprint objective.

Every status change is appended to `status_history` so the burndown chart
can be reconstructed after the fact rather than needing a separate snapshot
job — status_history is the source of truth.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.api.deps import get_current_manager
from app.db.collections import goals_col, members_col, sprints_col, task_notes_col, tasks_col
from app.schemas.tasks import TaskCreateRequest, TaskNoteCreateRequest, TaskUpdateRequest
from app.services.clock import now, to_datetime
from app.services.ids import gen_id
from app.services.pdf import build_in_review_queue_pdf
from app.services.slugs import slugify
from app.services.task_flags import in_review_since, is_overdue, is_stale

router = APIRouter(prefix="/api/pm/tasks", tags=["pm-tracker:tasks"])


async def _get_task_or_404(task_id: str) -> dict:
    task = await tasks_col.find_one({"task_id": task_id}, {"_id": 0})
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@router.post("", status_code=201)
async def create_task(
    payload: TaskCreateRequest, current_manager: dict = Depends(get_current_manager)
) -> dict:
    if not await members_col.find_one({"member_id": payload.member_id}):
        raise HTTPException(404, "member_id does not match an existing team member")
    if payload.goal_id and not await goals_col.find_one({"goal_id": payload.goal_id}):
        raise HTTPException(404, "goal_id does not match an existing sprint goal")

    task_id = gen_id("TSK")
    ts = now()
    doc = {
        "task_id": task_id,
        "sprint_id": payload.sprint_id,
        "member_id": payload.member_id,
        "goal_id": payload.goal_id,
        "title": payload.title,
        "description": payload.description,
        "expectation": payload.expectation,
        "priority": payload.priority,
        "status": payload.status.value,
        "dependency_note": payload.dependency_note,
        "blocked_reason": None,
        "due_date": to_datetime(payload.due_date) if payload.due_date else None,
        "status_history": [{"status": payload.status.value, "changed_at": ts}],
        "last_progress_at": ts,
        "created_at": ts,
        "updated_at": ts,
    }
    await tasks_col.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("")
async def list_tasks(
    sprint_id: str,
    member_id: str | None = Query(None),
    goal_id: str | None = Query(None),
    status: str | None = Query(None),
    current_manager: dict = Depends(get_current_manager),
) -> list[dict]:
    query: dict = {"sprint_id": sprint_id}
    if member_id:
        query["member_id"] = member_id
    if goal_id:
        query["goal_id"] = goal_id
    if status:
        query["status"] = status
    tasks = await tasks_col.find(query, {"_id": 0}).sort("priority", 1).to_list(length=5000)
    for t in tasks:
        t["is_stale"] = is_stale(t)
        t["is_overdue"] = is_overdue(t)
    return tasks


# ─────────────────────────────────────────────────────────────────────────────
# NOTES (list-all) + IN-REVIEW PDF EXPORT — both registered ahead of
# GET /{task_id} on purpose: without this ordering, requests for
# /api/pm/tasks/notes or /api/pm/tasks/in-review-pdf get swallowed by the
# {task_id} route (task_id="notes" / task_id="in-review-pdf") instead of
# reaching these handlers. FastAPI matches routes in registration order, so
# this ordering is load-bearing.
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/notes")
async def list_all_notes(
    sprint_id: str,
    note_type: str | None = Query(None),
    member_id: str | None = Query(None),
    task_id: str | None = Query(None),
    current_manager: dict = Depends(get_current_manager),
) -> list[dict]:
    """
    Every task note logged against this sprint, newest first — powers the
    standalone Notes page. Notes only carry a task_id, so this joins back
    through the sprint's tasks to attach task title + member context.
    """
    task_query: dict = {"sprint_id": sprint_id}
    if member_id:
        task_query["member_id"] = member_id
    if task_id:
        task_query["task_id"] = task_id

    sprint_tasks = await tasks_col.find(
        task_query, {"_id": 0, "task_id": 1, "title": 1, "member_id": 1}
    ).to_list(length=5000)
    task_by_id = {t["task_id"]: t for t in sprint_tasks}
    if not task_by_id:
        return []

    note_query: dict = {"task_id": {"$in": list(task_by_id.keys())}}
    if note_type:
        note_query["note_type"] = note_type

    members = await members_col.find({}, {"_id": 0, "member_id": 1, "name": 1, "color_tag": 1}).to_list(
        length=500
    )
    member_by_id = {m["member_id"]: m for m in members}

    notes = await task_notes_col.find(note_query, {"_id": 0}).sort("created_at", -1).to_list(length=2000)

    enriched = []
    for n in notes:
        task = task_by_id.get(n["task_id"], {})
        member = member_by_id.get(task.get("member_id"), {})
        enriched.append(
            {
                **n,
                "task_title": task.get("title", "Unknown task"),
                "member_id": task.get("member_id"),
                "member_name": member.get("name", "Unassigned"),
                "member_color": member.get("color_tag"),
            }
        )
    return enriched


@router.get("/in-review-pdf")
async def in_review_tasks_pdf(
    sprint_id: str, current_manager: dict = Depends(get_current_manager)
) -> Response:
    """
    Cross-team snapshot of everything sitting in review for this sprint,
    rendered as a PDF working queue — oldest-waiting first. Must stay above
    GET /{task_id} in this file or that route shadows it (see note above).
    """
    sprint = await sprints_col.find_one({"sprint_id": sprint_id}, {"_id": 0})
    if not sprint:
        raise HTTPException(404, "Sprint not found")

    tasks = await tasks_col.find({"sprint_id": sprint_id, "status": "in_review"}, {"_id": 0}).to_list(
        length=5000
    )

    member_ids = list({t["member_id"] for t in tasks if t.get("member_id")})
    members = (
        await members_col.find({"member_id": {"$in": member_ids}}, {"_id": 0}).to_list(length=500)
        if member_ids
        else []
    )
    member_by_id = {m["member_id"]: m for m in members}

    goal_ids = [t["goal_id"] for t in tasks if t.get("goal_id")]
    goals = (
        await goals_col.find({"goal_id": {"$in": goal_ids}}, {"_id": 0}).to_list(length=200)
        if goal_ids
        else []
    )
    goal_title_by_id = {g["goal_id"]: g["title"] for g in goals}

    for t in tasks:
        t["is_overdue"] = is_overdue(t)
        t["goal_title"] = goal_title_by_id.get(t.get("goal_id"))
        m = member_by_id.get(t.get("member_id"), {})
        t["member_name"] = m.get("name", "Unassigned")
        t["member_color"] = m.get("color_tag")
        since = in_review_since(t)
        t["waiting_days"] = (now() - since).days if since else None

    # oldest-waiting first, priority as tiebreaker
    tasks.sort(key=lambda t: (-(t["waiting_days"] or 0), t["priority"]))

    pdf_bytes = build_in_review_queue_pdf(
        sprint=sprint, tasks=tasks, generated_by=current_manager.get("name")
    )

    filename = f"in-review-{slugify(sprint['name'])}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{task_id}")
async def get_task(task_id: str, current_manager: dict = Depends(get_current_manager)) -> dict:
    task = await _get_task_or_404(task_id)
    notes = (
        await task_notes_col.find({"task_id": task_id}, {"_id": 0}).sort("created_at", -1).to_list(length=500)
    )
    task["notes"] = notes
    task["is_stale"] = is_stale(task)
    task["is_overdue"] = is_overdue(task)
    return task


@router.patch("/{task_id}")
async def update_task(
    task_id: str, payload: TaskUpdateRequest, current_manager: dict = Depends(get_current_manager)
) -> dict:
    task = await _get_task_or_404(task_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No fields provided to update")
    ts = now()

    if "due_date" in updates and updates["due_date"] is not None:
        updates["due_date"] = to_datetime(updates["due_date"])

    sprint_changed = False
    if "sprint_id" in updates and updates["sprint_id"] != task["sprint_id"]:
        if not await sprints_col.find_one({"sprint_id": updates["sprint_id"]}):
            raise HTTPException(404, "Target sprint not found")
        sprint_changed = True
        # a goal belongs to the sprint it was created under — clear it on move unless
        # the caller also supplied a new goal_id for the destination sprint.
        if "goal_id" not in updates:
            updates["goal_id"] = None

    status_changed = False
    if "status" in updates:
        new_status = updates["status"].value if hasattr(updates["status"], "value") else updates["status"]
        updates["status"] = new_status
        status_changed = new_status != task["status"]

    updates["updated_at"] = ts
    if status_changed:
        updates["last_progress_at"] = ts

    await tasks_col.update_one({"task_id": task_id}, {"$set": updates})
    if status_changed:
        await tasks_col.update_one(
            {"task_id": task_id},
            {"$push": {"status_history": {"status": updates["status"], "changed_at": ts}}},
        )
    if sprint_changed:
        from_sprint = await sprints_col.find_one({"sprint_id": task["sprint_id"]}, {"_id": 0, "name": 1})
        await task_notes_col.insert_one(
            {
                "note_id": gen_id("NOTE"),
                "task_id": task_id,
                "author": current_manager.get("name", "PM"),
                "note_type": "update",
                "content": f"Carried over from {from_sprint['name'] if from_sprint else task['sprint_id']}.",
                "created_at": ts,
            }
        )
    return await _get_task_or_404(task_id)


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: str, current_manager: dict = Depends(get_current_manager)) -> None:
    await _get_task_or_404(task_id)
    await tasks_col.delete_one({"task_id": task_id})
    await task_notes_col.delete_many({"task_id": task_id})
    return None


# ─────────────────────────────────────────────────────────────────────────────
# NOTES — the PM's running commentary on a task (progress, blockers, decisions)
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/{task_id}/notes", status_code=201)
async def add_task_note(
    task_id: str, payload: TaskNoteCreateRequest, current_manager: dict = Depends(get_current_manager)
) -> dict:
    await _get_task_or_404(task_id)
    note_id = gen_id("NOTE")
    ts = now()
    doc = {
        "note_id": note_id,
        "task_id": task_id,
        "author": payload.author or current_manager.get("name", "PM"),
        "note_type": payload.note_type.value,
        "content": payload.content,
        "created_at": ts,
    }
    await task_notes_col.insert_one(doc)
    # a note counts as forward motion even if the status didn't change
    await tasks_col.update_one({"task_id": task_id}, {"$set": {"last_progress_at": ts, "updated_at": ts}})
    doc.pop("_id", None)
    return doc


@router.delete("/notes/{note_id}", status_code=204)
async def delete_task_note(note_id: str, current_manager: dict = Depends(get_current_manager)) -> None:
    await task_notes_col.delete_one({"note_id": note_id})
    return None
