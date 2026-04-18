# api-testgen-ai

A CLI tool that uses AI to automatically generate and execute API test cases. Supports **Google Gemini**, **Anthropic Claude**, **OpenAI**, and **Ollama** (local, free, no API key).

---

## Features

- AI-generated test cases covering 4 categories: **Functional**, **Negative**, **Edge Cases**, **Validation**
- **4 AI providers**: Google Gemini (free), Anthropic Claude, OpenAI, Ollama (local)
- **API description field** — describe your API's behaviour so the AI generates accurate tests
- **Two test runners**: colored CLI (`tester.py`) and pytest (`tests/`) for CI/CD
- Saves settings (provider, model, API key) so you only configure once
- Optional auth: Bearer token or custom header (e.g. `X-API-Key`)
- Includes a sample FastAPI server for local testing

---

## Project Structure

```
api-test-ai/
├── main.py                       # CLI entry point — provider setup, input collection, orchestration
├── ai_client.py                  # AI provider integrations → returns list[TestCase]
├── tester.py                     # Colored CLI test runner — human-friendly pass/fail output
├── models.py                     # Pydantic data models: TestCase, TestInput, ExpectedResult
├── colors.py                     # Shared ANSI color constants
├── api.py                        # Sample FastAPI server (GET /users, POST /login)
├── requirements.txt              # Python dependencies
├── pytest.ini                    # pytest configuration
├── tests/
│   ├── conftest.py               # pytest CLI options (--test-file, --base-url, --bearer, --header)
│   └── test_api.py               # Parametrized pytest test — one test per JSON test case
├── examples/                     # Ready-to-run test case files (no AI call needed)
│   ├── local_api_login.json                # Tests for the sample api.py server
│   ├── local_api_login_gemini.json         # Gemini-generated version of the above
│   ├── jsonplaceholder_post_gemini.json    # Gemini tests for JSONPlaceholder POST /posts
│   └── jsonplaceholder_post_ollama.json    # Ollama tests for JSONPlaceholder POST /posts
└── .claude/                      # Claude Code project config (rules, skills, hooks)
    ├── rules/                    # AI behaviour rules for this project
    └── skills/                   # Custom slash commands (fix-bug, api-review, etc.)
```

---

## Setup

### 1. Create a virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Get an API key (skip for Ollama)

