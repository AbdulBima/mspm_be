"""
app.services.alignment
=======================
For each sprint goal: how many activities serve it, and how much of that
work is done — i.e. whether day-to-day activity is actually tracking toward
the stated sprint objectives. Tasks with no goal_id are surfaced separately
as 'unaligned' so drift is visible.
"""

from __future__ import annotations


def alignment_breakdown(goals: list[dict], tasks: list[dict]) -> dict:
    """
    completion_pct treats in_review the same as done (work is finished, just
    waiting on sign-off), and excludes blocked tasks from the denominator
    entirely — a task stuck waiting on someone else shouldn't drag down the
    percentage the same way an untouched task does. Blocked work is still
    fully visible via blocked_count; it just isn't penalized twice.
    """
    by_goal = {
        g["goal_id"]: {
            "goal_id": g["goal_id"],
            "title": g["title"],
            "task_count": 0,
            "done_count": 0,
            "in_review_count": 0,
            "blocked_count": 0,
            "status_breakdown": {},
        }
        for g in goals
    }

    unaligned = []
    for t in tasks:
        gid = t.get("goal_id")
        status = t.get("status", "not_started")
        if gid and gid in by_goal:
            bucket = by_goal[gid]
            bucket["task_count"] += 1
            bucket["status_breakdown"][status] = bucket["status_breakdown"].get(status, 0) + 1
            if status == "done":
                bucket["done_count"] += 1
            if status == "in_review":
                bucket["in_review_count"] += 1
            if status == "blocked":
                bucket["blocked_count"] += 1
        else:
            unaligned.append({"task_id": t["task_id"], "title": t["title"], "member_id": t.get("member_id")})

    goal_list = []
    for g in by_goal.values():
        completed = g["done_count"] + g["in_review_count"]
        non_blocked = g["task_count"] - g["blocked_count"]
        pct = round((completed / non_blocked) * 100) if non_blocked > 0 else 0
        goal_list.append({**g, "completion_pct": pct})

    total_tasks = len(tasks)
    aligned_tasks = total_tasks - len(unaligned)
    alignment_score = round((aligned_tasks / total_tasks) * 100) if total_tasks else 100

    return {
        "goals": goal_list,
        "unaligned_tasks": unaligned,
        "alignment_score": alignment_score,  # % of all logged activity that maps to a stated sprint goal
    }
