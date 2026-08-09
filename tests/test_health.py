"""Tests for the unauthenticated liveness endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch


def test_root(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "sprint-ops"}


def test_health_ok(client) -> None:
    with patch("app.main.ping", new=AsyncMock(return_value=None)):
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_degraded_returns_503(client) -> None:
    with patch("app.main.ping", new=AsyncMock(side_effect=ConnectionError("no db"))):
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
