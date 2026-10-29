"""Load and validate configuration from the environment (.env file)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from dotenv import load_dotenv

# llama-3.1-8b-instant (the model named in the assignment) was retired by Groq
# on 2026-08-16, so we default to its recommended replacement. You can always
# override this with MODEL_NAME in your .env file.
DEFAULT_MODEL = "openai/gpt-oss-20b"

# How many recent chat messages (user + assistant) are sent to the model.
DEFAULT_MAX_HISTORY_MESSAGES = 40

SYSTEM_PROMPT = (
    "You are NOVA, a friendly and knowledgeable AI assistant that lives in the "
    "user's terminal. Give clear, accurate, well-structured answers. Keep replies "
    "concise unless the user asks for detail. Use Markdown (short lists, code "
    "blocks) when it improves readability."
)

_PLACEHOLDER_KEYS = {"your_api_key_here", "your_key_here", "paste_your_key_here"}


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    """Validated application settings."""

    # repr=False keeps the secret out of logs and accidental print() calls.
    api_key: str = field(repr=False)
    model_name: str = DEFAULT_MODEL
    max_history_messages: int = DEFAULT_MAX_HISTORY_MESSAGES


def load_config(env: Mapping[str, str] | None = None) -> Config:
    """Read settings from `env` (defaults to the real environment + .env file).

    Passing a dict as `env` is mainly useful for tests.
    Raises ConfigError with a helpful message if something is wrong.
    """
    if env is None:
        load_dotenv()  # copies values from .env into os.environ (if the file exists)
        env = os.environ

    api_key = env.get("GROQ_API_KEY", "").strip()
    if not api_key or api_key.lower() in _PLACEHOLDER_KEYS:
        raise ConfigError(
            "GROQ_API_KEY is missing or still a placeholder.\n\n"
            "How to fix it:\n"
            "  1. Create a free key at https://console.groq.com/keys\n"
            "  2. Copy .env.example to .env\n"
            "  3. Put your key in .env:  GROQ_API_KEY=your_real_key\n"
            "  4. Run the chatbot again."
        )

    model_name = env.get("MODEL_NAME", "").strip() or DEFAULT_MODEL
    if any(ch.isspace() for ch in model_name):
        raise ConfigError(
            f"MODEL_NAME {model_name!r} must not contain spaces. "
            "Copy the exact model ID from https://console.groq.com/docs/models."
        )

    max_history = DEFAULT_MAX_HISTORY_MESSAGES
    raw_limit = env.get("MAX_HISTORY_MESSAGES", "").strip()
    if raw_limit:
        try:
            max_history = int(raw_limit)
        except ValueError:
            raise ConfigError(
                f"MAX_HISTORY_MESSAGES must be a whole number, got {raw_limit!r}."
            ) from None
        if max_history < 2:
            raise ConfigError("MAX_HISTORY_MESSAGES must be at least 2.")

    return Config(api_key=api_key, model_name=model_name, max_history_messages=max_history)
