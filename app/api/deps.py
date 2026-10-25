"""
app.api.deps
============
Shared FastAPI dependencies for the versioned API.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from app.core.security import MEMBER_TOKEN_SCOPE, TOKEN_SCOPE, JWTError, decode_token
from app.db.collections import managers_col, member_accounts_col, members_col


def _bearer_claims(request: Request) -> dict:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Authentication required. Provide Authorization: Bearer <token>")
    try:
        return decode_token(auth_header.split(" ", 1)[1])
    except JWTError as err:
        raise HTTPException(401, "Your session has expired. Sign in again.") from err


async def _manager_from_claims(claims: dict) -> dict:
    manager = await managers_col.find_one({"manager_id": claims.get("manager_id")}, {"_id": 0})
    if not manager:
        raise HTTPException(401, "Manager account not found")
    return manager


async def _member_from_claims(claims: dict) -> dict:
    account = await member_accounts_col.find_one({"member_id": claims.get("member_id")}, {"_id": 0})
    if not account or not account.get("password_hash"):
        raise HTTPException(401, "Your access has been revoked. Ask your manager for a new access code.")
    member = await members_col.find_one({"member_id": claims.get("member_id")}, {"_id": 0})
    if not member:
        raise HTTPException(401, "Team member not found")
    if not member.get("active", True):
        raise HTTPException(403, "Your account is paused. Contact your manager.")
    return member


async def get_current_manager(request: Request) -> dict:
    claims = _bearer_claims(request)
    if claims.get("scope") == MEMBER_TOKEN_SCOPE:
        raise HTTPException(403, "This area is for managers only.")
    if claims.get("scope") != TOKEN_SCOPE:
        raise HTTPException(401, "Token is not valid for the sprint tracker")
    return await _manager_from_claims(claims)


async def get_current_member(request: Request) -> dict:
    claims = _bearer_claims(request)
    if claims.get("scope") != MEMBER_TOKEN_SCOPE:
        raise HTTPException(403, "This area is for team members only.")
    return await _member_from_claims(claims)


async def get_current_principal(request: Request) -> tuple[str, dict]:
    claims = _bearer_claims(request)
    scope = claims.get("scope")
    if scope == TOKEN_SCOPE:
        return "manager", await _manager_from_claims(claims)
    if scope == MEMBER_TOKEN_SCOPE:
        return "member", await _member_from_claims(claims)
    raise HTTPException(401, "Token is not valid for the sprint tracker")
