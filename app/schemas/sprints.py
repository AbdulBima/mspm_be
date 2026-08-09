"""app.schemas.sprints — sprint and goal request contracts."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.schemas.enums import SprintStatus


class SprintCreateRequest(BaseModel):
    name: str  # e.g. "Sprint 35"
    theme: str | None = None  # e.g. "Enterprise Operations & Unified Program Foundations"
    start_date: date
    working_days: int = 10
    success_measures: list[str] = Field(default_factory=list)
    critical_path: list[str] = Field(
        default_factory=list
    )  # ordered dependency chain, PM's "do not block" list
    out_of_scope: list[str] = Field(default_factory=list)


class SprintUpdateRequest(BaseModel):
    name: str | None = None
    theme: str | None = None
    status: SprintStatus | None = None
    working_days: int | None = None
    success_measures: list[str] | None = None
    critical_path: list[str] | None = None
    out_of_scope: list[str] | None = None
    notes: str | None = None


class GoalCreateRequest(BaseModel):
    title: str
    description: str | None = None
    order: int | None = None


class GoalUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    order: int | None = None


class CarryOverRequest(BaseModel):
    to_sprint_id: str
    task_ids: list[str] | None = None  # if omitted, carries every non-done task in the sprint
    carry_open_risks: bool = True
