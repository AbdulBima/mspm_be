"""Tests for app.services.access_codes."""

from __future__ import annotations

from app.services.access_codes import generate_access_code, normalize_access_code, normalize_email


def test_generated_code_shape() -> None:
    code = generate_access_code()
    assert len(code) == 9 and code[4] == "-"
    assert not set(code.replace("-", "")) & set("01IOL")


def test_normalize_access_code_accepts_loose_input() -> None:
    assert normalize_access_code(" abcd efgh ") == "ABCD-EFGH"
    assert normalize_access_code("abcd-efgh") == "ABCD-EFGH"


def test_normalize_email() -> None:
    assert normalize_email("  Ada@Example.COM ") == "ada@example.com"
