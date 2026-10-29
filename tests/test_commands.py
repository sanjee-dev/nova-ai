"""Tests for command parsing and empty-input handling."""

import pytest

from nova.commands import CommandKind, parse_command


@pytest.mark.parametrize("raw", ["", " ", "   \t  ", "\n"])
def test_blank_input_is_empty(raw):
    assert parse_command(raw).kind is CommandKind.EMPTY


@pytest.mark.parametrize("raw", ["exit", "quit", "EXIT", "  Quit  ", "/exit", "/quit"])
def test_exit_commands(raw):
    assert parse_command(raw).kind is CommandKind.EXIT


@pytest.mark.parametrize(
    ("raw", "kind"),
    [
        ("/help", CommandKind.HELP),
        ("/HELP", CommandKind.HELP),
        ("/clear", CommandKind.CLEAR),
        ("/history", CommandKind.HISTORY),
        ("/models", CommandKind.MODELS),
    ],
)
def test_slash_commands(raw, kind):
    assert parse_command(raw).kind is kind


def test_history_command_keeps_its_argument():
    command = parse_command("/history 5")
    assert command.kind is CommandKind.HISTORY
    assert command.argument == "5"


def test_unknown_slash_command():
    command = parse_command("/nonsense now")
    assert command.kind is CommandKind.UNKNOWN
    assert command.argument == "/nonsense"


def test_normal_text_is_a_message_and_is_stripped():
    command = parse_command("  What is a token?  ")
    assert command.kind is CommandKind.MESSAGE
    assert command.argument == "What is a token?"


def test_words_that_merely_contain_exit_are_messages():
    assert parse_command("exit strategy for startups").kind is CommandKind.MESSAGE
