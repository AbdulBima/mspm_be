"""app.services.slugs — filesystem/URL-safe filename slugs for PDF downloads."""

from __future__ import annotations


def slugify(value: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in value).strip("-") or "file"
