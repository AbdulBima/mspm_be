"""app.schemas.ai — AI assistant request contracts."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AIChatTurn(BaseModel):
    # `role` is a plain str rather than Literal["user", "assistant"] on
    # purpose: app.api.v1.ai.ask() filters turns with
    # `if turn.role in ("user", "assistant")` at runtime, silently dropping
    # anything else instead of failing request validation on an unexpected
    # role.
    role: str
    content: str


class AIAskRequest(BaseModel):
    sprint_id: str
    question: str
    history: list[AIChatTurn] = Field(default_factory=list)
