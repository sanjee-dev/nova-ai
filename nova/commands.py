"""Turn raw user input into a Command (message, /help, /clear, exit, ...)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class CommandKind(Enum):
    EMPTY = auto()
    MESSAGE = auto()
    EXIT = auto()
    HELP = auto()
    CLEAR = auto()
    HISTORY = auto()
    MODELS = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class Command:
    kind: CommandKind
    argument: str = ""  # message text, command argument, or the unknown command name


# (command, description) - used by /help and the startup screen.
COMMAND_HELP: list[tuple[str, str]] = [
    ("/help", "Show this list of commands"),
    ("/clear", "Start a new conversation (keeps the system prompt)"),
    ("/history [n]", "Show the last n messages (default 10)"),
    ("/models", "List models available to your API key"),
    ("exit | quit", "Leave NOVA AI CLI"),
]

_SLASH_COMMANDS = {
    "/help": CommandKind.HELP,
    "/clear": CommandKind.CLEAR,
    "/history": CommandKind.HISTORY,
    "/models": CommandKind.MODELS,
    "/exit": CommandKind.EXIT,
    "/quit": CommandKind.EXIT,
}


def parse_command(raw: str) -> Command:
    """Classify one line of user input."""
    text = raw.strip()
    if not text:
        return Command(CommandKind.EMPTY)

    if text.lower() in {"exit", "quit"}:
        return Command(CommandKind.EXIT)

    if text.startswith("/"):
        name, _, argument = text.partition(" ")
        kind = _SLASH_COMMANDS.get(name.lower())
        if kind is None:
            return Command(CommandKind.UNKNOWN, name)
        return Command(kind, argument.strip())

    return Command(CommandKind.MESSAGE, text)
