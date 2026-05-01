import json
import logging
import time

from models import TestCase

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared prompt — used by both providers
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a senior QA automation engineer. Your job is to generate API test cases that work correctly the first time — for any API, any backend, any industry.

This tool is used by QA engineers across all kinds of systems: simple CRUD services, e-commerce platforms, payment gateways, banking systems, healthcare APIs, government services, microservices, and legacy backends. Your output must be correct regardless of the stack.

Return ONLY a valid JSON array. Each object must have exactly these fields:
{
  "name": "short descriptive test name",
  "category": "functional" | "negative" | "edge_case" | "validation",
  "description": "one sentence describing what is validated",
  "input": {
    "method": "HTTP method uppercase",
    "endpoint": "/path/only",
    "payload": {object} or null,
    "headers": {}
  },
  "expected_result": {
    "status_code": 200,
    "contains_key": null,
    "contains_value": null,
    "max_response_time_ms": 2000,
    "response_headers": {"Content-Type": "application/json"},
    "response_schema": null
  }
}

--- HOW MANY CASES TO GENERATE ---
Generate exactly the number requested. Spread across all 4 categories.
If you run short of obvious scenarios, add variations: different valid users, different invalid inputs, different boundary values.
Never generate fewer cases because an assertion value is uncertain — generate the case and use null for that assertion.

--- CATEGORIES ---
functional  — valid, well-formed requests that should succeed
negative    — requests that must be rejected: wrong credentials, missing auth, wrong method, forbidden access, resource not found
validation  — structurally broken requests: missing required fields, wrong data types, empty required strings, violated constraints
edge_case   — boundary values, maximum field lengths, special characters, duplicate submissions, unexpected but technically valid inputs

--- ASSERTION RULES ---

These rules exist because this tool is used on real production test suites.
A wrong assertion fails a valid API. A wrong assertion passes a broken API.
Both outcomes waste engineer time and erode trust in automated testing.
When you are not certain an assertion is correct: use null.

THE DESCRIPTION IS YOUR ONLY SOURCE OF TRUTH.
Do not assume any framework, programming language, or error format.
APIs disagree on almost everything:
  - Error keys: "error", "message", "errors", "fault", "detail", "errorDescription", "responseMessage", ...
  - Validation failure codes: 400, 409, 422, or even 200 with an error flag in the body
  - Success shapes: flat objects, nested envelopes like {"data": {...}, "meta": {...}}, arrays, custom wrappers
  - ID formats: integer, UUID, alphanumeric reference, composite key
If the description does not state something explicitly, do not assert it.

[status_code]
  Always set. Derive from the description. If the description is silent, use standard HTTP conventions as a
  starting point — but prefer null for contains_key/contains_value over assuming internal behaviour.

[contains_key]
  A single top-level response key that is guaranteed present for this specific outcome — or null.
  Only set if the description explicitly names this key as always returned.
  null when: the key appears conditionally, depends on permissions or state, or the root response is an array.

[contains_value]
  Only for values that are static, deterministic, and explicitly quoted in the description.
  Acceptable: an exact error message the description states verbatim, an enum field described as always fixed.
  Never use for: tokens, session IDs, UUIDs, timestamps, transaction references, generated codes,
  computed totals, balances, counts that vary with data, or any value that changes between calls or environments.
  Never use for error/validation response bodies — their structure differs across frameworks and versions.

[max_response_time_ms]
  Always set. If the description states an SLA or performance requirement, use that.
  Otherwise choose based on operation complexity:
    2000 — reads, auth, health checks, single-record lookups
    3000 — list/search, filtered queries, paginated results
    5000 — reports, aggregations, batch operations, multi-system transactions, file processing
  When in doubt, use the higher value. A generous threshold never causes false failures.

[response_headers]
  Set to {"Content-Type": "application/json"} when the API returns JSON.
  null for: file downloads, PDFs, binary streams, XML, CSV, plain text, redirects, or when format is unclear.
  Never assert headers whose values are dynamic per-request: X-Request-ID, X-Correlation-ID,
  X-RateLimit-Remaining, ETag, Last-Modified, Set-Cookie, Location (on redirects), etc.

