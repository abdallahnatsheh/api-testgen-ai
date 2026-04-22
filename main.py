import json
import logging
import os
import sys
from dataclasses import dataclass
from urllib.parse import urlparse

import ai_client
from ai_client import PROVIDERS
from colors import (BOLD, CYAN, DIM, GREEN, RED, RESET, YELLOW,
                    CATEGORY_COLOR, CATEGORY_LABEL)
from models import TestCase
from tester import run_tests

SETTINGS_FILE = "settings.json"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Settings persistence
# ---------------------------------------------------------------------------

def load_settings() -> dict | None:
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    return None


def save_settings(provider: str, model: str, api_key: str) -> None:
    with open(SETTINGS_FILE, "w") as f:
        json.dump({"provider": provider, "model": model, "api_key": api_key}, f, indent=2)
    print(f"\n  {GREEN}✓ Settings saved to {SETTINGS_FILE}{RESET}")


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

def _prompt(label: str, default: str = "") -> str:
    hint = f"  [{default}]" if default else ""
    return input(f"  {CYAN}{label}{hint}:{RESET} ").strip()


def _pick(options: dict, prompt_text: str, default: str = "1") -> str:
    for key, (_, label) in options.items():
        print(f"    {YELLOW}{key}{RESET}. {label}")
    choice = _prompt(prompt_text, default) or default
    if choice not in options:
        print(f"  {RED}Invalid choice — using default.{RESET}")
        choice = default
    return options[choice][0]


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

def print_banner(provider_label: str = "", model: str = "") -> None:
    print(f"\n{BOLD}{'═' * 62}{RESET}")
    print(f"{BOLD}   AI API Test Assistant{RESET}")
    if provider_label and model:
        print(f"   {DIM}Provider: {provider_label}   Model: {model}{RESET}")
    print(f"{BOLD}{'═' * 62}{RESET}\n")


# ---------------------------------------------------------------------------
# Provider / model selection
# ---------------------------------------------------------------------------

def select_provider() -> tuple[str, str, str]:
    settings = load_settings()

    if settings:
        provider = settings["provider"]
        model    = settings["model"]
        api_key  = settings["api_key"]
        cfg      = PROVIDERS[provider]

        print(f"\n{BOLD}  Saved Settings{RESET}")
        print(f"    Provider : {cfg['label']}")
        print(f"    Model    : {model}")
        print(f"    API Key  : {api_key[:8]}{'*' * (len(api_key) - 8)}")

        change = _prompt("\n  Use these settings? (y/n)", "y") or "y"
        if change.lower() == "y":
            return provider, model, api_key

    print(f"\n{BOLD}  Step 1 — Choose AI Provider{RESET}\n")
    print(f"    {YELLOW}1{RESET}. Google Gemini  {GREEN}(free — recommended){RESET}")
    print(f"    {YELLOW}2{RESET}. Anthropic Claude  {DIM}(requires paid API key){RESET}")
    print(f"    {YELLOW}3{RESET}. OpenAI  {DIM}(requires paid API key){RESET}")
    print(f"    {YELLOW}4{RESET}. Ollama  {GREEN}(local — free, no API key){RESET}")

    choice = _prompt("Provider", "1") or "1"
    provider = {"1": "gemini", "2": "claude", "3": "openai", "4": "ollama"}.get(choice, "gemini")
    cfg = PROVIDERS[provider]

    print(f"\n{BOLD}  Step 2 — Choose Model  ({cfg['label']}){RESET}\n")
    model = _pick(cfg["models"], "Model", "1")

    if model == "__custom__":
        model = _prompt("Enter Ollama model name  (e.g. llama3.2, phi4:14b)")
        if not model:
            print(f"\n  {RED}Model name is required. Exiting.{RESET}\n")
            sys.exit(1)

    if provider == "ollama":
        api_key = "ollama"
    else:
        env_key = os.environ.get(cfg["env_key"], "")
        if env_key:
            print(f"\n  {GREEN}✓ API key loaded from environment ({cfg['env_key']}){RESET}")
            api_key = env_key
        else:
            print(f"\n{BOLD}  Step 3 — Enter API Key{RESET}")
            if provider == "gemini":
                print(f"  {DIM}Get a free key at: https://aistudio.google.com → 'Get API key'{RESET}")
            else:
                print(f"  {DIM}Get a key at: https://console.anthropic.com{RESET}")
            api_key = _prompt(f"{cfg['label']} API key")
            if not api_key:
                print(f"\n  {RED}API key is required. Exiting.{RESET}\n")
                sys.exit(1)

    if (_prompt("Save these settings? (y/n)", "y") or "y").lower() == "y":
        save_settings(provider, model, api_key)
    return provider, model, api_key


# ---------------------------------------------------------------------------
# Test case display
# ---------------------------------------------------------------------------

def print_test_cases(test_cases: list[TestCase]) -> None:
    grouped: dict[str, list[TestCase]] = {}
    for tc in test_cases:
        grouped.setdefault(tc.category, []).append(tc)

    print(f"\n{BOLD}  Generated {len(test_cases)} test cases{RESET}\n")

    for category, tests in grouped.items():
        color = CATEGORY_COLOR.get(category, "")
        label = CATEGORY_LABEL.get(category, category.title())
        print(f"  {color}{BOLD}{label}{RESET}  ({len(tests)} tests)")

        for tc in tests:
            payload_hint = ""
            if tc.input.payload:
                keys = list(tc.input.payload.keys())
                payload_hint = f"  payload={{{', '.join(keys)}}}"

            print(f"    {YELLOW}▸{RESET} {tc.name}")
            print(f"      {DIM}{tc.description}{RESET}")
            print(
                f"      {tc.input.method} {tc.input.endpoint}{payload_hint}"
                f"  → expect {tc.expected_result.status_code}"
                + (f", key='{tc.expected_result.contains_key}'" if tc.expected_result.contains_key else "")
            )
        print()


