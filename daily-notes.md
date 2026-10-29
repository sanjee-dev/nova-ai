# Daily Note - Day 1: Environment Setup and First LLM Chatbot

> **How to use this file:** everything marked **EXAMPLE** is a *template written in advance* so you have
> something to start from. It describes what *typically* happens in this project - it is **not** a record of
> what you actually did. Replace each example with your own experience, delete what did not happen, and
> remove these instructions before you submit.

## What did I finish today?

**EXAMPLE (edit me):**
- Installed Python 3.11+, VS Code, Git, uv and created a Groq account and API key.
- Built NOVA AI CLI: a command-line chatbot with streaming replies, conversation history and error handling.
- Ran 11 LLM experiments and wrote down what I noticed (see `experiments/README.md`).
- Wrote the README, added automated tests and pushed the project to GitHub: `<paste your repo link here>`.

## What did I learn?

**EXAMPLE (edit me):**
- The chatbot "remembers" only because I send the **whole `messages` list** to the model on every request.
- A lower temperature gives more predictable answers; a higher one gives more varied answers.
- Streaming (`stream=True`) returns the answer in small pieces so the user does not wait for the whole reply.
- Secrets such as API keys belong in `.env`, which must be listed in `.gitignore`.
- `uv` manages the virtual environment and dependencies: `uv sync` installs, `uv run main.py` runs.

### Key ideas in my own words (the assignment asks for these)

**EXAMPLE definitions - rewrite them so they sound like you:**
- **Model:** a program trained on a huge amount of text that predicts the next piece of text, which lets it answer questions and write.
- **Token:** a small chunk of text (a word, part of a word or punctuation). Models read and write tokens, and limits and speed are counted in tokens.
- **Context window:** the maximum number of tokens the model can look at in one request (my prompt + the chat history + its answer). Anything beyond it is forgotten.

## Where did I get stuck, and how did I solve it?

**Write only problems you really had.** Possible examples of things beginners often meet - keep one *only if* it happened to you:
- _The model name from the assignment (`llama-3.1-8b-instant`) was not available._ -> I checked the Groq models page / the `/models` command and set `MODEL_NAME` in `.env` to an available model.
- _"GROQ_API_KEY is missing"._ -> I created `.env` from `.env.example` and pasted my key (no quotes, no spaces).
- _Rate-limit error._ -> I waited a minute and tried again.
- _`uv` was not recognised after installing._ -> I closed and reopened the terminal.

**My real answer:**
_TODO: describe what blocked you, what you tried (for at least a few minutes), and what finally worked._
