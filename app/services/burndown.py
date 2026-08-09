"""
app.services.burndown
======================
Reconstructs a day-by-day count of open tasks from each task's
status_history, for the sprint's working days elapsed so far, plus the ideal
line.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.services.clock import now, to_datetime
from app.services.sprint_calendar import sprint_day_number, working_date_for_day


def build_burndown(sprint: dict, tasks: list[dict]) -> list[dict]:
    working_days = sprint.get("working_days", 10)
    days_elapsed = sprint_day_number(sprint)["day_number"]
    total_tasks = len(tasks)

    series = []
    for day in range(0, working_days + 1):
        as_of_date = working_date_for_day(sprint, day) if day > 0 else sprint["start_date"]
        as_of_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        as_of_dt = to_datetime(as_of_date) + timedelta(hours=23, minutes=59)

        remaining = 0
        for t in tasks:
            history = t.get("status_history") or [
                {"status": t.get("status", "not_started"), "changed_at": t.get("created_at", now())}
            ]
            # status as of that day = last history entry at/before as_of_dt
            applicable = [h for h in history if h["changed_at"] <= as_of_dt]
            status_then = applicable[-1]["status"] if applicable else "not_started"
            if status_then != "done":
                remaining += 1

        ideal_remaining = round(total_tasks * (1 - day / working_days)) if working_days else 0
        series.append(
            {
                "day": day,
                "date": as_of_date.isoformat(),
                "remaining": remaining if day <= days_elapsed else None,  # don't project into the future
                "ideal_remaining": ideal_remaining,
            }
        )
    return series