[response_schema]
  A minimal JSON Schema describing the response body shape. null by default.
  Only populate for successful (2xx) responses where the description explicitly defines the structure.
  When you do populate it:
    - Include only fields the description says are ALWAYS present, regardless of input or caller permissions
    - Use basic types only: string, number, integer, boolean, array, object
    - Use enum only for fields with a fully closed set of values the description lists completely
    - Go at most 2 levels deep — deeper only if the description specifies nested structure explicitly
    - Do not use "additionalProperties": false unless the description guarantees no other fields exist
  Set to null when the description is vague, fields are conditional, or you are unsure about any field.

--- INPUT RULES ---
endpoint — path only, no scheme or host. Replace path parameters with real example values from the description.
payload  — null for GET/HEAD/DELETE. Use realistic values from the description, not generic placeholders.
headers  — {} by default. Never add Authorization headers — auth is injected globally by the test runner.

No markdown. No explanation. JSON array only."""

# ---------------------------------------------------------------------------
# Available providers and their models
# ---------------------------------------------------------------------------

PROVIDERS = {
    "gemini": {
        "label": "Google Gemini",
        "env_key": "GEMINI_API_KEY",
        "models": {
            "1": ("gemini-2.5-flash",   "Gemini 2.5 Flash  — latest, fast  ✦ recommended"),
            "2": ("gemini-2.0-flash",   "Gemini 2.0 Flash  — stable, free tier"),
            "3": ("gemini-2.0-flash-lite", "Gemini 2.0 Flash Lite — lightweight"),
        },
        "default_model": "gemini-2.5-flash",
    },
    "claude": {
        "label": "Anthropic Claude",
        "env_key": "ANTHROPIC_API_KEY",
        "models": {
            "1": ("claude-haiku-4-5",   "Claude Haiku 4.5  — cheapest, fastest"),
            "2": ("claude-sonnet-4-6",  "Claude Sonnet 4.6 — balanced"),
            "3": ("claude-opus-4-7",    "Claude Opus 4.7   — most capable"),
        },
        "default_model": "claude-haiku-4-5",
    },
    "openai": {
        "label": "OpenAI",
        "env_key": "OPENAI_API_KEY",
        "models": {
            "1": ("gpt-4o-mini",  "GPT-4o Mini — cheapest, fastest"),
            "2": ("gpt-4o",       "GPT-4o      — balanced"),
            "3": ("gpt-4.1",      "GPT-4.1     — most capable"),
        },
        "default_model": "gpt-4o-mini",
    },
    "ollama": {
        "label": "Ollama (local)",
        "env_key": "",
        "models": {
            "1": ("qwen2.5-coder:7b",    "Qwen 2.5 Coder 7B   — best JSON/structured output  ✦ recommended"),
            "2": ("deepseek-coder-v2",   "DeepSeek Coder V2   — strong code & JSON generation"),
            "3": ("llama3.1:8b",         "Llama 3.1 8B        — solid instruction following"),
            "4": ("mistral:7b",          "Mistral 7B          — fast, reliable JSON output"),
            "5": ("phi4:14b",            "Phi 4 14B           — strong reasoning, structured output"),
            "6": ("__custom__",          "Other               — enter model name manually"),
        },
        "default_model": "qwen2.5-coder:7b",
    },
}

# ---------------------------------------------------------------------------
# Module-level state (set once via setup())
# ---------------------------------------------------------------------------

_provider: str = ""
_model: str = ""
_client = None          # anthropic.Anthropic  OR  google.genai.Client


# ---------------------------------------------------------------------------
# Setup — call this before generate_test_cases()
# ---------------------------------------------------------------------------

def setup(provider: str, model: str, api_key: str) -> None:
    global _provider, _model, _client

    _provider = provider
    _model = model

    if provider == "gemini":
        from google import genai
        _client = genai.Client(api_key=api_key)
        logger.info("Gemini client ready  (model: %s)", model)

    elif provider == "claude":
        import anthropic
        _client = anthropic.Anthropic(api_key=api_key)
        logger.info("Claude client ready  (model: %s)", model)

    elif provider == "openai":
        import openai
        _client = openai.OpenAI(api_key=api_key)
        logger.info("OpenAI client ready  (model: %s)", model)

    elif provider == "ollama":
        import openai
        _client = openai.OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
        logger.info("Ollama client ready  (model: %s)", model)

    else:
        raise ValueError(f"Unknown provider: {provider!r}")


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def generate_test_cases(method: str, endpoint: str, payload: str | None, description: str | None = None, count: int | None = None) -> list[TestCase]:
    if not _provider:
        raise RuntimeError("Call ai_client.setup() before generate_test_cases().")

    count_instruction = f"exactly {count}" if count else "8-12"
    user_message = (
        f"Generate {count_instruction} test cases covering all 4 categories for:\n"
        f"Method:   {method}\n"
        f"Endpoint: {endpoint}\n"
        f"Payload:  {payload or 'None'}\n"
        f"API Description: {description or 'None'}"
    )

    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            if _provider == "gemini":
                return _call_gemini(user_message)
            elif _provider == "claude":
                return _call_claude(user_message)
            elif _provider == "ollama":
                return _call_ollama(user_message)
            else:
                return _call_openai(user_message)
        except json.JSONDecodeError as e:
            last_exc = e
            logger.warning("JSON parse error on attempt %d/3 — retrying: %s", attempt + 1, e)
        except Exception as e:
            last_exc = e
            msg = str(e)
            if "503" in msg or "UNAVAILABLE" in msg or "502" in msg:
                wait = 10 * (attempt + 1)
                logger.warning("Server unavailable (attempt %d/3) — retrying in %ds…", attempt + 1, wait)
                time.sleep(wait)
            else:
                raise
    raise last_exc


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

def _parse_response(text: str) -> list[TestCase]:
    """Strip optional markdown fences, parse JSON, validate each test case."""
    from json_repair import repair_json
    from pydantic import ValidationError

    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = lines[1:]
        try:
            close = next(i for i, l in enumerate(inner) if l.strip().startswith("```"))
            inner = inner[:close]
        except StopIteration:
            pass
        text = "\n".join(inner).strip()

    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        repaired = repair_json(text)
        raw = json.loads(repaired)

    valid: list[TestCase] = []
    for i, item in enumerate(raw):
        try:
            valid.append(TestCase.model_validate(item))
        except ValidationError as e:
            name = item.get("name", f"item {i + 1}") if isinstance(item, dict) else f"item {i + 1}"
            logger.warning("Skipping test case %r — validation error: %s", name, e)

    if not valid:
        raise ValueError("All test cases returned by AI failed validation — check logs for details.")

    if len(valid) < len(raw):
        logger.warning("Validation: %d/%d test cases passed, %d skipped", len(valid), len(raw), len(raw) - len(valid))
    else:
        logger.info("Validation: all %d test cases passed", len(valid))

    return valid


def _call_gemini(user_message: str) -> list[TestCase]:
    from google.genai import types

    logger.info("Calling Gemini API  (model: %s) …", _model)

    response = _client.models.generate_content(
        model=_model,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.3,
            response_mime_type="application/json",
        ),
        contents=user_message,
    )

    text = response.text
    cases = _parse_response(text)
    logger.info("Generated %d test cases via Gemini", len(cases))
    return cases


def _call_claude(user_message: str) -> list[TestCase]:
    logger.info("Calling Claude API  (model: %s) …", _model)

    response = _client.messages.create(
        model=_model,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )

    text = response.content[0].text
    cases = _parse_response(text)
    logger.info(
        "Generated %d test cases via Claude  (tokens: %d, cached: %d)",
        len(cases),
        response.usage.input_tokens,
        response.usage.cache_read_input_tokens or 0,
    )
    return cases


def _call_ollama(user_message: str) -> list[TestCase]:
    logger.info("Calling Ollama API  (model: %s) …", _model)

    response = _client.chat.completions.create(
        model=_model,
        temperature=0.3,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
    )

    text = response.choices[0].message.content
    cases = _parse_response(text)
    logger.info("Generated %d test cases via Ollama", len(cases))
    return cases


def _call_openai(user_message: str) -> list[TestCase]:
    logger.info("Calling OpenAI API  (model: %s) …", _model)

    response = _client.chat.completions.create(
        model=_model,
        temperature=0.3,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
    )

    text = response.choices[0].message.content
    cases = _parse_response(text)
    logger.info(
        "Generated %d test cases via OpenAI  (tokens: %d)",
        len(cases),
        response.usage.total_tokens,
    )
    return cases
