"""
app.schemas.enums
==================
Enum types shared across request schemas. Kept in one module since they're
small, frequently cross-referenced (e.g. TaskStatus is read by
app.services.task_flags, app.services.alignment, and three different route
modules), and splitting them up would mean import cycles for no real
benefit.
"""

from __future__ import annotations

from enum import Enum


class SprintStatus(str, Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    COMPLETED = "completed"


class Discipline(str, Enum):
    """Broad discipline bucket — drives grouping on the Team page."""

    PRODUCT = "product"
    DESIGN = "design"
    FRONTEND = "frontend"
    BACKEND = "backend"
    QA = "qa"
    MOBILE = "mobile"
    INTERN = "intern"
    LEADERSHIP = "leadership"
    OTHER = "other"


class TaskStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    IN_REVIEW = "in_review"
    DONE = "done"


class NoteType(str, Enum):
    UPDATE = "update"  # general progress note
    BLOCKER = "blocker"  # flags something is in the way
    QUESTION = "question"  # needs an answer from the PM / another team
    DECISION = "decision"  # a call was made
    PRAISE = "praise"  # positive callout


class RiskKind(str, Enum):
    RISK = "risk"
    BLOCKER = "blocker"


class RiskSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskStatus(str, Enum):
    OPEN = "open"
    MITIGATED = "mitigated"
    RESOLVED = "resolved"


class CheckinFlag(str, Enum):
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    BLOCKED = "blocked"
    NO_UPDATE = "no_update"


class AttendanceStatus(str, Enum):
    PRESENT = "present"
    LATE = "late"
    ABSENT = "absent"
    EXCUSED = "excused"


class MeetingType(str, Enum):
    STANDUP = "standup"
    SPRINT_PLANNING = "sprint_planning"
    BACKLOG_REFINEMENT = "backlog_refinement"
    KICKOFF = "kickoff"
    MID_SPRINT_REVIEW = "mid_sprint_review"
    DEMO_READINESS = "demo_readiness"
    SPRINT_REVIEW = "sprint_review"
    RETROSPECTIVE = "retrospective"
    LEADERSHIP_UPDATE = "leadership_update"
    OTHER = "other"


class ReportType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    SPRINT = "sprint"
