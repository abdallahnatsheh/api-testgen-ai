import json
import logging
import sys

import requests

from colors import (BOLD, CYAN, DIM, GREEN, RED, RESET, YELLOW,
                    CATEGORY_COLOR, CATEGORY_LABEL)
from models import TestCase

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_url(base_url: str, endpoint: str) -> str:
    base = base_url.rstrip("/")
    path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    return f"{base}{path}"


def _truncate(text: str, limit: int = 120) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def _pretty_json(data) -> str:
    try:
        return json.dumps(data, indent=None, separators=(", ", ": "))
    except Exception:
        return str(data)


# ---------------------------------------------------------------------------
# Core executor
# ---------------------------------------------------------------------------

def run_tests(test_cases: list[TestCase], base_url: str, global_headers: dict | None = None) -> int:
    """Run all test cases and return the number of failures."""
    divider = "─" * 64
    global_headers = global_headers or {}

    print(f"\n{BOLD}{'═' * 64}{RESET}")
    print(f"{BOLD}  Running {len(test_cases)} test cases against {base_url}{RESET}")
    if global_headers:
        print(f"{DIM}  Auth headers: {', '.join(global_headers.keys())}{RESET}")
    print(f"{BOLD}{'═' * 64}{RESET}\n")

    passed = 0
    failed = 0

    for i, tc in enumerate(test_cases, 1):
        cat_color = CATEGORY_COLOR.get(tc.category, "")
        cat_label = CATEGORY_LABEL.get(tc.category, tc.category.upper())
        url = _build_url(base_url, tc.input.endpoint)

        print(f"{BOLD}{i:2}.{RESET} {cat_color}[{cat_label.upper():10}]{RESET}  {BOLD}{tc.name}{RESET}")
        print(f"    {CYAN}{tc.description}{RESET}")
        print(f"    {divider}")

        payload_str = _pretty_json(tc.input.payload) if tc.input.payload else "—"
        print(f"    {YELLOW}→ REQUEST {RESET} {tc.input.method}  {url}")
        print(f"    {YELLOW}  Payload  {RESET} {_truncate(payload_str)}")

        merged_headers = {**global_headers, **tc.input.headers}

        try:
            resp = requests.request(
                method=tc.input.method,
                url=url,
                json=tc.input.payload,
                headers=merged_headers,
                timeout=5,
            )

            try:
                body = resp.json()
                body_str = _pretty_json(body)
            except Exception:
                body = None
                body_str = resp.text or "—"

            print(f"    {CYAN}← RESPONSE{RESET} {resp.status_code} {resp.reason}")
            print(f"    {CYAN}  Body     {RESET} {_truncate(body_str)}")

            status_ok = resp.status_code == tc.expected_result.status_code

            key_ok = True
            if tc.expected_result.contains_key:
                if isinstance(body, dict):
                    key_ok = tc.expected_result.contains_key in body
                else:
                    key_ok = False

            value_ok = True
            value_fail_reason = ""
            if tc.expected_result.contains_value and isinstance(body, dict):
                for k, expected in tc.expected_result.contains_value.items():
                    actual = body.get(k)
                    if actual != expected:
                        value_ok = False
                        value_fail_reason = f"expected {k}={expected!r}, got {actual!r}"
                        break

            ok = status_ok and key_ok and value_ok

            if ok:
                passed += 1
                verdict = f"{GREEN}✓ PASS{RESET}"
            else:
                failed += 1
                reason_parts = []
                if not status_ok:
                    reason_parts.append(
                        f"expected status {tc.expected_result.status_code}, got {resp.status_code}"
                    )
                if not key_ok:
                    reason_parts.append(
                        f"key '{tc.expected_result.contains_key}' missing from response"
                    )
                if not value_ok:
                    reason_parts.append(value_fail_reason)
                verdict = f"{RED}✗ FAIL{RESET}  ({', '.join(reason_parts)})"

            logger.debug("Test '%s': status=%d key_ok=%s", tc.name, resp.status_code, key_ok)

        except requests.exceptions.ConnectionError:
            failed += 1
            verdict = f"{RED}✗ ERROR{RESET}  — could not connect to {base_url}"
            logger.error("Connection error for test '%s': %s", tc.name, url)

        except requests.exceptions.Timeout:
            failed += 1
            verdict = f"{RED}✗ ERROR{RESET}  — request timed out"
            logger.error("Timeout for test '%s': %s", tc.name, url)

        except Exception as e:
            failed += 1
            verdict = f"{RED}✗ ERROR{RESET}  — {e}"
            logger.exception("Unexpected error for test '%s'", tc.name)

        print(f"    {divider}")
        print(f"    {verdict}\n")

    print(f"{BOLD}{'═' * 64}{RESET}")
    total = len(test_cases)
    print(
        f"{BOLD}  Results:{RESET}  "
        f"{GREEN}{passed} passed{RESET}  "
        f"{RED}{failed} failed{RESET}  "
        f"({total} total)"
    )
    print(f"{BOLD}{'═' * 64}{RESET}\n")

    return failed


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run API test cases from a JSON file against a live server.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("json_file", help="Path to test cases JSON file")
    parser.add_argument("base_url", help="Base URL of the API  (e.g. https://api.example.com)")
    parser.add_argument(
        "--bearer",
        metavar="TOKEN",
        help="Bearer token — adds Authorization: Bearer <TOKEN> to every request",
    )
    parser.add_argument(
        "--header",
        metavar="NAME=VALUE",
        action="append",
        dest="headers",
        help="Custom header in NAME=VALUE format (repeatable)",
    )

    args = parser.parse_args()

    global_headers: dict = {}
    if args.bearer:
        global_headers["Authorization"] = f"Bearer {args.bearer}"
    if args.headers:
        for h in args.headers:
            if "=" not in h:
                print(f"Invalid header format: {h!r}  (expected NAME=VALUE)")
                sys.exit(1)
            name, _, value = h.partition("=")
            global_headers[name.strip()] = value.strip()

    with open(args.json_file) as f:
        cases = [TestCase.model_validate(tc) for tc in json.load(f)]

    sys.exit(run_tests(cases, args.base_url, global_headers=global_headers))
