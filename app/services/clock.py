"""app.services.clock — naive-UTC time helpers used for Mongo storage."""

from __future__ import annotations

from datetime import date, datetime, timezone

# Define UTC for Python 3.10 compatibility
UTC = timezone.utc


def now() -> datetime:
    """Current time as naive UTC — Mongo stores everything naive here;
    keeping every write on the same convention avoids aware/naive
    comparison bugs when documents are read back."""
    return datetime.now(UTC).replace(tzinfo=None)


def to_datetime(d: date) -> datetime:
    """Normalize a plain date into a naive UTC midnight datetime."""
    return datetime(d.year, d.month, d.day)
