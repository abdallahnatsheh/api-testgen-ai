---
paths:
  - "ai_client.py"
---

# AI Client Rules

- Never hardcode an API key — always read from `settings.json` or environment variables
- The retry loop in `generate_test_cases()` must handle both `JSONDecodeError` and `503 UNAVAILABLE` — do not bypass it
- Default provider is Gemini (`gemini-2.5-flash`) — only change if the user explicitly asks
- `_parse_response()` is the single entry point for converting AI text → `list[TestCase]` — all providers must go through it
- When adding a new provider: add to `PROVIDERS` dict, write a `_call_<provider>()` function, update the menu in `main.py` — see OpenAI as the simplest reference implementation (`chat.completions.create`)
- OpenAI uses `OPENAI_API_KEY` env var; env key name must match the `env_key` field in `PROVIDERS`
- Never add a model to `PROVIDERS` that hasn't been verified to work with the API key — test first
- The system prompt tells the AI not to add Authorization headers — auth is handled globally by `run_tests(global_headers=...)`, not per test case
- `generate_test_cases()` receives `path` only (e.g. `/login`) — never the full URL — `collect_inputs()` splits the URL before calling it
