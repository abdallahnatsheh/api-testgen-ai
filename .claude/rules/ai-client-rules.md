---
paths:
  - "ai_client.py"
---

# AI Client Rules

## Provider rules
- Never hardcode an API key — always read from `settings.json` or environment variables
- Default provider is Gemini (`gemini-2.5-flash`) — only change if the user explicitly asks
- Ollama needs no API key — it uses `http://localhost:11434/v1` with `api_key="ollama"` as a placeholder
- `env_key` in `PROVIDERS` must match the environment variable name used for that provider's API key

## Adding a new provider
1. Add entry to `PROVIDERS` dict with `label`, `env_key`, `models`, `default_model`
2. Write a `_call_<provider>()` function — use `_call_openai()` as the simplest reference
3. Add a branch in `generate_test_cases()` and `setup()`
4. Add the provider to the menu in `main.py`
5. Never add a model that hasn't been verified to work — test first

## Response parsing
- `_parse_response()` is the single entry point for converting AI text → `list[TestCase]` — all providers must call it
- It strips markdown fences, parses JSON, falls back to `json_repair`, then validates each item via `TestCase.model_validate()`
- Bad test cases are skipped with `logger.warning` — never crash on a single bad item
- Raises `ValueError` only when ALL items fail validation

## Retry logic
- The retry loop in `generate_test_cases()` must handle both `JSONDecodeError` and `503 UNAVAILABLE` — do not bypass it
- Backoff: 10s / 20s / 30s on server errors (`503`, `502`, `UNAVAILABLE` in message)
- Do not add separate retry logic inside individual `_call_*` functions

## Prompt rules
- `generate_test_cases()` receives `path` only (e.g. `/login`) — never the full URL — `collect_inputs()` splits before calling
- The system prompt instructs the AI not to add Authorization headers — auth is handled globally by `run_tests(global_headers=...)`
- The `count` parameter sets the exact number of test cases — if `None`, the prompt asks for 8-12
- When a `description` is provided it is appended verbatim to the user message — this is the primary lever for improving AI accuracy

## Logging
- Use `logger = logging.getLogger(__name__)` at module level — never `print()` in ai_client.py
- Log API call start at INFO, token usage at INFO, skipped cases at WARNING
