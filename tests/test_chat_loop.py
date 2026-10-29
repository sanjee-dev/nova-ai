"""End-to-end tests of the chat loop with a fake (mocked) Groq client."""

import io
from types import SimpleNamespace
from unittest.mock import MagicMock

import groq
import httpx
from rich.console import Console

import main
from nova.config import Config
from nova.history import ChatHistory

CONFIG = Config(api_key="test-key", model_name="test-model", max_history_messages=40)
REQUEST = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


def make_console():
    return Console(file=io.StringIO(), width=100, force_terminal=False, color_system=None)


def output(console):
    return console.file.getvalue()


def chunk(text):
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=text))])


def make_client(*results):
    """Each result is a list of text pieces (a successful stream) or an exception to raise."""
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        r if isinstance(r, BaseException) else iter([chunk(p) for p in r]) for r in results
    ]
    return client


def scripted(*lines):
    iterator = iter(lines)
    return lambda: next(iterator)


def run(client, *lines):
    console = make_console()
    history = ChatHistory("system prompt")
    main.run_chat(console, client, CONFIG, history=history, read_input=scripted(*lines))
    return console, history


def test_conversation_context_is_sent_on_every_request():
    client = make_client(["Hello", " there"], ["You said hi."])
    _, history = run(client, "Hi", "What did I say?", "exit")

    assert [m["role"] for m in history.messages] == ["system", "user", "assistant", "user", "assistant"]
    assert history.messages[2]["content"] == "Hello there"  # streamed pieces were joined

    second_call = client.chat.completions.create.call_args_list[1].kwargs
    assert second_call["model"] == "test-model"
    assert second_call["stream"] is True
    assert [m["content"] for m in second_call["messages"]] == [
        "system prompt", "Hi", "Hello there", "What did I say?",
    ]


def test_rate_limit_error_is_shown_and_history_is_not_corrupted():
    rate_limit = groq.RateLimitError("slow down", response=httpx.Response(429, request=REQUEST), body=None)
    client = make_client(rate_limit, ["Second answer"])
    console, history = run(client, "first", "second", "exit")

    assert "Rate limit" in output(console)
    assert "Traceback" not in output(console)
    # The failed "first" message was rolled back; the chat kept working afterwards.
    assert [m["content"] for m in history.messages] == ["system prompt", "second", "Second answer"]


def test_connection_error_is_recoverable():
    client = make_client(groq.APIConnectionError(request=REQUEST), ["Back online"])
    console, history = run(client, "one", "two", "exit")
    assert "internet connection" in output(console)
    assert history.messages[-1]["content"] == "Back online"


def test_unexpected_error_does_not_crash_the_app():
    client = make_client(RuntimeError("boom"), ["ok"])
    console, history = run(client, "one", "two", "exit")
    assert "Unexpected error" in output(console)
    assert len(history) == 2


def test_error_in_the_middle_of_a_stream_is_not_saved():
    def broken_stream():
        yield chunk("partial ")
        raise groq.APIConnectionError(request=REQUEST)

    client = MagicMock()
    client.chat.completions.create.side_effect = [broken_stream()]
    console, history = run(client, "hello", "exit")
    assert len(history) == 0
    assert "not saved" in output(console)


def test_keyboard_interrupt_while_waiting_cancels_the_request():
    client = make_client(KeyboardInterrupt(), ["fine"])
    console, history = run(client, "slow question", "next", "exit")
    assert "cancelled" in output(console)
    assert [m["content"] for m in history.messages] == ["system prompt", "next", "fine"]


def test_empty_model_response_is_not_saved():
    client = make_client([])
    console, history = run(client, "hello", "exit")
    assert len(history) == 0
    assert "no text" in output(console)


def test_empty_input_never_calls_the_api():
    client = make_client()
    console, history = run(client, "", "   ", "exit")
    client.chat.completions.create.assert_not_called()
    assert len(history) == 0
    assert "Please type a message" in output(console)


def test_clear_command_resets_history_but_keeps_system_message():
    client = make_client(["Hi!"])
    _, history = run(client, "Hello", "/clear", "exit")
    assert history.messages == [{"role": "system", "content": "system prompt"}]


def test_history_and_help_commands_print_without_calling_the_api():
    client = make_client(["Pong"])
    console, _ = run(client, "ping", "/history", "/help", "/history abc", "/bogus", "quit")
    text = output(console)
    assert "Recent messages" in text and "ping" in text and "Pong" in text
    assert "/clear" in text  # from /help
    assert "Usage: /history" in text
    assert "Unknown command" in text
    assert client.chat.completions.create.call_count == 1


def test_ctrl_c_or_ctrl_d_at_the_prompt_exits_cleanly():
    for exception in (KeyboardInterrupt, EOFError):
        def read():
            raise exception

        console = make_console()
        main.run_chat(console, make_client(), CONFIG, history=ChatHistory("s"), read_input=read)
        assert "Goodbye" in output(console)


def test_models_command_lists_models_and_handles_errors():
    client = make_client()
    client.models.list.return_value = SimpleNamespace(data=[SimpleNamespace(id="test-model"), SimpleNamespace(id="other")])
    console, _ = run(client, "/models", "exit")
    assert "test-model" in output(console) and "(current)" in output(console)

    client.models.list.side_effect = groq.APIConnectionError(request=REQUEST)
    console, _ = run(client, "/models", "exit")
    assert "Could not list models" in output(console)
