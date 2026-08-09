"""
app.core.security
==================
Password hashing and JWT issuance/verification for the single-manager-class
auth model. No user roles, no refresh tokens — deliberately minimal for an
internal tool with one class of authenticated user.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TOKEN_SCOPE = "pm_tracker"


def hash_password(password: str) -> str:
    # Truncate password to 72 bytes to prevent bcrypt ValueError
    if isinstance(password, str):
        password = password.encode("utf-8")[:72].decode("utf-8", errors="ignore")
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    # Truncate password to 72 bytes to prevent bcrypt ValueError
    if isinstance(password, str):
        password = password.encode("utf-8")[:72].decode("utf-8", errors="ignore")
    return _pwd_context.verify(password, password_hash)


def issue_manager_token(manager: dict) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.pm_token_expire_minutes)
    payload = {
        "sub": manager["email"],
        "manager_id": manager["manager_id"],
        "exp": expire,
        "scope": TOKEN_SCOPE,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict:
    """Raises jose.JWTError on an invalid or expired token — callers map that to HTTP 401."""
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


__all__ = [
    "JWTError",
    "TOKEN_SCOPE",
    "decode_token",
    "hash_password",
    "issue_manager_token",
    "verify_password",
]
