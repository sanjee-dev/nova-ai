"""All Rich terminal output lives here, so the chat logic stays easy to read."""

from __future__ import annotations

from collections.abc import Iterator

from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from nova.commands import COMMAND_HELP
from nova.config import Config

# One consistent palette for the whole app.
ACCENT = "#a78bfa"  # soft violet  - NOVA / assistant
USER = "#22d3ee"  # cyan         - you
MUTED = "grey62"
OK = "#4ade80"
WARN = "#fbbf24"
ERR = "#f87171"

PROMPT = f"[bold {USER}]You[/] [{MUTED}]❯[/] "

_LOGO_ROWS = [
    "███╗   ██╗ ██████╗ ██╗   ██╗ █████╗ ",
    "████╗  ██║██╔═══██╗██║   ██║██╔══██╗",
    "██╔██╗ ██║██║   ██║██║   ██║███████║",
    "██║╚██╗██║██║   ██║╚██╗ ██╔╝██╔══██║",
    "██║ ╚████║╚██████╔╝ ╚████╔╝ ██║  ██║",
    "╚═╝  ╚═══╝ ╚═════╝   ╚═══╝  ╚═╝  ╚═╝",
]


def _logo(console: Console) -> Text:
    """Big block logo, with a plain-text fallback for narrow/legacy terminals."""
    wide_enough = console.width >= len(_LOGO_ROWS[0]) + 8
    if wide_enough and console.encoding.lower().startswith("utf"):
        return Text("\n".join(_LOGO_ROWS), style=f"bold {ACCENT}")
    return Text("N O V A   A I   C L I", style=f"bold {ACCENT}")


def print_banner(console: Console, config: Config) -> None:
    """Startup screen: branding, status and available commands."""
    header = Panel(
        Group(
            Align.center(_logo(console)),
            Text(""),
            Align.center(Text("A modern terminal AI assistant · powered by Groq", style=MUTED)),
        ),
        box=box.ROUNDED,
        border_style=ACCENT,
        padding=(1, 2),
    )

    status = Table.grid(padding=(0, 2))
    status.add_column(justify="right", style=MUTED)
    status.add_column()
    status.add_row("Model", Text(config.model_name, style=f"bold {ACCENT}"))
    status.add_row("API key", Text("✓ loaded (hidden)", style=OK))
    status.add_row("Connection", Text("ready · verified on your first message", style=WARN))
    status.add_row(
        "Memory",
        Text(f"this session only · last {config.max_history_messages} messages sent", style="white"),
    )

    commands = Table.grid(padding=(0, 2))
    commands.add_column(style=f"bold {USER}", no_wrap=True)
    commands.add_column(style=MUTED)
    for name, description in COMMAND_HELP:
        commands.add_row(name, description)

    console.print(header)
    console.print(Panel(status, title="Status", title_align="left", border_style=MUTED, box=box.ROUNDED))
    console.print(Panel(commands, title="Commands", title_align="left", border_style=MUTED, box=box.ROUNDED))
    console.print(f"[{MUTED}]Type a message and press Enter to start chatting.[/]\n")


def print_help(console: Console) -> None:
    table = Table.grid(padding=(0, 2))
    table.add_column(style=f"bold {USER}", no_wrap=True)
    table.add_column(style="white")
    for name, description in COMMAND_HELP:
        table.add_row(name, description)
    console.print(Panel(table, title="Commands", title_align="left", border_style=ACCENT, box=box.ROUNDED))


def _assistant_panel(text: str, subtitle: str | None = None, border: str = ACCENT) -> Panel:
    return Panel(
        Markdown(text),
        title=f"[bold {ACCENT}]NOVA[/]",
        title_align="left",
        subtitle=subtitle,
        subtitle_align="right",
        border_style=border,
        box=box.ROUNDED,
        padding=(0, 1),
    )


def stream_reply(console: Console, chunks: Iterator[str]) -> str:
    """Show a spinner until the first piece arrives, then render the reply live.

    Returns the full reply text. If an error or Ctrl+C happens part-way, the
    exception is re-raised and the partial reply is marked as not saved.
    """
    pieces = iter(chunks)
    with console.status(f"[{MUTED}]NOVA is thinking…[/]", spinner="dots", spinner_style=ACCENT):
        first = next(pieces, None)
    if first is None:
        return ""

    text = first
    with Live(
        _assistant_panel(text, "streaming…"),
        console=console,
        refresh_per_second=12,
        vertical_overflow="visible",
    ) as live:
        try:
            for piece in pieces:
                text += piece
                live.update(_assistant_panel(text, "streaming…"))
        except BaseException:
            live.update(_assistant_panel(text, "⚠ incomplete · not saved to history", WARN))
            raise
        live.update(_assistant_panel(text))
    console.print()
    return text


def _shorten(text: str, limit: int = 300) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def print_history(console: Console, messages: list[dict[str, str]], total: int) -> None:
    if not messages:
        print_info(console, "No messages yet. Say something to NOVA first!")
        return
    table = Table(box=box.SIMPLE_HEAD, expand=True, show_edge=False)
    table.add_column("#", justify="right", style=MUTED, width=3)
    table.add_column("Role", width=10)
    table.add_column("Message", ratio=1)
    first_number = total - len(messages) + 1
    for offset, message in enumerate(messages):
        is_user = message["role"] == "user"
        role = Text("You" if is_user else "NOVA", style=f"bold {USER if is_user else ACCENT}")
        table.add_row(str(first_number + offset), role, Text(_shorten(message["content"])))
    console.print(
        Panel(
            table,
            title=f"Recent messages ({len(messages)} of {total})",
            title_align="left",
            border_style=MUTED,
            box=box.ROUNDED,
        )
    )


def print_models(console: Console, models: list[str], current: str) -> None:
    table = Table.grid(padding=(0, 2))
    table.add_column(no_wrap=True)
    table.add_column()
    for model in models:
        active = model == current
        table.add_row(
            Text("●" if active else " ", style=OK),
            Text(model + ("  (current)" if active else ""), style="bold white" if active else "white"),
        )
    console.print(Panel(table, title="Available models", title_align="left", border_style=ACCENT, box=box.ROUNDED))
    console.print(f"[{MUTED}]Change the model by editing MODEL_NAME in your .env file and restarting.[/]\n")


def print_error(console: Console, title: str, message: str) -> None:
    """Show an error without a traceback. `message` is printed as plain text."""
    console.print(Panel(Text(message), title=f"[bold {ERR}]✗ {title}[/]", title_align="left", border_style=ERR, box=box.ROUNDED))


def print_config_error(console: Console, message: str) -> None:
    print_error(console, "Configuration problem", message)


def print_warning(console: Console, message: str) -> None:
    console.print(f"[{WARN}]⚠ {message}[/]\n")


def print_info(console: Console, message: str) -> None:
    console.print(f"[{MUTED}]{message}[/]\n")


def print_success(console: Console, message: str) -> None:
    console.print(f"[{OK}]✓ {message}[/]\n")


def print_goodbye(console: Console) -> None:
    console.print(f"\n[{ACCENT}]Goodbye! Thanks for chatting with NOVA.[/]")
