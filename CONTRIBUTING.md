# Contributing

## Adding a new AI provider

1. Add config to `PROVIDERS` in `ai_client.py`:
```python
"myprovider": {
    "label": "My Provider",
    "env_key": "MYPROVIDER_API_KEY",  # "" for local providers
    "models": { "1": ("model-id", "Model Name") },
}
```
2. Add `_call_myprovider(user_message) -> list[TestCase]` — use `_parse_response()`, `temperature=0.3`. See `_call_ollama()` as reference.
3. Add to `select_provider()` in `main.py`.
4. If no API key needed, add to the `if provider == "ollama":` branch.

## Adding a new Ollama model

Add to the `"ollama"` → `"models"` dict in `ai_client.py`. Only include models verified to produce valid JSON for test generation.

## Adding a new test assertion

1. Add field to `ExpectedResult` in `models.py`
2. Add assertion logic in `tester.py` → `run_tests()`
3. Add assertion logic in `tests/test_api.py`

## Adding a new API endpoint

1. Add route to `api.py` using `raise HTTPException(...)` for errors (never `return (dict, status)`)
2. Add unit tests in `tests/test_api_server.py`
3. Add example description + test cases in `examples/<endpoint>/`

## Style rules

- No comments unless the reason is non-obvious
- No new dependencies without updating `requirements.txt`
- All ANSI colors from `colors.py` — never redefine
- All providers through `_parse_response()` — never parse AI output directly
- `models.py` is the single source of truth for TestCase schema

## Running examples

```bash
python3 api.py &
python3 tester.py examples/login/tests_gemini.json http://localhost:8000
python3 tester.py examples/me/tests_gemini.json http://localhost:8000 \
  --auth-url http://localhost:8000/login \
  --auth-payload '{"email":"alice@example.com","password":"alice123"}'
pytest tests/ --test-file=examples/login/tests_gemini.json --base-url=http://localhost:8000 -v
```
