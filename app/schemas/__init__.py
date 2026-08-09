"""
app.schemas
===========
Pydantic request contracts, one module per domain. This package init
re-exports everything so callers can do either

    from app.schemas import TaskCreateRequest
    from app.schemas.tasks import TaskCreateRequest

Route modules use the more specific import; the flat re-export exists for
scripts and tests that just want "give me the schemas."
"""

from __future__ import annotations

from app.schemas.ai import AIAskRequest, AIChatTurn
from app.schemas.auth import ManagerLoginRequest, ManagerSignupRequest
from app.schemas.enums import (
    AttendanceStatus,
    CheckinFlag,
    Discipline,
    MeetingType,
    NoteType,
    ReportType,
    RiskKind,
    RiskSeverity,
    RiskStatus,
    SprintStatus,
    TaskStatus,
)
from app.schemas.members import MemberCreateRequest, MemberUpdateRequest
from app.schemas.reports import ReportGenerateRequest
from app.schemas.sprints import (
    CarryOverRequest,
    GoalCreateRequest,
    GoalUpdateRequest,
    SprintCreateRequest,
    SprintUpdateRequest,
)
from app.schemas.tasks import TaskCreateRequest, TaskNoteCreateRequest, TaskUpdateRequest
from app.schemas.tracking import (
    ActionItem,
    AttendanceBulkMarkRequest,
    AttendanceEntry,
    AttendanceMarkRequest,
    CheckinCreateRequest,
    DecisionCreateRequest,
    MeetingCreateRequest,
    MeetingUpdateRequest,
    RiskCreateRequest,
    RiskUpdateRequest,
)

__all__ = [
    "AIAskRequest",
    "AIChatTurn",
    "ManagerLoginRequest",
    "ManagerSignupRequest",
    "AttendanceStatus",
    "CheckinFlag",
    "Discipline",
    "MeetingType",
    "NoteType",
    "ReportType",
    "RiskKind",
    "RiskSeverity",
    "RiskStatus",
    "SprintStatus",
    "TaskStatus",
    "MemberCreateRequest",
    "MemberUpdateRequest",
    "ReportGenerateRequest",
    "CarryOverRequest",
    "GoalCreateRequest",
    "GoalUpdateRequest",
    "SprintCreateRequest",
    "SprintUpdateRequest",
    "TaskCreateRequest",
    "TaskNoteCreateRequest",
    "TaskUpdateRequest",
    "ActionItem",
    "AttendanceBulkMarkRequest",
    "AttendanceEntry",
    "AttendanceMarkRequest",
    "CheckinCreateRequest",
    "DecisionCreateRequest",
    "MeetingCreateRequest",
    "MeetingUpdateRequest",
    "RiskCreateRequest",
    "RiskUpdateRequest",
]
