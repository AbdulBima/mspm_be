"""
app.schemas.tracking
=====================
Request contracts for check-ins, standup attendance, the risk/blocker
register, decisions, and meetings.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.schemas.enums import AttendanceStatus, CheckinFlag, MeetingType, RiskKind, RiskSeverity, RiskStatus


class CheckinCreateRequest(BaseModel):
    sprint_id: str
    member_id: str
    checkin_date: date
    yesterday: str | None = None
    today_plan: str | None = None
    blockers: str | None = None
    needs_from_pm: str | None = None
    # The specific tasks a member promised to move during standup — distinct
    # from today_plan's free-text narrative. Powers the accountability view
    # (api/v1/tracking.py::checkin_accountability) and the AI standup
    # summary. Previously missing from this model even though every route
    # that reads a check-in expects it — new check-ins would AttributeError
    # on payload.committed_task_ids.
    committed_task_ids: list[str] = Field(default_factory=list)
    flag: CheckinFlag = CheckinFlag.ON_TRACK


class AttendanceMarkRequest(BaseModel):
    """Set (or correct) one member's attendance for one day — upserts the day record."""

    sprint_id: str
    member_id: str
    attendance_date: date
    status: AttendanceStatus = AttendanceStatus.PRESENT
    joined_at: str | None = None  # "HH:MM" — when they actually joined the call
    today_plan: str | None = None  # what they said they're working on today
    task_ids: list[str] = Field(default_factory=list)  # their own sprint tasks attached as "working on this"
    note: str | None = None


class AttendanceEntry(BaseModel):
    member_id: str
    status: AttendanceStatus = AttendanceStatus.PRESENT
    joined_at: str | None = None
    today_plan: str | None = None
    task_ids: list[str] = Field(default_factory=list)
    note: str | None = None


class AttendanceBulkMarkRequest(BaseModel):
    """Save a full day's roll call in one request — the primary path from the roster UI."""

    sprint_id: str
    attendance_date: date
    entries: list[AttendanceEntry] = Field(default_factory=list)


class RiskCreateRequest(BaseModel):
    sprint_id: str
    title: str
    description: str | None = None
    kind: RiskKind = RiskKind.RISK
    severity: RiskSeverity = RiskSeverity.MEDIUM
    owner_member_id: str | None = None
    related_task_id: str | None = None


class RiskUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: RiskSeverity | None = None
    owner_member_id: str | None = None
    related_task_id: str | None = None
    status: RiskStatus | None = None


class DecisionCreateRequest(BaseModel):
    sprint_id: str
    decision: str
    context: str | None = None
    made_by: str | None = None
    related_goal_id: str | None = None
    decided_on: date | None = None


class ActionItem(BaseModel):
    text: str
    owner: str | None = None
    done: bool = False


class MeetingCreateRequest(BaseModel):
    sprint_id: str
    meeting_type: MeetingType = MeetingType.STANDUP
    meeting_date: date
    notes: str | None = None
    action_items: list[ActionItem] = Field(default_factory=list)


class MeetingUpdateRequest(BaseModel):
    notes: str | None = None
    action_items: list[ActionItem] | None = None
