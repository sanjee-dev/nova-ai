"""NOVA AI CLI - a terminal chatbot powered by an open-weight LLM on Groq.

Run it with:   uv run main.py

How it works (the short version):
  1. Load settings from .env and create the Groq client once.
  2. Keep a `messages` list (inside ChatHistory) that starts with a system message.
  3. Loop: read input -> add user message -> send ALL messages to the model with
     stream=True -> show the reply as it arrives -> add the full reply to messages.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

from groq import Groq, GroqError
from rich.console import Console

from nova import ui
from nova.commands import CommandKind, parse_command
from nova.config import SYSTEM_PROMPT, Config, ConfigError, load_config
from nova.history import ChatHistory
from nova.llm import friendly_error_message, list_models, stream_chat

DEFAULT_HISTORY_VIEW = 10


def handle_message(console: Console, client: Groq, config: Config, history: ChatHistory, text: str) -> bool:
    """Send one user message to the model. Returns True if the reply was saved.

    The user message is added first, but removed again if anything goes wrong,
    so a failed or cancelled request never leaves the history in a broken state.
    """
    history.add_user(text)
    try:
        messages = history.messages_for_api(config.max_history_messages)
        reply = ui.stream_reply(console, stream_chat(client, config.model_name, messages))
    except KeyboardInterrupt:
        history.remove_last_user_message()
        ui.print_warning(console, "Response cancelled. That message was not saved to the history.")
        return False
    except Exception as exc:  # noqa: BLE001 - every failure becomes a friendly message
        history.remove_last_user_message()
        ui.print_error(console, "Request failed", friendly_error_message(exc))
        return False

    if not reply.strip():
        history.remove_last_user_message()
        ui.print_error(console, "Empty response", "The model returned no text. Please try again.")
        return False

    history.add_assistant(reply)  # only complete replies are ever stored
    return True


def run_chat(
    console: Console,
    client: Groq,
    config: Config,
    history: ChatHistory | None = None,
    read_input: Callable[[], str] | None = None,
) -> None:
    """The main chat loop. `history` and `read_input` can be replaced in tests."""
    if history is None:  # (not `history or ...`: an empty history is falsy)
        history = ChatHistory(SYSTEM_PROMPT)
    if read_input is None:

        def read_input() -> str:
            return console.input(ui.PROMPT)

    while True:
        try:
            raw = read_input()
        except (KeyboardInterrupt, EOFError):  # Ctrl+C / Ctrl+D at the prompt
            break

        command = parse_command(raw)

        if command.kind is CommandKind.EMPTY:
            ui.print_info(console, "Please type a message (or /help for commands).")
        elif command.kind is CommandKind.EXIT:
            break
        elif command.kind is CommandKind.HELP:
            ui.print_help(console)
        elif command.kind is CommandKind.CLEAR:
            history.clear()
            ui.print_success(console, "Conversation cleared. The system prompt was kept.")
        elif command.kind is CommandKind.HISTORY:
            count = DEFAULT_HISTORY_VIEW
            if command.argument:
                if command.argument.isdigit() and int(command.argument) > 0:
                    count = int(command.argument)
                else:
                    ui.print_warning(console, "Usage: /history [n]  (n must be a positive number)")
                    continue
            ui.print_history(console, history.recent(count), total=len(history))
        elif command.kind is CommandKind.MODELS:
            try:
                ui.print_models(console, list_models(client), config.model_name)
            except Exception as exc:  # noqa: BLE001
                ui.print_error(console, "Could not list models", friendly_error_message(exc))
        elif command.kind is CommandKind.UNKNOWN:
            ui.print_warning(console, f"Unknown command {command.argument!r}. Type /help to see all commands.")
        else:  # CommandKind.MESSAGE
            handle_message(console, client, config, history, command.argument)

    ui.print_goodbye(console)


def main() -> int:
    console = Console()
    try:
        config = load_config()
        client = Groq(api_key=config.api_key)  # created once and reused
    except ConfigError as exc:
        ui.print_config_error(console, str(exc))
        return 1
    except GroqError as exc:
        ui.print_config_error(console, friendly_error_message(exc))
        return 1

    ui.print_banner(console, config)
    run_chat(console, client, config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
