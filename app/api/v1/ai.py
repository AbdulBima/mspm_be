"""
Sprint Tracker (RPM Ops) — AI Assistant Routes
=================================================
Two AI-powered endpoints over the current state of a sprint:

- POST /ask — open-ended NLP Q&A grounded in a full sprint snapshot (goals,
  members, tasks, risks, check-ins, meetings).
- GET /standup-summary — a narrative summary of one day's standup: who
  committed to what, and whether it's on track, stalled, or blocked, using
  the same app.services.commitments.classify_commitment logic as the
  accountability endpoint in api/v1/tracking.py.

Both follow the same "structured data first, AI narrates on top" boundary
used in report generation (app.services.narrative) — the model only sees a
compiled JSON snapshot and is instructed not to invent facts beyond it.
"""

from __future__ import annotations

import json
from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_current_manager
from app.db.collections import (
    checkins_col,
    decisions_col,
    goals_col,
    meetings_col,
    members_col,
    risks_col,
    sprints_col,
    tasks_col,
)
from app.schemas.ai import AIAskRequest
from app.services import narrative
from app.services.clock import now, to_datetime
from app.services.commitments import classify_commitment

router = APIRouter(prefix="/api/pm/ai", tags=["pm-tracker:ai"])


async def _compile_snapshot(sprint_id: str) -> dict:
    sprint = await sprints_col.find_one({"sprint_id": sprint_id}, {"_id": 0})
    if not sprint:
        raise HTTPException(404, "Sprint not found")

    goals = await goals_col.find({"sprint_id": sprint_id}, {"_id": 0}).sort("order", 1).to_list(length=200)
    members = await members_col.find({}, {"_id": 0}).to_list(length=500)
    member_by_id = {m["member_id"]: m for m in members}
    goal_title_by_id = {g["goal_id"]: g["title"] for g in goals}

    tasks = await tasks_col.find({"sprint_id": sprint_id}, {"_id": 0}).to_list(length=5000)

    def _task_brief(t: dict) -> dict:
        m = member_by_id.get(t.get("member_id"), {})
        return {
            "title": t["title"],
            "member": m.get("name", "Unassigned"),
            "status": t["status"],
            "priority": t["priority"],
            "goal": goal_title_by_id.get(t.get("goal_id"), "Unlinked"),
            "due_date": t["due_date"].isoformat() if t.get("due_date") else None,
        }

    risks = await risks_col.find({"sprint_id": sprint_id, "status": "open"}, {"_id": 0}).to_list(length=500)
    decisions = (
        await decisions_col.find({"sprint_id": sprint_id}, {"_id": 0})
        .sort("decided_on", -1)
        .to_list(length=100)
    )
    checkins = (
        await checkins_col.find({"sprint_id": sprint_id}, {"_id": 0})
        .sort("checkin_date", -1)
        .to_list(length=100)
    )
    meetings = (
        await meetings_col.find({"sprint_id": sprint_id}, {"_id": 0})
        .sort("meeting_date", -1)
        .to_list(length=50)
    )

    return {
        "sprint_name": sprint["name"],
        "sprint_theme": sprint.get("theme"),
        "sprint_status": sprint.get("status"),
        "success_measures": sprint.get("success_measures", []),
        "critical_path": sprint.get("critical_path", []),
        "goals": [{"title": g["title"], "description": g.get("description")} for g in goals],
        "team_members": [
            {"name": m["name"], "role": m["role_title"], "discipline": m["discipline"]}
            for m in members
            if m.get("active", True)
        ],
        "tasks": [_task_brief(t) for t in tasks],
        "open_risks_and_blockers": [
            {
                "title": r["title"],
                "kind": r["kind"],
                "severity": r["severity"],
                "owner": member_by_id.get(r.get("owner_member_id"), {}).get("name"),
            }
            for r in risks
        ],
        "recent_decisions": [
            {"decision": d["decision"], "context": d.get("context")} for d in decisions[:30]
        ],
        "recent_checkins": [
            {
                "member": member_by_id.get(c.get("member_id"), {}).get("name", "Unknown"),
                "flag": c["flag"],
                "blockers": c.get("blockers"),
            }
            for c in checkins[:40]
        ],
        "recent_meetings": [
            {
                "type": m["meeting_type"],
                "open_action_items": [ai["text"] for ai in m.get("action_items", []) if not ai.get("done")],
            }
            for m in meetings[:20]
        ],
    }


