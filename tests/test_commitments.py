"""Tests for app.services.commitments — the shared standup-commitment classifier."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.services.commitments import classify_commitment


def test_task_deleted_when_task_missing() -> None:
    assert classify_commitment(None, datetime.utcnow(), datetime.utcnow()) == "task_deleted"


def test_done_task() -> None:
    task = {"status": "done"}
    assert classify_commitment(task, datetime.utcnow(), datetime.utcnow()) == "done"


def test_blocked_task() -> None:
    task = {"status": "blocked"}
    assert classify_commitment(task, datetime.utcnow(), datetime.utcnow()) == "blocked"


def test_progressing_when_progress_after_commitment() -> None:
    commitment_date = datetime.utcnow() - timedelta(days=2)
    task = {"status": "in_progress", "last_progress_at": datetime.utcnow() - timedelta(days=1)}
    assert classify_commitment(task, commitment_date, datetime.utcnow()) == "progressing"


def test_too_soon_when_committed_today() -> None:
    now = datetime.utcnow()
    task = {"status": "in_progress", "last_progress_at": None}
    assert classify_commitment(task, now, now) == "too_soon"


def test_stale_when_no_progress_since_commitment() -> None:
    now = datetime.utcnow()
    commitment_date = now - timedelta(days=3)
    task = {"status": "in_progress", "last_progress_at": now - timedelta(days=5)}
    assert classify_commitment(task, commitment_date, now) == "stale"
