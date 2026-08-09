"""app.services.ids — short, prefixed, URL-safe public identifiers."""

from __future__ import annotations

import secrets
import string

_ALPHABET = string.ascii_letters + string.digits


def gen_id(prefix: str, length: int = 10) -> str:
    body = "".join(secrets.choice(_ALPHABET) for _ in range(length))
    return f"{prefix}-{body.upper()}"
