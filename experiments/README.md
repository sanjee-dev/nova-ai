# LLM Experiments (Day 1, Part 3)

`llm_experiments.py` contains **11 experiments** that show how an LLM reacts to different inputs.
They only run when you launch the script yourself - the tests never call the real API.

## How to run

From the project folder (after `uv sync` and creating your `.env`):

```bash
uv run experiments/llm_experiments.py            # run all 11 experiments (~21 API calls)
uv run experiments/llm_experiments.py --list     # show the experiment list
uv run experiments/llm_experiments.py --only 3 4 # run just experiments 3 and 4
```

The script pauses 2 seconds between calls to stay under the free plan's rate limit.
Raw outputs are saved to `experiments/last_run_results.md` (overwritten on every run), so
**write your own observations in the table below** - that is the part the assignment asks for.

## Experiments and what to look for

| # | Experiment | What to look for | What I noticed (write 1-2 lines) |
|---|------------|------------------|----------------------------------|
| 1 | Simple question | A basic request/response round trip | _TODO_ |
| 2 | Different system prompts | Same question with no / teacher / pirate system prompt - how do tone and style change? | _TODO_ |
| 3 | Temperature 0.0 | Run the same prompt twice - are the answers (almost) identical? | _TODO_ |
| 4 | Temperature 1.0 | Same prompt twice - are the answers more varied? | _TODO_ |
| 5 | Short response length | `max_completion_tokens=60` - is the answer cut off? Check `finish_reason` (`length` = cut off) | _TODO_ |
| 6 | Longer response length | `max_completion_tokens=600` - fuller answer, more tokens used | _TODO_ |
| 7 | Different prompt wording | "Tell me about Python" vs. a specific request - which is more useful? | _TODO_ |
| 8 | Follow-up with history | "What is its capital?" with and without earlier messages - this is why the chatbot keeps a `messages` list | _TODO_ |
| 9 | Structured response | Does the model return valid JSON that Python can parse? | _TODO_ |
| 10 | Comparing prompts | Three styles of the same question - compare length and usefulness | _TODO_ |
| 11 | Token usage | How `prompt_tokens` grows with a longer prompt | _TODO_ |

## Good to know

- **Reasoning models and token limits.** The default model (`openai/gpt-oss-20b`) "thinks" before it answers, and
  that thinking can use up the token limit. With a very small limit (experiment 5) you may see a cut-off or even
  an empty answer. That is a real behaviour to note down, not a bug. The script sets `reasoning_effort="low"` for
  gpt-oss models to keep this small.
- **Temperature** is accepted by Groq's chat models (0.0 = most predictable, higher = more varied).
  If you switch to a model that rejects a parameter, the script prints the API error and continues.
- Every observation should be in **your own words** - the model's answers will differ from run to run.
