"""app.schemas.auth — signup, login and member activation request contracts."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class ManagerSignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8)
    invite_code: str | None = None


class ManagerLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


LoginRequest = ManagerLoginRequest


class MemberActivateRequest(BaseModel):
    email: EmailStr
    access_code: str = Field(min_length=4, max_length=20)
    password: str = Field(min_length=8)
