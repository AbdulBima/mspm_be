"""app.schemas.tasks — task and task-note request contracts."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from app.schemas.enums import NoteType, TaskStatus


class TaskCreateRequest(BaseModel):
    sprint_id: str
    member_id: str
    goal_id: str | None = None  # link to the sprint goal this activity serves — drives alignment view
    title: str
    description: str | None = None  # what the work actually involves
    expectation: str | None = None  # what "done" looks like / acceptance bar
    priority: int = 3  # 1 = highest, matches "Priority 1/2/3..." convention
    status: TaskStatus = TaskStatus.NOT_STARTED
    dependency_note: str | None = None
    due_date: date | None = None


class TaskUpdateRequest(BaseModel):
    goal_id: str | None = None
    sprint_id: str | None = None  # allows moving a task to a different sprint (carry-over)
    title: str | None = None
    description: str | None = None
    expectation: str | None = None
    priority: int | None = None
    status: TaskStatus | None = None
    dependency_note: str | None = None
    blocked_reason: str | None = None
    due_date: date | None = None


class TaskNoteCreateRequest(BaseModel):
    content: str
    note_type: NoteType = NoteType.UPDATE
    author: str | None = None  # defaults to "PM" server-side if absent
