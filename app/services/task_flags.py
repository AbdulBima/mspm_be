"""
app.services.task_flags
========================
Per-task derived flags computed on read, not stored: whether a task has
"gone quiet" (stale) or missed its due date (overdue), and when it most
recently entered "in_review".
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from app.services.clock import now

STALE_AFTER_DAYS = 2  # "no update in N days" — matches the RPM playbook's escalation cadence
OPEN_STATUSES = ("not_started", "in_progress", "blocked", "in_review")


def is_stale(task: dict, as_of: datetime | None = None) -> bool:
    """A task is 'gone quiet' if it's open and hasn't moved in STALE_AFTER_DAYS."""
    if task.get("status") not in OPEN_STATUSES:
        return False
    as_of = as_of or now()
    last_touch = task.get("last_progress_at") or task.get("updated_at") or task.get("created_at")
    if not last_touch:
        return False
    return (as_of - last_touch) > timedelta(days=STALE_AFTER_DAYS)


def is_overdue(task: dict, as_of: date | None = None) -> bool:
    due = task.get("due_date")
    if not due or task.get("status") == "done":
        return False
    as_of = as_of or date.today()
    due_date = due.date() if isinstance(due, datetime) else due
    return due_date < as_of


def in_review_since(task: dict) -> datetime | None:
    """
    Timestamp the task most recently entered "in_review", if it's sitting
    there now. Reads status_history rather than a separate field, same
    pattern as is_stale — status_history is the source of truth.
    """
    if task.get("status") != "in_review":
        return None
    for entry in reversed(task.get("status_history") or []):
        if entry.get("status") == "in_review":
            return entry.get("changed_at")
    return task.get("updated_at")
