# Contributing

## Adding a new AI provider

1. Add the provider config to `PROVIDERS` in `ai_client.py`:
```python
"myprovider": {
    "label": "My Provider",
    "env_key": "MYPROVIDER_API_KEY",   # set "" for local providers
    "models": {
        "1": ("model-id", "Model Name — description"),
    },
    "default_model": "model-id",
}
```

2. Add a `_call_myprovider(user_message)` function that returns `list[TestCase]` via `_parse_response()`. Use `temperature=0.3` for consistent output. See `_call_ollama()` as the simplest reference (OpenAI-compatible client).

3. Add the provider to the menu in `main.py` → `select_provider()`.

4. If the provider needs no API key (e.g. local), add it to the `if provider == "ollama":` branch that sets `api_key` without prompting.

## Adding a new Ollama model

Add an entry to the `"ollama"` → `"models"` dict in `ai_client.py`. Only include models verified to produce valid JSON output for API test generation. Prefer instruction-tuned coding models.

## Adding new test assertions

Both runners check `status_code` and `contains_key`. To add more assertion types (e.g. response body value matching):
1. Extend `ExpectedResult` in `models.py`
2. Update the assertion block in `tester.py` → `run_tests()`
3. Update the assertion block in `tests/test_api.py`

## Adding colors or display changes

All ANSI constants live in `colors.py`. Never redefine them in `main.py` or `tester.py` — always import from `colors`.

## Sample API

`api.py` is intentionally simple — it exists only for local testing. It demonstrates:
- Normal auth flow (`admin@example.com` / `admin123`)
- Locked account handling (`locked@example.com` → 403)
- FastAPI Pydantic validation (missing fields → 422)

## Running the example test files

```bash
# CLI runner
python3 tester.py examples/local_api_login.json http://localhost:8000
python3 tester.py examples/jsonplaceholder_post_gemini.json https://jsonplaceholder.typicode.com

# pytest runner
pytest tests/ --test-file=examples/local_api_login.json --base-url=http://localhost:8000 -v
pytest tests/ --test-file=examples/jsonplaceholder_post_gemini.json --base-url=https://jsonplaceholder.typicode.com -v
```

## Style

- No comments unless the reason is non-obvious
- No new dependencies without updating `requirements.txt`
- Keep `models.py` as the single source of truth for the `TestCase` schema
- All providers must go through `_parse_response()` — never parse AI output directly
- `collect_inputs()` returns a `CollectedInput` dataclass — add new fields there, not as extra return values
