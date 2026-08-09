"""
Sprint Tracker (RPM Ops) — Auth Routes
=========================================
Deliberately minimal: this tool has one class of user — the manager/RPM
running the sprint. `signup` is only usable when no manager account exists
yet (or with a matching PM_TRACKER_INVITE_CODE), so a stray public endpoint
can't be used to create arbitrary accounts once you've set yours up.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_manager
from app.core.config import settings
from app.core.security import hash_password, issue_manager_token, verify_password
from app.db.collections import managers_col
from app.schemas.auth import ManagerLoginRequest, ManagerSignupRequest
from app.services.clock import now
from app.services.ids import gen_id

router = APIRouter(prefix="/api/pm/auth", tags=["pm-tracker:auth"])


@router.post("/signup", status_code=201)
async def signup(payload: ManagerSignupRequest) -> dict:
    existing_count = await managers_col.count_documents({})
    if existing_count > 0 and (
        not settings.pm_tracker_invite_code or payload.invite_code != settings.pm_tracker_invite_code
    ):
        raise HTTPException(403, "...")

    if await managers_col.find_one({"email": payload.email}):
        raise HTTPException(409, "An account with this email already exists.")

    manager_id = gen_id("MGR")
    doc = {
        "manager_id": manager_id,
        "name": payload.name,
        "email": payload.email,
        "password_hash": hash_password(payload.password),
        "created_at": now(),
    }
    await managers_col.insert_one(doc)
    token = issue_manager_token(doc)
    return {
        "token": token,
        "manager": {"manager_id": manager_id, "name": payload.name, "email": payload.email},
    }


@router.post("/login")
async def login(payload: ManagerLoginRequest) -> dict:
    manager = await managers_col.find_one({"email": payload.email})
    if not manager or not verify_password(payload.password, manager["password_hash"]):
        raise HTTPException(401, "Incorrect email or password")
    token = issue_manager_token(manager)
    return {
        "token": token,
        "manager": {"manager_id": manager["manager_id"], "name": manager["name"], "email": manager["email"]},
    }


@router.get("/me")
async def me(current_manager: dict = Depends(get_current_manager)) -> dict:
    return {
        "manager_id": current_manager["manager_id"],
        "name": current_manager["name"],
        "email": current_manager["email"],
    }
