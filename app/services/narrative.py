"""
app.services.narrative
=======================
Thin wrapper around the optional Groq client used for AI-generated prose on
top of deterministic sprint data. Every caller treats a `None` return from
`complete`/`chat` as "narrative unavailable" and continues serving the
structured data — the AI layer is strictly additive and never a hard
dependency of the API.

Previously each of api/v1/reports.py and api/v1/ai.py constructed and
guarded its own Groq client independently; centralizing it here means the
"is it configured, did the call fail" logic exists in exactly one place.
"""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

try:
    from groq import Groq

    _client: Groq | None = Groq(api_key=settings.groq_api_key) if settings.groq_api_key else None
except Exception:  # pragma: no cover - groq package optional at runtime
    _client = None


def is_configured() -> bool:
    return _client is not None


def complete(
    *, user_prompt: str, system_prompt: str | None = None, temperature: float = 0.3, max_tokens: int = 700
) -> str | None:
    """Single-turn completion. Returns the model's reply, or None if the client isn't configured or the call fails."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})
    return chat(messages, temperature=temperature, max_tokens=max_tokens)


def chat(messages: list[dict], *, temperature: float = 0.2, max_tokens: int = 700) -> str | None:
    """Multi-turn chat completion for callers that build the full message list themselves (e.g. the /ai/ask endpoint)."""
    if _client is None:
        return None
    try:
        response = _client.chat.completions.create(
            model=_MODEL,
            messages=messages,  # type: ignore[arg-type]  # Groq wants typed message dicts; plain dicts match the runtime shape
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        return content.strip() if content is not None else None
    except Exception:
        logger.warning("Groq completion failed", exc_info=True)
        return None
