"""app.schemas.members — team member request contracts."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr

from app.schemas.enums import Discipline


class MemberCreateRequest(BaseModel):
    name: str
    role_title: str  # e.g. "UI/UX Designer", "Backend Engineer", "CTO"
    discipline: Discipline = Discipline.OTHER
    email: EmailStr | None = None
    color_tag: str | None = None  # hex, purely cosmetic — backend assigns a default if absent


class MemberUpdateRequest(BaseModel):
    name: str | None = None
    role_title: str | None = None
    discipline: Discipline | None = None
    email: EmailStr | None = None
    color_tag: str | None = None
    active: bool | None = None