def save_test_cases(test_cases: list[TestCase]) -> None:
    filename = _prompt("Filename", "test_cases.json") or "test_cases.json"
    with open(filename, "w") as f:
        json.dump([tc.model_dump() for tc in test_cases], f, indent=2)
    logger.info("Saved to %s", filename)
    print(f"\n  {GREEN}✓ Saved to {filename}{RESET}\n")


# ---------------------------------------------------------------------------
# Endpoint input
# ---------------------------------------------------------------------------

@dataclass
class CollectedInput:
    method: str
    base_url: str
    path: str
    payload: str | None
    description: str | None
    auth_headers: dict
    count: int | None = None


def _parse_base_and_path(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path or "/"
    return base, path


def _collect_auth() -> dict:
    print(f"\n{BOLD}  Authentication  {DIM}(optional){RESET}\n")
    print(f"    {YELLOW}1{RESET}. None")
    print(f"    {YELLOW}2{RESET}. Bearer Token")
    print(f"    {YELLOW}3{RESET}. API Key Header")

    choice = _prompt("Auth type", "1") or "1"

    if choice == "2":
        token = _prompt("Bearer token value")
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}

    if choice == "3":
        name  = _prompt("Header name  (e.g. X-API-Key)")
        value = _prompt("Header value")
        if not name or not value:
            return {}
        return {name: value}

    return {}


def _load_description() -> str | None:
    print(f"\n  {BOLD}API Description{RESET}  {DIM}(helps AI generate accurate tests){RESET}")
    print(f"    {YELLOW}1{RESET}. Type inline")
    print(f"    {YELLOW}2{RESET}. Load from file  {DIM}(.txt or .md){RESET}")
    print(f"    {YELLOW}3{RESET}. Skip")
    choice = _prompt("Choice", "3") or "3"

    if choice == "1":
        text = _prompt("Description")
        return text or None

    if choice == "2":
        path = _prompt("File path  (e.g. login_api.md)")
        if not path:
            return None
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read().strip()
            print(f"  {GREEN}✓ Loaded {len(content)} chars from {path}{RESET}")
            logger.info("Description loaded from file: %s (%d chars)", path, len(content))
            return content or None
        except FileNotFoundError:
            print(f"  {RED}File not found: {path} — skipping description.{RESET}")
            return None

    return None


def collect_inputs() -> CollectedInput:
    print(f"\n{BOLD}  Describe the API endpoint to test{RESET}\n")

    method = _prompt("HTTP Method (GET, POST, PUT, DELETE)", "GET").upper() or "GET"

    full_url = _prompt("Full endpoint URL  (e.g. https://api.example.com/v1/login)")
    if not full_url:
        print(f"\n  {RED}Endpoint URL is required. Exiting.{RESET}\n")
        sys.exit(1)

    base_url, path = _parse_base_and_path(full_url)
    print(f"  {DIM}Base URL: {base_url}   Path: {path}{RESET}")

    payload = _prompt("Request Payload (JSON, Enter to skip)") or None
    description = _load_description()

    count_str = _prompt("Number of test cases to generate (Enter for default 8-12)") or ""
    count: int | None = None
    if count_str.isdigit() and int(count_str) > 0:
        count = int(count_str)
        print(f"  {DIM}Generating exactly {count} test cases{RESET}")
    else:
        print(f"  {DIM}Generating 8-12 test cases (default){RESET}")

    auth_headers = _collect_auth()
    if auth_headers:
        print(f"  {GREEN}✓ Auth header set: {list(auth_headers.keys())[0]}{RESET}")

    return CollectedInput(
        method=method,
        base_url=base_url,
        path=path,
        payload=payload,
        description=description,
        auth_headers=auth_headers,
        count=count,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _setup_logging() -> None:
    fmt = "%(asctime)s  [%(levelname)-8s]  %(name)s — %(message)s"
    datefmt = "%H:%M:%S"

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(fmt, datefmt))

    file_handler = logging.FileHandler("test_run.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(fmt, datefmt))

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(console)
    root.addHandler(file_handler)


def main() -> None:
    _setup_logging()

    print(f"  {DIM}Detailed logs → test_run.log{RESET}\n")
    provider, model, api_key = select_provider()
    ai_client.setup(provider, model, api_key)

    provider_label = PROVIDERS[provider]["label"]
    print_banner(provider_label, model)

    inputs = collect_inputs()

    print(f"\n  Generating test cases with {provider_label}…\n")
    logger.info("Generating for %s %s%s", inputs.method, inputs.base_url, inputs.path)

    try:
        test_cases = ai_client.generate_test_cases(inputs.method, inputs.path, inputs.payload, inputs.description, inputs.count)
    except Exception as e:
        logger.error("Generation failed: %s", e)
        print(f"\n  {RED}Error: {e}{RESET}\n")
        sys.exit(1)

    print_test_cases(test_cases)

    if _prompt("Save test cases to file? (y/n)").lower() == "y":
        save_test_cases(test_cases)

    if _prompt("Execute test cases against the API? (y/n)").lower() != "y":
        print(f"\n  Done. Test cases generated but not executed.\n")
        return

    logger.info("Executing %d tests against %s", len(test_cases), inputs.base_url)
    run_tests(test_cases, inputs.base_url, global_headers=inputs.auth_headers)


if __name__ == "__main__":
    main()
