# NOVA AI CLI

A modern, terminal-based AI chatbot written in Python. It talks to an **open-weight LLM through the Groq API**,
streams answers word by word, remembers the conversation, and uses [Rich](https://github.com/Textualize/rich)
for a clean, colourful interface.

This is my Day 1 project for the AI Engineering Internship: *environment setup and first LLM chatbot*.

## Features

- Streaming replies that appear as they are generated, rendered as Markdown in a styled panel
- Conversation memory inside a session (a Python `messages` list that starts with a system message)
- Commands: `/help`, `/clear`, `/history`, `/models`, `exit` / `quit`
- Friendly error messages (missing/invalid key, no internet, rate limits, server errors) - the chat keeps working afterwards
- Secure configuration: API key and model name come from a `.env` file that is never committed
- 11 beginner-friendly LLM experiments and an automated test-suite (no internet or API key needed for the tests)

## Technology stack

| Purpose | Tool |
|---|---|
| Language | Python 3.11+ |
| LLM API | [Groq](https://console.groq.com) Python SDK (default model: `openai/gpt-oss-20b`, an open-weight model) |
| Terminal UI | Rich |
| Configuration | python-dotenv |
| Packages / virtual environment | [uv](https://docs.astral.sh/uv/) |
| Tests | pytest (mocked Groq client) |

## Example terminal session

*(Illustration of the layout, not a recording - real answers will differ.)*

```text
╭─ Status ────────────────────────────────────────────────╮
│      Model  openai/gpt-oss-20b                          │
│    API key  ✓ loaded (hidden)                           │
│ Connection  ready · verified on your first message      │
╰─────────────────────────────────────────────────────────╯
You ❯ What is a token?
╭─ NOVA ──────────────────────────────────────────────────╮
│ A token is a small chunk of text - a word, part of a    │
│ word or punctuation - that a language model reads/writes│
╰─────────────────────────────────────────────────────────╯
You ❯ Give me an example
...
You ❯ exit
Goodbye! Thanks for chatting with NOVA.
```

## Prerequisites

- A computer with a terminal (macOS, Linux, or Windows PowerShell / **Windows Terminal** recommended)
- [uv](https://docs.astral.sh/uv/) - it also downloads Python 3.11+ for you if you do not have it
- A free [Groq](https://console.groq.com) account (no credit card needed)
- Git and a GitHub account (to publish the project)

## Installation

### 1. Install uv

- macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows (PowerShell): `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

Close and reopen the terminal, then check it: `uv --version`

### 2. Get the project and install dependencies

```bash
unzip nova-ai-cli.zip        # Windows: right-click the ZIP -> "Extract All..."
cd nova-ai-cli
uv sync
```

`uv sync` creates the `.venv` virtual environment and installs everything listed in `pyproject.toml` /
`uv.lock` (including `pytest` for development). You never have to activate the environment manually.

### 3. Get a Groq API key

1. Sign up at <https://console.groq.com>.
2. Open the **API Keys** page, click **Create API Key**, and copy it (you only see it once).

### 4. Configure environment variables

```bash
cp .env.example .env          # Windows PowerShell: Copy-Item .env.example .env
```

Open `.env` in VS Code and fill it in:

```env
GROQ_API_KEY=paste_your_real_key_here
MODEL_NAME=openai/gpt-oss-20b
```

| Variable | Required | Meaning |
|---|---|---|
| `GROQ_API_KEY` | yes | Your secret Groq key |
| `MODEL_NAME` | no | Model ID to use (default `openai/gpt-oss-20b`) |
| `MAX_HISTORY_MESSAGES` | no | How many recent messages are sent to the model (default 40) |

> **About the model.** The assignment suggests `llama-3.1-8b-instant`. According to Groq's
> [deprecation page](https://console.groq.com/docs/deprecations) that model was retired on
> 16 Aug 2026 and `openai/gpt-oss-20b` is the recommended replacement, so that is the default here.
> Availability can change and depends on your account, so verify it yourself: run `uv run main.py` and type
> `/models`, or open <https://console.groq.com/docs/models>, then put the exact ID in `MODEL_NAME`.
> If your account still lists a Llama model, you can use that instead.

## Run the chatbot

```bash
uv run main.py
```

## Run the web dashboard

Install the web dependencies and start the browser app:

```bash
uv sync
uv run uvicorn nova.web:app --reload
```

Open <http://127.0.0.1:8000>. Without Google OAuth credentials the app runs in local preview mode and saves chats on this computer.
To enable Google sign-in, create an OAuth 2.0 **Web application** client in Google Cloud Console, add
`http://127.0.0.1:8000/auth/google/callback` as an authorized redirect URI, and put the client ID and secret in `.env`:

```env
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
NOVA_SESSION_SECRET=your_long_random_session_secret
NOVA_BASE_URL=http://127.0.0.1:8000
```

When Google credentials are configured, users must sign in before accessing their own saved conversations.
Locally, SQLite stores chats outside the repository at `~/.nova-ai/chats.sqlite3`. The web app uses this same SQLite database in every environment; it does not require PostgreSQL.

## Deploy the web app with its SQLite history

SQLite needs a persistent disk so chat history survives restarts and deployments. The included `render.yaml` configures a Render web service and mounts its disk at `/var/data`. Render requires a paid service plan for persistent disks.

1. Import this GitHub repository in Render and create the service from `render.yaml`.
2. Set `GROQ_API_KEY`, `GOOGLE_CLIENT_ID`, and `GOOGLE_CLIENT_SECRET` in the Render dashboard when prompted. Keep these secrets out of GitHub.
3. After the first deploy, copy the service URL from Render. In Google Cloud Console, add `https://YOUR-SERVICE.onrender.com/auth/google/callback` as an authorized redirect URI, replacing the example hostname with your actual service URL.
4. Open the Render service's Environment settings and set `NOVA_BASE_URL` to the exact HTTPS service URL. Then redeploy.
5. Test Google sign-in and create a chat. Share the HTTPS service URL with your users only after both work.

The service's SQLite file is stored at `/var/data/chats.sqlite3` on the persistent disk. A persistent disk supports a single service instance, which is suitable for this small app.

Vercel can run the FastAPI app, but its serverless filesystem is not persistent. For a temporary demo without a hosted database, set `NOVA_DB_PATH=/tmp/nova-ai/chats.sqlite3`; chats may disappear after an instance restarts and may not be shared across instances. Use the Render persistent-disk setup above if chat history must be durable. Local preview mode is intended only for localhost development.

To deploy a temporary-history demo on Vercel, import this GitHub repository and add these Environment Variables in the Vercel project settings:

- `GROQ_API_KEY`: your Groq API key
- `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`: your Google OAuth web client
- `NOVA_SESSION_SECRET`: a long random secret
- `NOVA_BASE_URL`: your stable production URL, such as `https://your-project.vercel.app`
- `NOVA_DB_PATH`: `/tmp/nova-ai/chats.sqlite3`
- `NOVA_LOCAL_PREVIEW`: `false`

Add `https://your-project.vercel.app/auth/google/callback` as an authorized redirect URI in Google Cloud Console, replacing the hostname with your actual Vercel domain. Redeploy after setting these values. The app blocks chat access until Google sign-in is configured. Do not promise users that chat history is permanent on Vercel.

## Available commands

| Command | What it does |
|---|---|
| `/help` | Show all commands |
| `/clear` | Start a new conversation (the system message is kept) |
| `/history [n]` | Show the last *n* messages (default 10) |
| `/models` | List the models your API key can use |
| `exit` or `quit` | Leave the program (`Ctrl+C` / `Ctrl+D` at the prompt also work) |

Pressing `Ctrl+C` **while a reply is streaming** cancels just that reply; the chat keeps running.

## How conversation history works

```python
messages = [{"role": "system", "content": "You are NOVA..."}]      # 1. starts with a system message
messages.append({"role": "user", "content": "Hi"})                   # 2. add the user's message
# 3. send the WHOLE list to the model (stream=True) and collect the full reply
messages.append({"role": "assistant", "content": reply})             # 4. add the finished reply
```

The model has no memory of its own - it "remembers" because every request contains the earlier messages.
In this project (`nova/history.py`):

- A reply is added to the history **only after it has fully arrived**. Failed, cancelled or empty replies are never saved,
  and the user message of a failed request is removed again, so the history never gets corrupted.
- Only the last `MAX_HISTORY_MESSAGES` (default 40) messages are sent, so very long chats do not exceed the model's context window.
- **History is kept in memory only. It is lost when the program exits** - nothing is written to disk.

## Run the experiments

```bash
uv run experiments/llm_experiments.py              # all 11 experiments
uv run experiments/llm_experiments.py --list
uv run experiments/llm_experiments.py --only 3 4
```

See [experiments/README.md](experiments/README.md) for what each experiment shows and where to write your notes.
The experiments call the real API, so they only run when you start them.

## Run the tests

```bash
uv run pytest
```

The tests use a mocked Groq client: no API key and no internet connection are needed.

## Project structure

```text
nova-ai-cli/
├── main.py              # entry point + chat loop (start reading here)
├── nova/
│   ├── config.py        # reads/validates .env settings
│   ├── history.py       # the messages list (ChatHistory)
│   ├── commands.py      # parses /help, /clear, exit ...
│   ├── llm.py           # streaming call + friendly error messages
│   └── ui.py            # all Rich output (banner, panels, spinner)
├── experiments/         # 11 LLM experiments + notes
├── tests/               # pytest tests
├── daily-notes.md       # end-of-day note (edit it!)
├── pyproject.toml / uv.lock
├── .env.example         # safe template (no real key)
└── .gitignore
```

Why not just one `main.py`? The assignment's loop is still in `main.py`, but splitting out configuration, history, commands
and the API call makes each piece small and testable without a network connection.

## Troubleshooting

| Problem | Fix |
|---|---|
| `uv: command not found` | Close and reopen the terminal after installing uv. |
| "GROQ_API_KEY is missing" | Make sure the file is named exactly `.env` (not `.env.txt`), sits in the project folder, and contains `GROQ_API_KEY=...` with no quotes. |
| "Authentication failed" | The key is wrong, revoked or has extra spaces. Create a new key and update `.env`. |
| "Model or endpoint not found" / "decommissioned" | Your `MODEL_NAME` is retired or misspelled. Type `/models` and copy an available ID into `.env`. |
| "Rate limit reached" | The free plan has per-minute limits. Wait a minute and try again. |
| "Could not reach the Groq API" | Check your internet connection, VPN or proxy. |
| Strange boxes instead of the logo/borders (Windows) | Use **Windows Terminal** or VS Code's terminal. |
| An empty or cut-off answer | Reasoning models spend tokens "thinking". Ask again or pick another model. |

## Publish to GitHub

1. Create an empty repository on <https://github.com/new> (no README, no .gitignore - they already exist). Copy its URL.
2. In the project folder:

```bash
git init
git add .
git status                    # check that .env is NOT listed!
git commit -m "Initial commit: NOVA AI CLI project setup"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

Suggested clean commit history (make these as separate commits if you are building step by step):

1. `Set up uv project with groq, rich and python-dotenv`
2. `Add configuration loading and .env.example`
3. `Add chat loop with conversation history`
4. `Add streaming responses and Rich terminal UI`
5. `Add error handling and /clear /history /help commands`
6. `Add LLM experiments and notes`
7. `Add tests for history, commands, configuration and errors`
8. `Write README and daily note`

Always commit `pyproject.toml` and `uv.lock` (together they replace `requirements.txt`).
GitHub may ask for a Personal Access Token or browser login when you push the first time.

## Security notes

- **Never** put your API key in code, in `.env.example`, in screenshots, or in a commit. `.env` is listed in `.gitignore`.
- Run `git status` before every commit and make sure `.env` does not appear.
- If a key is ever exposed, delete it in the Groq console immediately and create a new one.
- Error messages never print the key, and `Config` hides it from `repr()` / logs.
- Your messages are sent to Groq's servers - do not type passwords or private data into the chat.

## Limitations and future improvements

- History is **not saved** between runs (in-memory only). A future version could save chats to a JSON file.
- Trimming history is by message count, not exact token count.
- Very long replies in small terminals can scroll awkwardly while streaming.
- The app was developed with a mocked client in automated tests; always do a quick manual test with your own key.
- Ideas: save/load conversations, switch model with a command, token-usage display, a `/system` command to change the system prompt.
