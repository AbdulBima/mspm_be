"""
Shared pytest fixtures. Test-only environment variables are set here, at
module import time (before any test module imports the app), since
Settings() are read once when app.core.config is first imported.
"""

from __future__ import annotations

import os

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("DATABASE_NAME", "sprint_ops_test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("ENV", "development")

from unittest.mock import AsyncMock, patch  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    """
    A TestClient with the two real-DB calls made during lifespan/health
    mocked out, so the suite doesn't need a live MongoDB instance. Tests
    that care about the health endpoint's actual behavior re-patch
    `app.main.ping` themselves within their own `with` block.
    """
    with (
        patch("app.main.ensure_indexes", new=AsyncMock(return_value=None)),
        patch("app.main.ping", new=AsyncMock(return_value=None)),
        TestClient(app) as test_client,
    ):
        yield test_client
