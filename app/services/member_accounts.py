"""
app.services.member_accounts
=============================
Login credentials for team members live in their own collection
(pm_member_accounts), never on the member document, so member payloads
returned across the API can't leak a password or access-code hash.
"""

from __future__ import annotations

import re
from datetime import timedelta

from fastapi import HTTPException

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.db.collections import managers_col, member_accounts_col, members_col
from app.services.access_codes import generate_access_code, normalize_access_code, normalize_email
from app.services.clock import now


def email_query(email: str) -> dict:
    return {"$regex": f"^{re.escape(normalize_email(email))}$", "$options": "i"}


async def ensure_email_available(email: str, member_id: str | None = None) -> None:
    clash = await members_col.find_one(
        {"email": email_query(email), "member_id": {"$ne": member_id}}, {"_id": 0, "member_id": 1}
    )
    if clash or await managers_col.find_one({"email": email_query(email)}, {"_id": 1}):
        raise HTTPException(409, "That email is already used by someone else on the tracker.")


def login_status(account: dict | None) -> str:
    if not account:
        return "none"
    if account.get("password_hash"):
        return "active"
    if account.get("access_code_hash"):
        expires = account.get("access_code_expires_at")
        return "expired" if expires and expires < now() else "pending"
    return "none"


def public_access(account: dict | None) -> dict:
    return {
        "login_status": login_status(account),
        "access_code_expires_at": account.get("access_code_expires_at") if account else None,
        "last_login_at": account.get("last_login_at") if account else None,
    }


async def issue_access_code(member: dict) -> dict:
    if not member.get("email"):
        raise HTTPException(400, "Add an email address for this member before giving them access.")
    code = generate_access_code()
    ts = now()
    expires = ts + timedelta(hours=settings.member_access_code_ttl_hours)
    await member_accounts_col.update_one(
        {"member_id": member["member_id"]},
        {
            "$set": {
                "email": normalize_email(member["email"]),
                "access_code_hash": hash_password(code),
                "access_code_expires_at": expires,
                "updated_at": ts,
            },
            "$setOnInsert": {"member_id": member["member_id"], "password_hash": None, "created_at": ts},
        },
        upsert=True,
    )
    return {"access_code": code, "access_code_expires_at": expires}


async def revoke_access(member_id: str) -> None:
    await member_accounts_col.delete_one({"member_id": member_id})


async def sync_account_email(member_id: str, email: str | None) -> None:
    if email:
        await member_accounts_col.update_one(
            {"member_id": member_id}, {"$set": {"email": normalize_email(email), "updated_at": now()}}
        )
    else:
        await revoke_access(member_id)


async def activate(email: str, access_code: str, password: str) -> tuple[dict, dict]:
    account = await member_accounts_col.find_one({"email": normalize_email(email)}, {"_id": 0})
    code = normalize_access_code(access_code)
    invalid = HTTPException(400, "That email and access code don't match. Check the code with your manager.")
    if not account or not account.get("access_code_hash"):
        raise invalid
    if not verify_password(code, account["access_code_hash"]):
        raise invalid
    if account.get("access_code_expires_at") and account["access_code_expires_at"] < now():
        raise HTTPException(400, "This access code has expired. Ask your manager for a new one.")

    member = await members_col.find_one({"member_id": account["member_id"]}, {"_id": 0})
    if not member:
        raise invalid
    if not member.get("active", True):
        raise HTTPException(403, "Your account is paused. Contact your manager.")

    ts = now()
    await member_accounts_col.update_one(
        {"member_id": account["member_id"]},
        {
            "$set": {
                "password_hash": hash_password(password),
                "access_code_hash": None,
                "access_code_expires_at": None,
                "activated_at": account.get("activated_at") or ts,
                "last_login_at": ts,
                "updated_at": ts,
            }
        },
    )
    return {**account, "activated_at": account.get("activated_at") or ts}, member


async def authenticate(email: str, password: str) -> tuple[dict, dict] | None:
    account = await member_accounts_col.find_one({"email": normalize_email(email)}, {"_id": 0})
    if not account or not account.get("password_hash"):
        return None
    if not verify_password(password, account["password_hash"]):
        return None
    member = await members_col.find_one({"member_id": account["member_id"]}, {"_id": 0})
    if not member:
        return None
    if not member.get("active", True):
        raise HTTPException(403, "Your account is paused. Contact your manager.")
    await member_accounts_col.update_one(
        {"member_id": account["member_id"]}, {"$set": {"last_login_at": now()}}
    )
    return account, member


def member_profile(member: dict) -> dict:
    return {
        "member_id": member["member_id"],
        "name": member["name"],
        "email": member.get("email"),
        "role_title": member.get("role_title"),
        "discipline": member.get("discipline"),
        "color_tag": member.get("color_tag"),
    }
