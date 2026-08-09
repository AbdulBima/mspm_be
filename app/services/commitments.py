"""
app.services.commitments
=========================
Single source of truth for classifying a standup commitment (a check-in's
committed_task_ids entry) against what actually happened to the task
afterward.

Used by both the accountability endpoint (api/v1/tracking.py::
checkin_accountability) and the AI standup summary (api/v1/ai.py::
standup_day_summary) — previously duplicated verbatim in both route files.
That duplication meant a future change to the classification rules could
silently make the two disagree with each other; centralizing it here removes
that risk.
"""

from __future__ import annotations

from datetime import datetime


def classify_commitment(task: dict | None, commitment_date: datetime, now_ts: datetime) -> str:
    """
    done         — task is complete
    blocked      — task is blocked
    progressing  — has moved since the commitment was made
    stale        — no progress since the commitment was made (worth a follow-up)
    too_soon     — committed today; nothing to judge yet
    task_deleted — the committed task no longer exists
    """
    if not task:
        return "task_deleted"
    if task["status"] == "done":
        return "done"
    if task["status"] == "blocked":
        return "blocked"
    last_progress = task.get("last_progress_at")
    if last_progress and last_progress > commitment_date:
        return "progressing"
    if commitment_date.date() >= now_ts.date():
        return "too_soon"
    return "stale"