| Provider | Free | Link |
|----------|------|------|
| Google Gemini | Yes | https://aistudio.google.com → Get API key |
| Anthropic Claude | No | https://console.anthropic.com |
| OpenAI | No | https://platform.openai.com/api-keys |
| Ollama | Local | See [Ollama setup](#ollama-local) below |

---

## Running

### Start the sample API server (optional)

```bash
python3 api.py
```

Server starts at `http://localhost:8000`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/users` | GET | Returns list of users |
| `/login` | POST | Validates credentials, returns token |

**Valid credentials:**

| Email | Password | Result |
|-------|----------|--------|
| `admin@example.com` | `admin123` | 200 + token |
| `user@example.com` | `user123` | 200 + token |
| `locked@example.com` | `locked123` | 403 locked |

---

### Generate test cases with the CLI

```bash
python3 main.py
```

**Step 1 — Choose provider:**
```
1. Google Gemini  (free — recommended)
2. Anthropic Claude
3. OpenAI
4. Ollama  (local — free, no API key)
```

**Step 2 — Choose model** (shown per provider)

**Step 3 — Enter API key** (skipped for Ollama)

Settings are saved to `settings.json` automatically. On subsequent runs press Enter to reuse them. Answer `n` to switch providers without overwriting saved settings.

**Then describe the endpoint:**

```
HTTP Method: POST
Full endpoint URL: https://api.example.com/v1/login
Request Payload (JSON): {"email": "admin@example.com", "password": "admin123"}
API Description: Returns 200 + token on valid credentials, 401 on wrong password, 403 if account is locked
Authentication: 1 (None) / 2 (Bearer) / 3 (API Key Header)
```

The **API Description** field is optional but highly recommended — it tells the AI about your API's actual behaviour (validation rules, status codes, quirks) so it generates accurate test cases instead of guessing.

The AI generates 8–12 test cases. You can then **save** them to a JSON file and/or **execute** them immediately.

---

### Run tests — CLI runner (colored output)

```bash
# Run example tests against the local sample API
python3 tester.py examples/local_api_login.json http://localhost:8000

# Run JSONPlaceholder examples (no server needed)
python3 tester.py examples/jsonplaceholder_post_gemini.json https://jsonplaceholder.typicode.com

# With Bearer token
python3 tester.py examples/local_api_login.json https://api.example.com --bearer eyJ0eXAiOiJKV1Q...

# With custom header
python3 tester.py examples/local_api_login.json https://api.example.com --header "X-API-Key=abc123"
```

Exits with code `0` if all tests pass, non-zero if any fail — CI/CD safe.

---

### Run tests — pytest runner (CI/CD)

```bash
# Basic run
pytest tests/ --test-file=examples/jsonplaceholder_post_gemini.json --base-url=https://jsonplaceholder.typicode.com -v

# Local sample API
pytest tests/ --test-file=examples/local_api_login.json --base-url=http://localhost:8000 -v

# With Bearer token
pytest tests/ --test-file=examples/local_api_login.json --base-url=https://api.example.com --bearer <token> -v

# Run only functional tests
pytest tests/ --test-file=examples/... --base-url=... -k "functional"

# Output JUnit XML for CI pipelines
pytest tests/ --test-file=examples/... --base-url=... --junit-xml=results.xml
```

Each JSON test case becomes a named pytest test — failures show exact status codes and missing keys.

---

## Ollama (local)

Ollama runs AI models entirely on your machine — no API key, no internet, no cost.

### Install

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Start and pull a model

```bash
ollama serve &
ollama pull qwen2.5-coder:7b   # recommended — ~4.7 GB
```

### Models available in the tool

| Option | Model | Size | Notes |
|--------|-------|------|-------|
| 1 | `qwen2.5-coder:7b` | 4.7 GB | Best JSON output — recommended |
| 2 | `deepseek-coder-v2` | 8.9 GB | Strong code & JSON generation |
| 3 | `llama3.1:8b` | 4.7 GB | Solid instruction following |
| 4 | `mistral:7b` | 4.1 GB | Fast, reliable JSON output |
| 5 | `phi4:14b` | 9.1 GB | Strong reasoning |
| 6 | Custom | — | Enter any model name manually |

> **GPU acceleration (WSL / Linux):** Ollama auto-detects NVIDIA GPUs via CUDA. Install via the official script (not snap) for CUDA support. To enable CPU+GPU split offloading: `OLLAMA_GPU_OVERHEAD=0 ollama serve`

---

## Test Case Schema

```json
{
  "name": "Valid admin login",
  "category": "functional",
  "description": "Correct credentials should return 200 and a token",
  "input": {
    "method": "POST",
    "endpoint": "/login",
    "payload": { "email": "admin@example.com", "password": "admin123" },
    "headers": {}
  },
  "expected_result": {
    "status_code": 200,
    "contains_key": "token"
  }
}
```

| Field | Values | Description |
|-------|--------|-------------|
| `category` | `functional` / `negative` / `edge_case` / `validation` | Test type |
| `endpoint` | `/login` | Path only — tester prepends base URL |
| `contains_key` | `"token"` / `null` | Optional key to assert exists in JSON response |

---

## Supported AI Providers & Models

### Google Gemini (free)
| Model | Notes |
|-------|-------|
| `gemini-2.5-flash` | Latest, recommended |
| `gemini-2.0-flash` | Stable, free tier |
| `gemini-2.0-flash-lite` | Lightweight |

### Anthropic Claude
| Model | Notes |
|-------|-------|
| `claude-haiku-4-5` | Cheapest, fastest |
| `claude-sonnet-4-6` | Balanced |
| `claude-opus-4-7` | Most capable |

### OpenAI
| Model | Notes |
|-------|-------|
| `gpt-4o-mini` | Cheapest, fastest |
| `gpt-4o` | Balanced |
| `gpt-4.1` | Most capable |

### Ollama (local)
See [Ollama setup](#ollama-local) above.

---

## Settings File

`settings.json` is created on first run and stores your provider, model, and API key. It is excluded from git via `.gitignore` — never commit it.

Answer `n` when asked to reuse saved settings to switch providers for one session without overwriting the saved key.

---

## .claude Directory

This repo includes a `.claude/` directory with [Claude Code](https://claude.ai/code) project configuration:

| Path | Purpose |
|------|---------|
| `.claude/rules/` | AI behaviour rules (test conventions, API rules, provider rules) |
| `.claude/skills/` | Custom slash commands: `/fix-bug`, `/api-review`, `/run-tests`, `/add-bug`, `/new-endpoint` |
| `.claude/settings.json` | Shared hooks and permissions for this project |

These are useful if you develop this project with Claude Code — they enforce consistent behaviour and provide one-command workflows for common tasks.
