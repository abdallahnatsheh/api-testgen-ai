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
from postman_importer import load_collection
from openapi_importer import load_spec
import tester
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


def _flush_stdin() -> None:
    try:
        import termios
        termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except Exception:
        pass


def _run_postman_import(provider_label: str, base_url: str, auth_headers: dict, count: int | None) -> None:
    collection_path = _prompt("Postman collection file path  (e.g. collection.json)")
    if not collection_path:
        print(f"  {RED}File path is required. Exiting.{RESET}\n")
        sys.exit(1)

    try:
        requests = load_collection(collection_path)
    except Exception as e:
        print(f"  {RED}Failed to load collection: {e}{RESET}\n")
        sys.exit(1)

    print(f"\n  {GREEN}✓ Loaded {len(requests)} requests from collection{RESET}\n")

    description = _load_description()

    all_test_cases: list[TestCase] = []

    for req in requests:
        print(f"  {CYAN}Generating tests for:{RESET} {req.method} {req.path}  {DIM}({req.name}){RESET}")
        try:
            test_cases = ai_client.generate_test_cases(req.method, req.path, json.dumps(req.payload) if req.payload else None, description, count)
            all_test_cases.extend(test_cases)
            print(f"  {GREEN}✓ {len(test_cases)} test cases generated{RESET}\n")
        except Exception as e:
            logger.error("Generation failed for %s %s: %s", req.method, req.path, e)
            print(f"  {RED}✗ Failed: {e}{RESET}\n")

    if not all_test_cases:
        print(f"  {RED}No test cases generated. Exiting.{RESET}\n")
        sys.exit(1)

    print_test_cases(all_test_cases)

    _flush_stdin()

    if _prompt("Save all test cases to file? (y/n)").lower() == "y":
        save_test_cases(all_test_cases)

    if _prompt("Execute test cases against the API? (y/n)").lower() != "y":
        print(f"\n  Done. Test cases generated but not executed.\n")
        return

    merged_headers = {**auth_headers}
    run_tests(all_test_cases, base_url, global_headers=merged_headers)


