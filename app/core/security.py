from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

TOKEN_SCOPE = "manager"
MEMBER_TOKEN_SCOPE = "member"
UTC = timezone.utc

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _truncate_password(password: str) -> str:
    """bcrypt only reads the first 72 bytes."""
    if isinstance(password, str):
        return password.encode("utf-8")[:72].decode("utf-8", errors="ignore")
    return password


def hash_password(password: str) -> str:
    return _pwd_context.hash(_truncate_password(password))


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd_context.verify(_truncate_password(password), password_hash)
    except (ValueError, TypeError):
        return False


def _encode(claims: dict) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.pm_token_expire_minutes)
    return jwt.encode({**claims, "exp": expire}, settings.secret_key, algorithm=settings.algorithm)


def issue_manager_token(manager: dict) -> str:
    return _encode({"sub": manager["email"], "manager_id": manager["manager_id"], "scope": TOKEN_SCOPE})


def issue_member_token(account: dict) -> str:
    return _encode(
        {
            "sub": account["email"],
            "member_id": account["member_id"],
            "sid": account.get("session_key"),
            "scope": MEMBER_TOKEN_SCOPE,
        }
    )


def decode_token(token: str) -> dict:
    """Raises jose.JWTError on an invalid or expired token — callers map that to HTTP 401."""
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


__all__ = [
    "JWTError",
    "MEMBER_TOKEN_SCOPE",
    "TOKEN_SCOPE",
    "decode_token",
    "hash_password",
    "issue_manager_token",
    "issue_member_token",
    "verify_password",
]
