# api-testgen-ai

CLI tool that uses AI to generate and run API test cases. Supports **Gemini**, **Claude**, **OpenAI**, and **Ollama** (local, free).

---

## Features

- Generates 4 test categories: **Functional**, **Negative**, **Edge Cases**, **Validation**
- **3 input modes**: single endpoint (`--url`), Postman collection (`--postman`), OpenAPI/Swagger spec (`--openapi`)
- **Auth flow**: auto-login before tests via `--auth-url` — no manual token copy-paste
- **2 test runners**: colored CLI (`tester.py`) and pytest (`tests/`) for CI/CD
- **HTML reports**, JUnit XML, response time assertions, JSON Schema validation
- Saves provider settings — configure once, reuse every run

---

## Setup

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Get an API key: [Gemini (free)](https://aistudio.google.com) · [Claude](https://console.anthropic.com) · [OpenAI](https://platform.openai.com/api-keys) · Ollama (local, no key)

---

## Quick Start

```bash
# Start the sample API
python3 api.py

# Generate tests interactively (guided prompts)
python3 main.py

# Generate + run non-interactively (uses saved settings)
python3 main.py --url http://localhost:8000/login --method POST --save tests.json

# Run existing test file
python3 tester.py tests.json http://localhost:8000
```

On first run, provider/model/API key are saved to `settings.json`. Subsequent runs use them automatically. To save new settings: `--save-settings`.

---

## Sample API

`python3 api.py` starts a FastAPI server on `:8000`:

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/users` | GET | — | List all users |
| `/users/{id}` | GET | — | Get user by ID |
| `/login` | POST | — | Returns signed JWT |
| `/me` | GET | Bearer JWT | Current user profile |

**Valid credentials:** `alice@example.com / alice123` · `bob@example.com / bob123` · `carol@example.com / carol123`

> `locked@example.com / locked123` → returns 200 instead of 403 (intentional bug for regression demo)

---

## CLI Reference

### `main.py` — Generate test cases

```bash
# Single endpoint
python3 main.py --url http://host/path --method POST [--description file.md] [--count 10] [--save out.json]

# Postman collection
python3 main.py --postman collection.json --base-url http://host

# OpenAPI/Swagger spec
python3 main.py --openapi spec.yaml [--base-url http://override]
```

**Auth options** (all modes):
```bash
--bearer TOKEN                        # static Bearer token
--header X-API-Key=abc                # any custom header (repeatable)
--auth-url URL --auth-payload JSON    # auto-login before running tests
--auth-token-path token               # dot-notation path in auth response (default: token)
```

**Other flags:**
```bash
--provider gemini|claude|openai|ollama
--model MODEL --api-key KEY --save-settings   # save provider config
--no-run                                       # generate only, skip execution
--count N                                      # exact number of test cases
```

### `tester.py` — Run existing test files

```bash
python3 tester.py <file.json> <base_url> [auth] [--html report.html] [--dry-run]
```

Auth flags are the same as `main.py`. `--dry-run` validates JSON without hitting the server.

### pytest — CI/CD runner

```bash
pytest tests/ --test-file=<file.json> --base-url=<url> [auth] [-v] [--junit-xml=results.xml]
pytest tests/ --test-file=<file.json> --base-url=<url> --html=report.html --self-contained-html
```

Auth flags: `--bearer`, `--header`, `--auth-url`, `--auth-payload`, `--auth-token-path`

---

## Auth Flow

For endpoints that require login first:

```bash
# tester.py
python3 tester.py examples/me/tests_gemini.json http://localhost:8000 \
  --auth-url http://localhost:8000/login \
  --auth-payload '{"email":"alice@example.com","password":"alice123"}' \
  --auth-token-path token

# pytest
pytest tests/ --test-file=examples/me/tests_gemini.json --base-url=http://localhost:8000 \
  --auth-url http://localhost:8000/login \
  --auth-payload '{"email":"alice@example.com","password":"alice123"}'
```

The tool POSTs to `--auth-url`, extracts the token at `--auth-token-path` (dot-notation, e.g. `data.access_token`), and injects it as `Authorization: Bearer` for all requests. Fails fast if auth fails.

**Supports:** JWT login, OAuth2 password grant, OAuth2 client credentials.
**Does not support:** browser OAuth2, MFA, SSO.

---

## Test Case Schema

```json
{
  "name": "Valid login",
  "category": "functional",
  "description": "Returns 200 and a token",
  "input": {
    "method": "POST",
    "endpoint": "/login",
    "payload": { "email": "alice@example.com", "password": "alice123" },
    "headers": {}
  },
  "expected_result": {
    "status_code": 200,
    "contains_key": "token",
    "contains_value": { "email": "alice@example.com" },
    "max_response_time_ms": 2000,
    "response_headers": { "Content-Type": "application/json" },
    "response_schema": null
  }
}
```

| Field | Purpose |
|-------|---------|
| `category` | `functional` / `negative` / `edge_case` / `validation` |
| `contains_key` | Assert this key exists in the JSON response |
| `contains_value` | Assert `{key: value}` in response (e.g. `{"count": 3}`) |
| `max_response_time_ms` | Fail if response exceeds this threshold |
| `response_headers` | Assert response headers (substring match) |
| `response_schema` | Validate response body against JSON Schema |

---

## Ollama (local, free)

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve & ollama pull qwen2.5-coder:7b
python3 main.py  # select Ollama at the provider prompt
```

Recommended models: `qwen2.5-coder:7b` (best JSON), `mistral:7b` (fast), `llama3.1:8b`.

---

## Examples

Ready-to-run test files in `examples/`:

```bash
python3 api.py &
python3 tester.py examples/login/tests_gemini.json http://localhost:8000
python3 tester.py examples/users/tests_ollama.json http://localhost:8000
python3 tester.py examples/pokeapi/tests_pokemon.json https://pokeapi.co
```

Each folder has a `description.md` showing what was fed to the AI.
