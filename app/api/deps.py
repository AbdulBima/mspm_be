"""
app.api.deps
============
Shared FastAPI dependencies for the versioned API.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from app.core.security import TOKEN_SCOPE, JWTError, decode_token
from app.db.collections import managers_col


async def get_current_manager(request: Request) -> dict:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Authentication required. Provide Authorization: Bearer <token>")
    token = auth_header.split(" ", 1)[1]
    try:
        payload = decode_token(token)
    except JWTError as err:
        raise HTTPException(401, "Invalid or expired token") from err
    if payload.get("scope") != TOKEN_SCOPE:
        raise HTTPException(401, "Token is not valid for the sprint tracker")
    manager = await managers_col.find_one({"manager_id": payload.get("manager_id")}, {"_id": 0})
    if not manager:
        raise HTTPException(401, "Manager account not found")
    return manager