def _parse_args():
    import argparse
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="AI-powered API test case generator",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # Input mode
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--url", metavar="URL", help="Full endpoint URL  (e.g. http://localhost:8000/login)")
    group.add_argument("--postman", metavar="FILE", help="Postman collection JSON file")
    group.add_argument("--openapi", metavar="FILE", help="OpenAPI/Swagger spec file (.yaml or .json)")

    parser.add_argument("--method", metavar="METHOD", default="GET", help="HTTP method (default: GET)")
    parser.add_argument("--base-url", metavar="URL", help="Base URL for Postman import  (e.g. http://localhost:8000)")
    parser.add_argument("--payload", metavar="JSON", help="Request payload as JSON string")
    parser.add_argument("--description", metavar="FILE", help="Path to API description .md file")
    parser.add_argument("--count", metavar="N", type=int, help="Number of test cases to generate per endpoint")
    parser.add_argument("--bearer", metavar="TOKEN", help="Bearer token for auth")
    parser.add_argument("--header", metavar="NAME=VALUE", action="append", dest="headers", help="Custom header (repeatable)")
    parser.add_argument("--auth-url", metavar="URL", help="POST to this URL before running tests to obtain a Bearer token")
    parser.add_argument("--auth-payload", metavar="JSON", help="JSON payload for the auth request")
    parser.add_argument("--auth-token-path", metavar="PATH", default="token", help="Dot-notation path to token in auth response (default: token)")
    parser.add_argument("--save",    metavar="FILE", help="Save test cases to this file automatically")
    parser.add_argument("--no-run",  action="store_true", help="Skip test execution after generation (default: run automatically)")
    parser.add_argument("--run",     action="store_true", help=argparse.SUPPRESS)  # kept for backward compat
    parser.add_argument("--provider",      metavar="PROVIDER", choices=["gemini", "claude", "openai", "ollama"], help="AI provider")
    parser.add_argument("--model",         metavar="MODEL", help="Model name")
    parser.add_argument("--api-key",       metavar="KEY",  help="API key for the provider")
    parser.add_argument("--save-settings", action="store_true", help="Save --provider/--model/--api-key to settings.json for future runs")

    return parser.parse_args()


def _save_and_run(
    test_cases: list[TestCase],
    base_url: str,
    auth_headers: dict,
    args,
    non_interactive: bool,
) -> None:
    """Save test cases (if requested) and run them (unless --no-run is set)."""
    if args.save:
        with open(args.save, "w") as f:
            json.dump([tc.model_dump() for tc in test_cases], f, indent=2)
        print(f"\n  {GREEN}✓ Saved to {args.save}{RESET}\n")
    elif not non_interactive:
        if _prompt("Save test cases to file? (y/n)").lower() == "y":
            save_test_cases(test_cases)

    if non_interactive:
        should_run = not args.no_run
    else:
        should_run = _prompt("Execute test cases against the API? (y/n)").lower() == "y"

    if should_run:
        logger.info("Executing %d tests against %s", len(test_cases), base_url)
        run_tests(test_cases, base_url, global_headers=auth_headers)
    else:
        print(f"\n  Done. Test cases generated but not executed.\n")


def _build_auth_headers(args) -> dict:
    headers = {}
    if args.bearer:
        headers["Authorization"] = f"Bearer {args.bearer}"
    if args.headers:
        for h in args.headers:
            if "=" not in h:
                print(f"  {RED}Invalid header format: {h!r}  (expected NAME=VALUE){RESET}")
                sys.exit(1)
            name, _, value = h.partition("=")
            headers[name.strip()] = value.strip()
    if getattr(args, "auth_url", None):
        if not getattr(args, "auth_payload", None):
            print(f"  {RED}--auth-payload is required with --auth-url{RESET}\n")
            sys.exit(1)
        token = tester._fetch_auth_token(args.auth_url, args.auth_payload, args.auth_token_path)
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _load_description_from_file(path: str) -> str | None:
    try:
        from pathlib import Path
        content = Path(path).read_text(encoding="utf-8").strip()
        print(f"  {GREEN}✓ Description loaded from {path}{RESET}")
        return content or None
    except FileNotFoundError:
        print(f"  {RED}Description file not found: {path}{RESET}")
        return None


def main() -> None:
    _setup_logging()
    args = _parse_args()
    non_interactive = bool(args.url or args.postman or args.openapi)

    print(f"  {DIM}Detailed logs → test_run.log{RESET}\n")

    # Provider setup
    if non_interactive and args.provider:
        settings = load_settings() or {}
        provider = args.provider
        model = args.model or list(PROVIDERS[provider]["models"].values())[0][0]
        api_key = args.api_key or ("ollama" if provider == "ollama" else settings.get("api_key", ""))
        if not api_key:
            print(f"  {RED}--api-key is required for {provider}{RESET}\n")
            sys.exit(1)
        ai_client.setup(provider, model, api_key)
        provider_label = PROVIDERS[provider]["label"]
        if args.save_settings:
            save_settings(provider, model, api_key)
    elif non_interactive and not args.provider:
        settings = load_settings() or {}
        provider = settings.get("provider", "")
        model = settings.get("model", "")
        api_key = settings.get("api_key", "")
        if not provider or (not api_key and provider != "ollama"):
            print(f"  {RED}No provider configured. Run interactively once or pass --provider + --api-key.{RESET}\n")
            sys.exit(1)
        ai_client.setup(provider, model, api_key)
        provider_label = PROVIDERS[provider]["label"]
    else:
        provider, model, api_key = select_provider()
        ai_client.setup(provider, model, api_key)
        provider_label = PROVIDERS[provider]["label"]

    print_banner(provider_label, model)

    auth_headers = _build_auth_headers(args) if non_interactive else {}
    count: int | None = args.count if non_interactive else None
    description: str | None = None

    if args.description:
        description = _load_description_from_file(args.description)

    # --- OpenAPI mode ---
    if args.openapi:
        try:
            spec_base_url, openapi_requests = load_spec(args.openapi)
        except Exception as e:
            print(f"  {RED}Failed to load spec: {e}{RESET}\n")
            sys.exit(1)

        base_url = args.base_url or spec_base_url
        if not description and not non_interactive:
            description = _load_description()
        if not auth_headers and not non_interactive:
            auth_headers = _collect_auth()

        print(f"\n  {GREEN}✓ Loaded {len(openapi_requests)} operations from spec{RESET}")
        print(f"  {DIM}Base URL: {base_url}{RESET}\n")
        all_test_cases: list[TestCase] = []

        for req in openapi_requests:
            op_description = description or req.description
            print(f"  {CYAN}Generating tests for:{RESET} {req.method} {req.path}  {DIM}({req.name}){RESET}")
            try:
                tcs = ai_client.generate_test_cases(req.method, req.path, json.dumps(req.payload) if req.payload else None, op_description, count)
                all_test_cases.extend(tcs)
                print(f"  {GREEN}✓ {len(tcs)} test cases generated{RESET}\n")
            except Exception as e:
                logger.error("Generation failed for %s %s: %s", req.method, req.path, e)
                print(f"  {RED}✗ Failed: {e}{RESET}\n")

        if not all_test_cases:
            print(f"  {RED}No test cases generated. Exiting.{RESET}\n")
            sys.exit(1)

        print_test_cases(all_test_cases)
        _flush_stdin()
        _save_and_run(all_test_cases, base_url, auth_headers, args, non_interactive)
        return

    # --- Postman mode ---
    if args.postman:
        base_url = args.base_url
        if not base_url:
            print(f"  {RED}--base-url is required with --postman{RESET}\n")
            sys.exit(1)
        if not description and not non_interactive:
            description = _load_description()
        if not auth_headers and not non_interactive:
            auth_headers = _collect_auth()

        try:
            postman_requests = load_collection(args.postman)
        except Exception as e:
            print(f"  {RED}Failed to load collection: {e}{RESET}\n")
            sys.exit(1)

        print(f"\n  {GREEN}✓ Loaded {len(postman_requests)} requests from collection{RESET}\n")
        all_test_cases: list[TestCase] = []

        for req in postman_requests:
            print(f"  {CYAN}Generating tests for:{RESET} {req.method} {req.path}  {DIM}({req.name}){RESET}")
            try:
                tcs = ai_client.generate_test_cases(req.method, req.path, json.dumps(req.payload) if req.payload else None, description, count)
                all_test_cases.extend(tcs)
                print(f"  {GREEN}✓ {len(tcs)} test cases generated{RESET}\n")
            except Exception as e:
                logger.error("Generation failed for %s %s: %s", req.method, req.path, e)
                print(f"  {RED}✗ Failed: {e}{RESET}\n")

        if not all_test_cases:
            print(f"  {RED}No test cases generated. Exiting.{RESET}\n")
            sys.exit(1)

        print_test_cases(all_test_cases)
        _flush_stdin()
        _save_and_run(all_test_cases, base_url, auth_headers, args, non_interactive)
        return

    # --- Manual mode ---
    if args.url:
        base_url, path = _parse_base_and_path(args.url)
        print(f"  {DIM}Base URL: {base_url}   Path: {path}{RESET}")
        if not description and not non_interactive:
            description = _load_description()
        if not auth_headers and not non_interactive:
            auth_headers = _collect_auth()
        if count is None and not non_interactive:
            count_str = _prompt("Number of test cases to generate (Enter for default 8-12)") or ""
            count = int(count_str) if count_str.isdigit() and int(count_str) > 0 else None
        inputs = CollectedInput(
            method=args.method.upper(),
            base_url=base_url,
            path=path,
            payload=args.payload,
            description=description,
            auth_headers=auth_headers,
            count=count,
        )
    else:
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
    _flush_stdin()
    _save_and_run(test_cases, inputs.base_url, inputs.auth_headers, args, non_interactive)


if __name__ == "__main__":
    main()