@router.post("/ask")
async def ask(payload: AIAskRequest, current_manager: dict = Depends(get_current_manager)) -> dict:
    if not narrative.is_configured():
        raise HTTPException(503, "AI assistant isn't configured — GROQ_API_KEY is missing.")

    snapshot = await _compile_snapshot(payload.sprint_id)

    system_prompt = (
        "You are a sprint operations assistant for a Product Manager. You answer questions about the "
        "current sprint using ONLY the JSON snapshot provided below — team members, goals, tasks, risks, "
        "decisions, check-ins, and meetings. Never invent a task, person, or fact that isn't in the data. "
        "If the answer isn't in the data, say so plainly instead of guessing. Be concise and direct — answer "
        "in plain text (a short paragraph or a tight bulleted list), no markdown headers, no restating the "
        "question.\n\n"
        f"SPRINT SNAPSHOT:\n{json.dumps(snapshot, default=str, indent=2)}"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for turn in payload.history[-12:]:  # cap context growth on long-running chats
        if turn.role in ("user", "assistant"):
            messages.append({"role": turn.role, "content": turn.content})
    messages.append({"role": "user", "content": payload.question})

    answer = narrative.chat(messages, temperature=0.2, max_tokens=700)
    if answer is None:
        raise HTTPException(502, "The AI assistant couldn't answer that just now. Try again in a moment.")

    return {"answer": answer, "sprint_id": payload.sprint_id}


# ─────────────────────────────────────────────────────────────────────────────
# STANDUP DAY SUMMARY
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/standup-summary")
async def standup_day_summary(
    sprint_id: str,
    day: date_type = Query(..., description="The standup date to summarize, YYYY-MM-DD"),
    current_manager: dict = Depends(get_current_manager),
) -> dict:
    """AI narrative summary of everyone's standup commitments for a single day."""
    day_dt = to_datetime(day)
    checkins = await checkins_col.find({"sprint_id": sprint_id, "checkin_date": day_dt}, {"_id": 0}).to_list(
        length=200
    )

    if not checkins:
        return {
            "summary": "No standup commitments were logged for this day.",
            "date": day.isoformat(),
            "sprint_id": sprint_id,
            "checkin_count": 0,
        }

    if not narrative.is_configured():
        raise HTTPException(503, "AI assistant isn't configured — GROQ_API_KEY is missing.")

    sprint = await sprints_col.find_one({"sprint_id": sprint_id}, {"_id": 0})
    goals = await goals_col.find({"sprint_id": sprint_id}, {"_id": 0}).sort("order", 1).to_list(length=200)
    goal_title_by_id = {g["goal_id"]: g["title"] for g in goals}

    tasks = await tasks_col.find({"sprint_id": sprint_id}, {"_id": 0}).to_list(length=5000)
    task_by_id = {t["task_id"]: t for t in tasks}
    members = await members_col.find({}, {"_id": 0}).to_list(length=500)
    member_by_id = {m["member_id"]: m for m in members}
    now_ts = now()

    day_brief = []
    for c in checkins:
        member = member_by_id.get(c["member_id"])
        committed = []
        for tid in c.get("committed_task_ids") or []:
            task = task_by_id.get(tid)
            committed.append(
                {
                    "task": task["title"] if task else "Deleted task",
                    "status": classify_commitment(task, c["checkin_date"], now_ts),
                    # so the model can name which sprint goal this work serves,
                    # or say plainly that it doesn't map to any stated goal
                    "goal": goal_title_by_id.get(task.get("goal_id")) if task else None,
                }
            )
        day_brief.append(
            {
                "member": member["name"] if member else "Unknown",
                "flag": c.get("flag"),
                "notes": c.get("today_plan"),
                "committed_tasks": committed,
            }
        )

    snapshot = {
        "sprint_name": sprint["name"] if sprint else None,
        "sprint_theme": sprint.get("theme") if sprint else None,
        "sprint_goals": [g["title"] for g in goals],
        "standup": day_brief,
    }

    system_prompt = (
        "You are summarizing one day's team standup for a Product Manager, to sit alongside a raw log "
        "they can already see in full — their name, their notes, and their committed tasks. Do not "
        "restate that log. Your only value is connecting it to two things the raw log can't show: (1) "
        "which sprint goal each person's work actually serves, and (2) a candid read on where things "
        "stand.\n\n"
        "Write one line per person: their name, then what they're specifically doing — paraphrase their "
        "notes and task titles in your own words, concretely (not 'working on their tasks'), then which "
        "sprint goal it maps to (the goal field on each task tells you this; if it's null, say the work is "
        "unlinked to a stated goal), then a short flag: on track / needs attention / blocked. A task's "
        "status field means: done, progressing (has moved since they committed to it), blocked, stale (no "
        "progress since they committed — worth a direct follow-up), or too_soon (just committed today, "
        "nothing to judge yet).\n\n"
        "After the per-person lines, add one or two sentences on goal coverage: which of sprint_goals got "
        "real attention today, and which got none from anyone.\n\n"
        "Plain text. Simple '-' bullets are fine, no markdown headers. Never write filler like 'the team "
        "is generally on track' — every line must reference something specific from the data. Don't "
        "restate these instructions.\n\n"
        f"STANDUP DATA FOR {day.isoformat()}:\n{json.dumps(snapshot, default=str, indent=2)}"
    )

    summary = narrative.chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Summarize today's standup, person by person, tied to sprint goals."},
        ],
        temperature=0.25,
        max_tokens=800,
    )
    if summary is None:
        raise HTTPException(502, "Couldn't generate the summary just now. Try again in a moment.")

    return {
        "summary": summary,
        "date": day.isoformat(),
        "sprint_id": sprint_id,
        "checkin_count": len(checkins),
    }
