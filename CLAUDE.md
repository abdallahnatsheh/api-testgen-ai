# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

CLI tool that uses AI (Gemini, Claude, OpenAI, Ollama) to generate and execute API test cases from a description or spec.

## Commands

```bash
venv/bin/python3 -m pip install -r requirements.txt
venv/bin/python3 api.py                                        # sample FastAPI server on :8000
venv/bin/python3 main.py                                       # interactive mode
venv/bin/python3 main.py --url http://host/path --method POST  # non-interactive
venv/bin/python3 main.py --postman col.json --base-url http://host
venv/bin/python3 main.py --openapi spec.yaml
venv/bin/python3 tester.py <file.json> <base_url> [--bearer TOKEN] [--auth-url URL --auth-payload JSON] [--html report.html] [--dry-run]
venv/bin/python3 -m pytest tests/ --test-file=<file.json> --base-url=<url> [-v] [--junit-xml=results.xml]
```

Always use `venv/bin/python3` — never system python or `--break-system-packages`.

## Architecture

```
main.py              CLI orchestrator — settings, provider setup, 3 input modes, calls tester
ai_client.py         Multi-provider AI client → list[TestCase]; retries, fence stripping, per-case validation
tester.py            CLI test runner + _fetch_auth_token(); --html writes self-contained report
models.py            Pydantic models: TestCase / TestInput / ExpectedResult with field validators
colors.py            ANSI constants — single source, never redefine elsewhere
postman_importer.py  Postman v2.1 JSON → list[PostmanRequest]
openapi_importer.py  OpenAPI 3.x / Swagger 2.x → (base_url, list[OpenAPIRequest])
api.py               Sample FastAPI server: /users, /users/{id}, /login (JWT), /me (protected)
tests/conftest.py    pytest fixtures + CLI options incl. --auth-url flow
tests/test_api.py    Parametrized pytest — one test per JSON test case
tests/test_api_server.py  29 unit tests for api.py
tests/test_units.py  Unit tests for models, tester helpers, postman importer, CLI args
```

## Key Invariants

**API (api.py)**
- Always use `raise HTTPException(...)` — never `return (dict, status)`
- Real HS256 JWTs from `POST /login`. Valid creds: alice/alice123, bob/bob123, carol/carol123
- `GET /me` requires `Authorization: Bearer <token>` — 401 if missing/invalid/expired
- `locked@example.com` returns 200 with `{"detail":"Welcome!"}` — intentional bug, mark with `# BUG:`
- FastAPI returns 422 for Pydantic validation errors (missing fields), not 400
- Empty string inputs must be checked manually — Pydantic accepts them

**Models (models.py)**
- Single source of truth for TestCase schema — extend here first, then update both runners
- AI output is normalized: method→uppercase, endpoint→path-only, category aliases mapped, bad dict fields coerced to None
- `contains_key`, `contains_value`, `response_headers`, `response_schema`, `max_response_time_ms` are all optional

**AI client (ai_client.py)**
- All providers go through `_parse_response()` — never parse AI output directly
- Retries 3x on JSONDecodeError and 503; skips invalid cases with warning rather than crashing

**main.py**
- `_save_and_run()` is the single save/execute path — used by all 3 input modes
- `_build_auth_headers()` handles all auth modes: --bearer, --header, --auth-url
- Non-interactive mode reads api_key from settings.json; use `--save-settings` to persist new credentials
- `--no-run` skips execution; `--run` is accepted for backward compat (now a no-op, default is to run)

**tester.py**
- `_fetch_auth_token(url, payload_str, path)` — POSTs, walks dot-notation path, returns token string; sys.exit on failure
- `run_tests()` returns int (failed count) — callers use for sys.exit

**pytest (tests/)**
- conftest supports `--auth-url`/`--auth-payload`/`--auth-token-path` — auth fetched once per session
- `pytest.ini` disables class collection (conflicts with TestCase model) and auto-applies tests/report.css

## TestCase Schema

```
TestCase
  name, category, description
  input:
    method        — uppercase, validated against VALID_METHODS
    endpoint      — path only (/login); full URLs stripped
    payload       — dict | None
    headers       — dict (per-test overrides global headers)
  expected_result:
    status_code          — required, 100–599
    contains_key         — optional, assert key exists in JSON response
    contains_value       — optional, assert {key: value} in response
    max_response_time_ms — optional, fail if exceeded
    response_headers     — optional, substring match on response headers
    response_schema      — optional, JSON Schema validation of full response body
```

## Examples

```bash
venv/bin/python3 api.py &
venv/bin/python3 tester.py examples/login/tests_gemini.json http://localhost:8000
venv/bin/python3 tester.py examples/me/tests_gemini.json http://localhost:8000 \
  --auth-url http://localhost:8000/login \
  --auth-payload '{"email":"alice@example.com","password":"alice123"}'
```
