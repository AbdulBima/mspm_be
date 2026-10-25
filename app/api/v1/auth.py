"""
Sprint Tracker (RPM Ops) — Auth Routes
=========================================
Managers sign up (first account, or with PM_TRACKER_INVITE_CODE) and log in.
Team members activate their login with the one-time access code their
manager shares, then log in through the same /login endpoint.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_principal
from app.core.config import settings
from app.core.security import hash_password, issue_manager_token, issue_member_token, verify_password
from app.db.collections import managers_col
from app.schemas.auth import LoginRequest, ManagerSignupRequest, MemberActivateRequest
from app.services import member_accounts
from app.services.access_codes import normalize_email
from app.services.clock import now
from app.services.ids import gen_id

router = APIRouter(prefix="/api/pm/auth", tags=["pm-tracker:auth"])


def _manager_public(manager: dict) -> dict:
    return {"manager_id": manager["manager_id"], "name": manager["name"], "email": manager["email"]}


def _manager_session(manager: dict) -> dict:
    public = _manager_public(manager)
    return {"token": issue_manager_token(manager), "role": "manager", "user": public, "manager": public}


def _member_session(account: dict, member: dict) -> dict:
    return {
        "token": issue_member_token(account),
        "role": "member",
        "user": member_accounts.member_profile(member),
    }


@router.get("/setup-status")
async def setup_status() -> dict:
    has_manager = await managers_col.count_documents({}, limit=1) > 0
    return {"has_manager": has_manager, "invite_required": has_manager}


@router.post("/signup", status_code=201)
async def signup(payload: ManagerSignupRequest) -> dict:
    existing_count = await managers_col.count_documents({})
    if existing_count > 0 and (
        not settings.pm_tracker_invite_code or payload.invite_code != settings.pm_tracker_invite_code
    ):
        raise HTTPException(
            403, "A manager account already exists. Enter a valid invite code to add another manager."
        )

    email = normalize_email(payload.email)
    if await managers_col.find_one({"email": member_accounts.email_query(email)}):
        raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    await member_accounts.ensure_email_available(email)

    doc = {
        "manager_id": gen_id("MGR"),
        "name": payload.name.strip(),
        "email": email,
        "password_hash": hash_password(payload.password),
        "created_at": now(),
    }
    await managers_col.insert_one(doc)
    return _manager_session(doc)


@router.post("/login")
async def login(payload: LoginRequest) -> dict:
    manager = await managers_col.find_one({"email": member_accounts.email_query(payload.email)})
    if manager and verify_password(payload.password, manager["password_hash"]):
        return _manager_session(manager)

    result = await member_accounts.authenticate(payload.email, payload.password)
    if result:
        return _member_session(*result)

    raise HTTPException(401, "Incorrect email or password")


@router.post("/activate")
async def activate_member(payload: MemberActivateRequest) -> dict:
    account, member = await member_accounts.activate(payload.email, payload.access_code, payload.password)
    return _member_session(account, member)


@router.get("/me")
async def me(principal: tuple[str, dict] = Depends(get_current_principal)) -> dict:
    role, user = principal
    if role == "manager":
        return {"role": role, **_manager_public(user)}
    return {"role": role, **member_accounts.member_profile(user)}
