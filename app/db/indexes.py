"""
app.db.indexes
===============
Idempotent index creation, run once at startup (see app.main.lifespan).
"""

from __future__ import annotations

from app.db.collections import (
    checkins_col,
    decisions_col,
    goals_col,
    managers_col,
    meetings_col,
    members_col,
    reports_col,
    risks_col,
    sprints_col,
    standup_attendance_col,
    task_notes_col,
    tasks_col,
)


async def ensure_indexes() -> None:
    await sprints_col.create_index("sprint_id", unique=True)
    await goals_col.create_index([("sprint_id", 1)])
    await members_col.create_index("member_id", unique=True)
    await tasks_col.create_index([("sprint_id", 1), ("member_id", 1)])
    await tasks_col.create_index([("sprint_id", 1), ("goal_id", 1)])
    await task_notes_col.create_index([("task_id", 1), ("created_at", -1)])
    await checkins_col.create_index([("sprint_id", 1), ("member_id", 1), ("checkin_date", 1)])
    await standup_attendance_col.create_index([("sprint_id", 1), ("attendance_date", 1)], unique=True)
    await risks_col.create_index([("sprint_id", 1), ("status", 1)])
    await decisions_col.create_index([("sprint_id", 1)])
    await meetings_col.create_index([("sprint_id", 1), ("meeting_date", 1)])
    await reports_col.create_index([("sprint_id", 1), ("report_type", 1), ("created_at", -1)])
    await managers_col.create_index("email", unique=True)
