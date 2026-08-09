"""
app.db.collections
===================
Named collection handles, all under the `pm_` namespace so this service's
data can't collide with any other application sharing the cluster.
"""

from __future__ import annotations

from app.db.session import db

managers_col = db["pm_managers"]
sprints_col = db["pm_sprints"]
goals_col = db["pm_goals"]
members_col = db["pm_members"]
tasks_col = db["pm_tasks"]
task_notes_col = db["pm_task_notes"]
checkins_col = db["pm_checkins"]
standup_attendance_col = db["pm_standup_attendance"]
risks_col = db["pm_risks"]
decisions_col = db["pm_decisions"]
meetings_col = db["pm_meetings"]
reports_col = db["pm_reports"]
