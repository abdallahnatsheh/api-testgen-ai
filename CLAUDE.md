# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

CLI tool that uses AI (Gemini, Claude, OpenAI, or Ollama) to generate and execute API test cases. Users enter an endpoint and optional API description, the AI generates structured test cases, and the tester executes them against a live server with pass/fail output.

## Commands

```bash
pip install -r requirements.txt                               # install deps
python3 api.py                                                # start sample FastAPI server on :8000
python3 main.py                                               # run the interactive CLI tool
python3 tester.py <file.json> <base_url>                      # CLI runner standalone
python3 tester.py <file.json> <base_url> --bearer <token>     # with Bearer auth
python3 tester.py <file.json> <base_url> --header X-API-Key=x # with custom header
pytest tests/ --test-file=<file.json> --base-url=<url> -v     # pytest runner
pytest tests/ --test-file=<file.json> --base-url=<url> --junit-xml=results.xml  # CI output
```

## Architecture

```
main.py          CLI — loads/saves settings.json, collects endpoint input, orchestrates flow
ai_client.py     Multi-provider AI client (Gemini + Claude + OpenAI + Ollama) → returns list[TestCase]
tester.py        Colored CLI test runner — returns failed count, exits non-zero on failures
models.py        Pydantic models: TestCase, TestInput, ExpectedResult
colors.py        Shared ANSI color constants (used by main.py and tester.py)
api.py           Sample FastAPI server: GET /users, POST /login (with locked account logic)
pytest.ini       pytest config — disables class collection to avoid conflict with TestCase model
tests/
  conftest.py    pytest fixtures and CLI options (--test-file, --base-url, --bearer, --header)
  test_api.py    parametrized pytest test — one test per JSON test case
examples/        Ready-to-run JSON test case files
settings.json    Saved provider/model/api_key — gitignored, created on first run
```

### Data flow

```
main.py
  └── load_settings() / save_settings()              — settings.json persistence
  └── ai_client.setup(provider, model, api_key)
  └── collect_inputs() → CollectedInput dataclass
        └── urlparse splits full URL → base_url + path automatically
        └── _collect_auth() → Bearer / API Key header / None
  └── ai_client.generate_test_cases(method, path, payload, description) → list[TestCase]
        └── retries up to 3x on JSONDecodeError or 503 UNAVAILABLE
  └── tester.run_tests(test_cases, base_url, global_headers) → int (failed count)
        └── merges global_headers + per-test headers on every request
        └── requests.request() per TestCase → assert status_code + optional contains_key + optional contains_value
```

### TestCase schema

```
TestCase
  .name              str
  .category          "functional" | "negative" | "edge_case" | "validation"
  .description       str
  .input             TestInput
      .method        str
      .endpoint      str        (path only, e.g. /login — tester prepends base_url)
      .payload       dict | None
      .headers       dict
  .expected_result   ExpectedResult
      .status_code   int
      .contains_key  str | None  (optional key to assert exists in JSON response body)
      .contains_value dict | None (optional {key: value} to assert a specific value in response body)
```

### Two test runners

- `tester.py` — colored, verbose, human-friendly. Returns failed count; standalone exits `sys.exit(failed)`.
- `tests/` (pytest) — CI/CD-friendly. Each JSON test case is a named pytest test. Supports `-k` filtering, `--junit-xml`, and all standard pytest flags.

Both share the same JSON format and auth options (`--bearer`, `--header`).

## Key details

- `ai_client.py` auto-retries up to 3 times on `JSONDecodeError` (malformed AI output) and `503 UNAVAILABLE` (Gemini high demand), with 10/20/30s backoff on 503.
- `_parse_response()` strips markdown code fences before `json.loads()` — Gemini sometimes wraps output in ` ```json ` blocks. Fence stripping finds the closing fence explicitly (not just the last line) to handle trailing text. Falls back to `json_repair` on parse failure.
- Ollama uses the OpenAI-compatible API at `http://localhost:11434/v1` — no API key needed.
- `collect_inputs()` returns a `CollectedInput` dataclass (not a tuple) — fields: method, base_url, path, payload, description, auth_headers.
- `run_tests()` returns `int` (failed count) — callers can act on it; standalone tester uses it for `sys.exit`.
- `colors.py` is the single source of ANSI constants — never redefine them in other files.
- `api.py` uses `HTTPException` for all error responses — plain `return (dict, status)` tuples don't work in FastAPI.
- `settings.json` stores provider, model, and API key in plain text — never commit it (already in `.gitignore`).
- FastAPI returns `422` for missing/invalid fields (Pydantic validation), not `400` — test cases should expect `422` for schema errors.
- `LOCKED_ACCOUNTS` set in `api.py` controls which emails return 403 — `locked@example.com` is the example.
