"""Tests for streaming and friendly error messages (Groq client is mocked)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import groq
import httpx
import pytest

from nova.llm import friendly_error_message, list_models, stream_chat

REQUEST = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


def status_error(error_class, status_code):
    response = httpx.Response(status_code, request=REQUEST)
    return error_class("server said no", response=response, body=None)


def chunk(text):
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=text))])


def test_stream_chat_yields_text_and_skips_empty_chunks():
    client = MagicMock()
    client.chat.completions.create.return_value = iter(
        [chunk("Hel"), chunk(None), SimpleNamespace(choices=[]), chunk("lo"), chunk("")]
    )
    messages = [{"role": "user", "content": "hi"}]
    assert "".join(stream_chat(client, "test-model", messages)) == "Hello"
    client.chat.completions.create.assert_called_once_with(model="test-model", messages=messages, stream=True)


def test_list_models_returns_sorted_ids():
    client = MagicMock()
    client.models.list.return_value = SimpleNamespace(
        data=[SimpleNamespace(id="b-model"), SimpleNamespace(id="a-model")]
    )
    assert list_models(client) == ["a-model", "b-model"]


@pytest.mark.parametrize(
    ("exception", "expected_text"),
    [
        (status_error(groq.AuthenticationError, 401), "Authentication failed"),
        (status_error(groq.PermissionDeniedError, 403), "Access denied"),
        (status_error(groq.RateLimitError, 429), "Rate limit"),
        (status_error(groq.NotFoundError, 404), "/models"),
        (status_error(groq.BadRequestError, 400), "rejected the request"),
        (status_error(groq.InternalServerError, 500), "server-side"),
        (status_error(groq.APIStatusError, 418), "HTTP 418"),
        (groq.APIConnectionError(request=REQUEST), "internet connection"),
        (groq.APITimeoutError(request=REQUEST), "timed out"),
        (groq.GroqError("sdk problem"), "Groq SDK error"),
        (RuntimeError("boom"), "Unexpected error (RuntimeError)"),
    ],
)
def test_friendly_error_messages(exception, expected_text):
    assert expected_text in friendly_error_message(exception)


def test_error_messages_never_contain_the_api_key():
    error = status_error(groq.AuthenticationError, 401)
    assert "gsk_" not in friendly_error_message(error)
