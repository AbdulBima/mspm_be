"""Tests for app.services.task_flags — pure functions, no DB required."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from app.services.task_flags import is_overdue, is_stale


def _task(**overrides):
    base = {
        "status": "in_progress",
        "last_progress_at": datetime.utcnow() - timedelta(days=1),
        "due_date": None,
    }
    base.update(overrides)
    return base


def test_is_stale_true_after_threshold() -> None:
    task = _task(last_progress_at=datetime.utcnow() - timedelta(days=5))
    assert is_stale(task) is True


def test_is_stale_false_when_recent() -> None:
    task = _task(last_progress_at=datetime.utcnow() - timedelta(hours=2))
    assert is_stale(task) is False


def test_is_stale_false_for_closed_statuses() -> None:
    task = _task(status="done", last_progress_at=datetime.utcnow() - timedelta(days=10))
    assert is_stale(task) is False


def test_is_overdue_true_for_past_due_date() -> None:
    task = _task(due_date=date.today() - timedelta(days=1))
    assert is_overdue(task) is True


def test_is_overdue_false_when_done() -> None:
    task = _task(status="done", due_date=date.today() - timedelta(days=1))
    assert is_overdue(task) is False


def test_is_overdue_false_without_due_date() -> None:
    assert is_overdue(_task(due_date=None)) is False
