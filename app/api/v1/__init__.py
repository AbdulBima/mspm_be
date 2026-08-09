"""
app.api.v1
==========
Aggregates every route module into one `api_router`. Each sub-router
already declares its own full path prefix (e.g. "/api/pm/sprints"), so this
module adds no prefix of its own — see app/main.py. This is what keeps every
route path byte-for-byte identical to the pre-restructure layout: the
frontend's api.ts client needs zero changes.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import ai, auth, members, reports, sprints, tasks, tracking

api_router = APIRouter()
for _router in (
    auth.router,
    sprints.router,
    members.router,
    tasks.router,
    tracking.router,
    reports.router,
    ai.router,
):
    api_router.include_router(_router)

__all__ = ["api_router"]
