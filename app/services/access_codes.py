"""app.services.access_codes — one-time codes a manager shares so a member can activate their login."""

from __future__ import annotations

import secrets

_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_access_code() -> str:
    raw = "".join(secrets.choice(_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def normalize_access_code(code: str) -> str:
    cleaned = "".join(c for c in code.upper() if c.isalnum())
    return f"{cleaned[:4]}-{cleaned[4:]}" if len(cleaned) == 8 else cleaned


def normalize_email(email: str) -> str:
    return email.strip().lower()
