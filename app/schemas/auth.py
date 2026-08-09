"""app.schemas.auth — manager signup/login request contracts."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class ManagerSignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8)
    invite_code: str | None = None


class ManagerLoginRequest(BaseModel):
    email: EmailStr
    password: str
