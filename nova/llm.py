"""Talking to the Groq API: streaming chat, model listing, friendly errors."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import groq


def stream_chat(client: Any, model: str, messages: list[dict[str, str]]) -> Iterator[str]:
    """Send `messages` to the model and yield the reply piece by piece.

    The HTTP request happens when the first piece is requested, so API errors
    are raised from the loop that consumes this generator.
    """
    stream = client.chat.completions.create(model=model, messages=messages, stream=True)
    try:
        for chunk in stream:
            if not chunk.choices:  # some chunks (e.g. usage info) have no choices
                continue
            piece = chunk.choices[0].delta.content
            if piece:  # content is None for role-only / reasoning-only chunks
                yield piece
    finally:
        close = getattr(stream, "close", None)
        if callable(close):
            close()  # release the connection if we stop early (e.g. Ctrl+C)


def list_models(client: Any) -> list[str]:
    """Return the sorted IDs of the models your API key can use."""
    return sorted(model.id for model in client.models.list().data)


def _detail(exc: Exception, limit: int = 200) -> str:
    text = str(getattr(exc, "message", None) or exc).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def friendly_error_message(exc: Exception) -> str:
    """Translate an exception into a short, helpful, credential-free message."""
    # Order matters: more specific classes must be checked before their parents.
    if isinstance(exc, groq.AuthenticationError):
        return (
            "Authentication failed: your GROQ_API_KEY is invalid, expired or revoked.\n"
            "Create a new key at https://console.groq.com/keys and update your .env file."
        )
    if isinstance(exc, groq.PermissionDeniedError):
        return (
            "Access denied (HTTP 403). Your account or network may not be allowed to use "
            "this model or region. Check the Groq console or try another MODEL_NAME."
        )
    if isinstance(exc, groq.RateLimitError):
        return (
            "Rate limit reached. The free plan allows only a limited number of requests "
            "and tokens per minute. Wait about a minute, then try again."
        )
    if isinstance(exc, groq.NotFoundError):
        return (
            f"Model or endpoint not found: {_detail(exc)}\n"
            "Your MODEL_NAME may be retired or misspelled. Type /models to see the "
            "models available to you, then update MODEL_NAME in .env."
        )
    if isinstance(exc, groq.BadRequestError):
        return (
            f"The API rejected the request: {_detail(exc)}\n"
            "If this mentions a decommissioned model, choose another MODEL_NAME (see /models)."
        )
    if isinstance(exc, groq.APITimeoutError):
        return "The request timed out. Check your connection and try again."
    if isinstance(exc, groq.APIConnectionError):
        return "Could not reach the Groq API. Check your internet connection and try again."
    if isinstance(exc, groq.InternalServerError):
        return "Groq reported a server-side problem (HTTP 5xx). Wait a moment and try again."
    if isinstance(exc, groq.APIStatusError):
        return f"The API returned HTTP {exc.status_code}: {_detail(exc)}"
    if isinstance(exc, groq.GroqError):
        return f"Groq SDK error: {_detail(exc)}"
    return f"Unexpected error ({type(exc).__name__}): {_detail(exc)}"
