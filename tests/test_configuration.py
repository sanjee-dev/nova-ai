"""Tests for nova.config.load_config (uses plain dicts, never the real .env)."""

import pytest

from nova.config import DEFAULT_MAX_HISTORY_MESSAGES, DEFAULT_MODEL, ConfigError, load_config


def test_valid_config_with_custom_model():
    config = load_config({"GROQ_API_KEY": "gsk_test", "MODEL_NAME": "some/model"})
    assert config.api_key == "gsk_test"
    assert config.model_name == "some/model"
    assert config.max_history_messages == DEFAULT_MAX_HISTORY_MESSAGES


def test_model_falls_back_to_default_when_not_set():
    assert load_config({"GROQ_API_KEY": "gsk_test"}).model_name == DEFAULT_MODEL
    assert load_config({"GROQ_API_KEY": "gsk_test", "MODEL_NAME": "  "}).model_name == DEFAULT_MODEL


@pytest.mark.parametrize("env", [{}, {"GROQ_API_KEY": ""}, {"GROQ_API_KEY": "   "}])
def test_missing_api_key_gives_helpful_error(env):
    with pytest.raises(ConfigError) as error:
        load_config(env)
    assert "GROQ_API_KEY" in str(error.value)
    assert "console.groq.com" in str(error.value)


def test_placeholder_api_key_is_rejected():
    with pytest.raises(ConfigError):
        load_config({"GROQ_API_KEY": "your_api_key_here"})


def test_model_name_with_spaces_is_rejected():
    with pytest.raises(ConfigError):
        load_config({"GROQ_API_KEY": "gsk_test", "MODEL_NAME": "my model"})


def test_max_history_messages_is_validated():
    assert load_config({"GROQ_API_KEY": "k", "MAX_HISTORY_MESSAGES": "10"}).max_history_messages == 10
    for bad in ["abc", "1", "-5"]:
        with pytest.raises(ConfigError):
            load_config({"GROQ_API_KEY": "k", "MAX_HISTORY_MESSAGES": bad})


def test_api_key_is_not_leaked_by_repr():
    config = load_config({"GROQ_API_KEY": "gsk_super_secret"})
    assert "gsk_super_secret" not in repr(config)
    assert "gsk_super_secret" not in str(config)
