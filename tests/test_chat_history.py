"""Tests for nova.history.ChatHistory (no network needed)."""

import pytest

from nova.history import ChatHistory


def make_history() -> ChatHistory:
    return ChatHistory("You are a test bot.")


def test_starts_with_only_the_system_message():
    history = make_history()
    assert history.messages == [{"role": "system", "content": "You are a test bot."}]
    assert len(history) == 0


def test_adds_user_and_assistant_messages_in_order():
    history = make_history()
    history.add_user("Hello")
    history.add_assistant("Hi there!")
    assert [m["role"] for m in history.messages] == ["system", "user", "assistant"]
    assert history.messages[1]["content"] == "Hello"
    assert history.messages[2]["content"] == "Hi there!"
    assert len(history) == 2


@pytest.mark.parametrize("bad", ["", "   ", "\n\t"])
def test_rejects_empty_messages(bad):
    history = make_history()
    with pytest.raises(ValueError):
        history.add_user(bad)
    with pytest.raises(ValueError):
        history.add_assistant(bad)
    assert len(history) == 0


def test_clear_resets_but_keeps_system_message():
    history = make_history()
    history.add_user("Hello")
    history.add_assistant("Hi!")
    history.clear()
    assert history.messages == [{"role": "system", "content": "You are a test bot."}]


def test_remove_last_user_message_only_removes_a_trailing_user_message():
    history = make_history()
    history.add_user("Hello")
    assert history.remove_last_user_message() is True
    assert len(history) == 0
    # The system message must never be removed.
    assert history.remove_last_user_message() is False
    assert len(history.messages) == 1

    history.add_user("Q")
    history.add_assistant("A")
    assert history.remove_last_user_message() is False  # last one is the assistant
    assert len(history) == 2


def test_messages_for_api_returns_independent_copy():
    history = make_history()
    history.add_user("Hello")
    snapshot = history.messages_for_api(40)
    snapshot[0]["content"] = "tampered"
    snapshot.append({"role": "user", "content": "extra"})
    assert history.messages[0]["content"] == "You are a test bot."
    assert len(history.messages) == 2


def test_messages_for_api_trims_old_messages_but_keeps_system_and_starts_with_user():
    history = make_history()
    for i in range(5):
        history.add_user(f"q{i}")
        history.add_assistant(f"a{i}")
    sent = history.messages_for_api(3)  # naive cut would start with an assistant message
    assert sent[0]["role"] == "system"
    assert sent[1]["role"] == "user"
    assert sent[-1]["content"] == "a4"
    assert len(sent) <= 4


def test_recent_returns_last_messages_without_system():
    history = make_history()
    history.add_user("q1")
    history.add_assistant("a1")
    history.add_user("q2")
    assert [m["content"] for m in history.recent(2)] == ["a1", "q2"]
    assert [m["content"] for m in history.recent(10)] == ["q1", "a1", "q2"]
    assert history.recent(0) == []
