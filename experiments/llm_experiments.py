"""11 small experiments to learn how an LLM behaves (Day 1, Part 3).

Run everything:        uv run experiments/llm_experiments.py
Run some experiments:  uv run experiments/llm_experiments.py --only 3 4
List them:             uv run experiments/llm_experiments.py --list

Nothing here runs automatically: it only calls the Groq API when YOU launch
this script. It uses the same .env file (GROQ_API_KEY, MODEL_NAME) as the chatbot.
Raw results are saved to experiments/last_run_results.md - write what you
noticed in experiments/README.md (one or two lines per experiment).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Allow `import nova...` even though this file lives in a sub-folder.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import groq  # noqa: E402
from groq import Groq  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.table import Table  # noqa: E402
from rich.text import Text  # noqa: E402

from nova.config import ConfigError, load_config  # noqa: E402

RESULTS_FILE = Path(__file__).resolve().parent / "last_run_results.md"
PAUSE_SECONDS = 2.0  # keeps us under the free plan's ~30 requests/minute

console = Console()


@dataclass
class Answer:
    text: str
    finish_reason: str | None
    prompt_tokens: int | None
    completion_tokens: int | None


def user(text: str) -> dict[str, str]:
    return {"role": "user", "content": text}


def system(text: str) -> dict[str, str]:
    return {"role": "system", "content": text}


class Lab:
    """Wraps the Groq client: sends a request, prints it, and records it."""

    def __init__(self, client: Groq, model: str) -> None:
        self.client = client
        self.model = model
        self.log: list[str] = []  # markdown for last_run_results.md
        self.calls = 0

    def ask(self, label: str, messages: list[dict[str, str]], **params) -> Answer:
        """One (non-streaming) API call. `params` e.g. temperature=0.0, max_completion_tokens=50."""
        if self.calls:
            time.sleep(PAUSE_SECONDS)
        self.calls += 1

        # gpt-oss models "think" before answering; keep that short so the
        # token-limit experiments stay readable.
        if "gpt-oss" in self.model:
            params.setdefault("reasoning_effort", "low")

        response = self.client.chat.completions.create(model=self.model, messages=messages, **params)
        choice = response.choices[0]
        usage = response.usage
        answer = Answer(
            text=(choice.message.content or "").strip(),
            finish_reason=choice.finish_reason,
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
        )

        shown_params = {k: v for k, v in params.items() if k != "reasoning_effort"}
        meta = (
            f"params={shown_params or 'defaults'} | finish_reason={answer.finish_reason} | "
            f"tokens: prompt={answer.prompt_tokens}, completion={answer.completion_tokens}"
        )
        prompt_preview = messages[-1]["content"]
        body = answer.text or "(empty - the token limit may have been used up while the model was thinking)"
        console.print(Panel(Text(body), title=label, subtitle=meta, subtitle_align="left", border_style="#a78bfa"))

        self.log.append(
            f"#### {label}\n\n- Prompt: {prompt_preview}\n- {meta}\n\n```text\n{body}\n```\n"
        )
        return answer


# --------------------------------------------------------------------------
# The experiments. Each one is a small function that takes the Lab.
# --------------------------------------------------------------------------


def exp_1_simple_question(lab: Lab) -> None:
    lab.ask("Simple question", [user("What is a large language model? Answer in two sentences.")])


def exp_2_system_prompts(lab: Lab) -> None:
    question = user("Explain what a variable is in programming.")
    lab.ask("No system prompt", [question])
    lab.ask("System prompt: patient teacher", [system("You are a helpful teacher who explains ideas to beginners with a simple everyday analogy."), question])
    lab.ask("System prompt: pirate", [system("You are a pirate. Always answer in pirate speak."), question])


def exp_3_temperature_zero(lab: Lab) -> None:
    prompt = user("Invent a name for a coffee shop run by robots, and describe it in one sentence.")
    lab.ask("temperature=0.0 (run 1)", [prompt], temperature=0.0)
    lab.ask("temperature=0.0 (run 2)", [prompt], temperature=0.0)


def exp_4_temperature_high(lab: Lab) -> None:
    prompt = user("Invent a name for a coffee shop run by robots, and describe it in one sentence.")
    lab.ask("temperature=1.0 (run 1)", [prompt], temperature=1.0)
    lab.ask("temperature=1.0 (run 2)", [prompt], temperature=1.0)


def exp_5_short_answer(lab: Lab) -> None:
    lab.ask(
        "Short limit: max_completion_tokens=60",
        [user("Explain how the internet works.")],
        max_completion_tokens=60,
    )


def exp_6_long_answer(lab: Lab) -> None:
    lab.ask(
        "Longer limit: max_completion_tokens=600",
        [user("Explain how the internet works.")],
        max_completion_tokens=600,
    )


def exp_7_prompt_wording(lab: Lab) -> None:
    lab.ask("Vague wording", [user("Tell me about Python.")], max_completion_tokens=400)
    lab.ask(
        "Specific wording",
        [user("Give me three reasons a complete beginner should learn the Python programming language, as a numbered list.")],
        max_completion_tokens=400,
    )


def exp_8_follow_up_with_history(lab: Lab) -> None:
    first = user("What is the largest country in South America by area?")
    reply = lab.ask("Follow-up setup: first question", [first])
    follow_up = user("What is its capital?")
    lab.ask("Follow-up WITH history (model remembers)", [first, {"role": "assistant", "content": reply.text}, follow_up])
    lab.ask("Follow-up WITHOUT history (model is confused)", [follow_up])


def exp_9_structured_output(lab: Lab) -> None:
    answer = lab.ask(
        "Structured response (JSON)",
        [
            system("You reply with valid JSON only. No Markdown, no extra text."),
            user('Describe the planet Mars as JSON with the keys "name", "diameter_km", "moons" (a list) and "fun_fact".'),
        ],
        temperature=0.0,
    )
    cleaned = answer.text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(cleaned)
        console.print(f"[green]✓ Valid JSON.[/] Keys found: {list(data)}\n")
    except json.JSONDecodeError:
        console.print("[yellow]✗ Not valid JSON - models do not always follow format instructions![/]\n")


def exp_10_compare_prompts(lab: Lab) -> None:
    prompts = {
        "Plain": "Explain recursion.",
        "Audience + length": "Explain recursion to a 10 year old in 3 sentences.",
        "Format + limit": "Explain recursion with a tiny Python example (max 5 lines of code).",
    }
    rows = []
    for name, prompt in prompts.items():
        answer = lab.ask(f"Compare prompts: {name}", [user(prompt)], max_completion_tokens=500)
        rows.append((name, prompt, len(answer.text.split()), answer.completion_tokens))
    table = Table(title="Prompt comparison")
    for column in ("Prompt style", "Prompt", "Words", "Completion tokens"):
        table.add_column(column)
    for name, prompt, words, tokens in rows:
        table.add_row(name, prompt, str(words), str(tokens))
    console.print(table)
    console.print()


def exp_11_token_usage(lab: Lab) -> None:
    short = lab.ask("Tokens: short prompt", [user("Say hello.")], max_completion_tokens=50)
    long_prompt = "Please read this carefully. " * 40 + "Now just say hello."
    long = lab.ask("Tokens: long prompt", [user(long_prompt)], max_completion_tokens=50)
    console.print(
        f"[bold]Prompt tokens:[/] short={short.prompt_tokens}, long={long.prompt_tokens}  "
        "(longer input = more tokens = more of the context window used)\n"
    )


EXPERIMENTS = {
    1: ("Simple question", exp_1_simple_question),
    2: ("Different system prompts", exp_2_system_prompts),
    3: ("Temperature 0.0", exp_3_temperature_zero),
    4: ("Temperature 1.0", exp_4_temperature_high),
    5: ("Short response length", exp_5_short_answer),
    6: ("Longer response length", exp_6_long_answer),
    7: ("Different prompt wording", exp_7_prompt_wording),
    8: ("Follow-up question with history", exp_8_follow_up_with_history),
    9: ("Structured (JSON) response", exp_9_structured_output),
    10: ("Comparing different prompts", exp_10_compare_prompts),
    11: ("Token usage", exp_11_token_usage),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the LLM learning experiments.")
    parser.add_argument("--list", action="store_true", help="list the experiments and exit")
    parser.add_argument("--only", type=int, nargs="+", metavar="N", help="run only these experiment numbers")
    args = parser.parse_args()

    if args.list:
        for number, (title, _) in EXPERIMENTS.items():
            console.print(f"{number:>2}. {title}")
        return 0

    selected = args.only or list(EXPERIMENTS)
    unknown = [n for n in selected if n not in EXPERIMENTS]
    if unknown:
        console.print(f"[red]Unknown experiment number(s): {unknown}. Use --list to see them.[/]")
        return 2

    try:
        config = load_config()
    except ConfigError as exc:
        console.print(Panel(Text(str(exc)), title="Configuration problem", border_style="red"))
        return 1

    lab = Lab(Groq(api_key=config.api_key), config.model_name)
    console.print(f"[bold]Model:[/] {config.model_name}   [bold]Experiments:[/] {selected}\n")

    for number in selected:
        title, function = EXPERIMENTS[number]
        console.rule(f"[bold]Experiment {number}: {title}")
        lab.log.append(f"### Experiment {number}: {title}\n")
        try:
            function(lab)
        except groq.AuthenticationError:
            console.print("[red]Authentication failed - check GROQ_API_KEY in your .env file. Stopping.[/]")
            return 1
        except groq.RateLimitError:
            console.print("[yellow]Rate limit hit. Wait a minute, then re-run with --only for the remaining experiments.[/]")
            return 1
        except groq.GroqError as exc:
            console.print(f"[red]Experiment {number} failed:[/] {exc}")
            lab.log.append(f"_Experiment failed: {exc}_\n")

    header = f"# Last experiment run\n\nModel: `{config.model_name}`  \nDate: {datetime.now():%Y-%m-%d %H:%M}\n\n"
    RESULTS_FILE.write_text(header + "\n".join(lab.log), encoding="utf-8")
    console.print(f"[green]Done.[/] Raw results saved to {RESULTS_FILE.relative_to(RESULTS_FILE.parent.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
