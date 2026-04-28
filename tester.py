import json
import logging
import sys
import time

import jsonschema
import requests

from colors import (BOLD, CYAN, DIM, GREEN, RED, RESET, YELLOW,
                    CATEGORY_COLOR, CATEGORY_LABEL)
from models import TestCase

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_auth_token(auth_url: str, auth_payload: str, token_path: str) -> str:
    """POST to auth_url, walk token_path (dot-notation) in the JSON response, return the token."""
    print(f"  {YELLOW}→ Auth   {RESET} POST {auth_url}")
    try:
        payload = json.loads(auth_payload)
    except json.JSONDecodeError as e:
        print(f"  {RED}--auth-payload is not valid JSON: {e}{RESET}")
        sys.exit(1)

    try:
        resp = requests.post(auth_url, json=payload, timeout=10)
    except requests.exceptions.RequestException as e:
        print(f"  {RED}Auth request failed: {e}{RESET}")
        sys.exit(1)

    if not resp.ok:
        print(f"  {RED}Auth failed: {resp.status_code} {resp.reason}{RESET}")
        sys.exit(1)

    try:
        body = resp.json()
    except Exception:
        print(f"  {RED}Auth response is not JSON{RESET}")
        sys.exit(1)

    token: object = body
    for part in token_path.split("."):
        if not isinstance(token, dict) or part not in token:
            print(f"  {RED}Token path '{token_path}' not found in auth response. Keys: {list(body.keys()) if isinstance(body, dict) else body}{RESET}")
            sys.exit(1)
        token = token[part]

    if not isinstance(token, str):
        print(f"  {RED}Token at '{token_path}' is not a string (got {type(token).__name__}){RESET}")
        sys.exit(1)

    print(f"  {GREEN}✓ Token  {RESET} {token[:30]}…  (path: '{token_path}')\n")
    return token


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
# HTML report
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Test Report</title>
<style>
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; font-size: 16px; margin: 0; padding: 0; background: #f8fafc; color: #1e293b; }}
  header {{ background: #1e293b; color: #f1f5f9; padding: 20px 32px; font-size: 1.4rem; font-weight: 700; }}
  .summary {{ display: flex; gap: 24px; padding: 16px 32px; background: #fff; border-bottom: 1px solid #e2e8f0; font-size: 15px; }}
  .summary span {{ font-weight: 700; }}
  .pass {{ color: #16a34a; }} .fail {{ color: #dc2626; }} .err {{ color: #ea580c; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: #f1f5f9; text-align: left; padding: 10px 16px; font-size: 13px; color: #64748b; border-bottom: 2px solid #e2e8f0; position: sticky; top: 0; }}
  td {{ padding: 10px 16px; border-bottom: 1px solid #f1f5f9; font-size: 14px; vertical-align: top; }}
  tr:hover td {{ background: #f8fafc; }}
  .row-pass td:first-child {{ border-left: 3px solid #16a34a; }}
  .row-fail td:first-child {{ border-left: 3px solid #dc2626; }}
  .row-err  td:first-child {{ border-left: 3px solid #ea580c; }}
  .badge {{ display: inline-block; border-radius: 4px; padding: 2px 8px; font-size: 12px; font-weight: 600; }}
  .badge-pass {{ background: #dcfce7; color: #16a34a; }}
  .badge-fail {{ background: #fee2e2; color: #dc2626; }}
  .badge-err  {{ background: #ffedd5; color: #ea580c; }}
  .reason {{ color: #dc2626; font-size: 13px; margin-top: 4px; }}
  .dim {{ color: #94a3b8; font-size: 13px; }}
</style>
</head>
<body>
<header>API Test Report — {base_url}</header>
<div class="summary">
  <div>Total: <span>{total}</span></div>
  <div class="pass">Passed: <span>{passed}</span></div>
  <div class="fail">Failed: <span>{failed}</span></div>
</div>
<table>
  <thead><tr><th>#</th><th>Test</th><th>Request</th><th>Status</th><th>Duration</th><th>Result</th></tr></thead>
  <tbody>{rows}</tbody>
</table>
</body>
</html>"""

_ROW_TEMPLATE = """<tr class="{row_class}">
  <td class="dim">{num}</td>
  <td><strong>{name}</strong><br><span class="dim">{category} · {description}</span></td>
  <td class="dim">{method} {endpoint}</td>
  <td class="dim">{status_code}</td>
  <td class="dim">{duration}</td>
  <td><span class="badge {badge_class}">{verdict}</span>{reason_html}</td>
</tr>"""


def _write_html_report(results: list[dict], base_url: str, html_path: str) -> None:
    rows = []
    for r in results:
        if r["verdict"] == "PASS":
            row_class, badge_class, verdict = "row-pass", "badge-pass", "PASS"
        elif r["verdict"] == "ERROR":
            row_class, badge_class, verdict = "row-err", "badge-err", "ERROR"
        else:
            row_class, badge_class, verdict = "row-fail", "badge-fail", "FAIL"

        reason_html = f'<div class="reason">{r["reason"]}</div>' if r.get("reason") else ""
        duration = f'{r["duration_ms"]:.0f} ms' if r.get("duration_ms") is not None else "—"

        rows.append(_ROW_TEMPLATE.format(
            num=r["num"],
            name=r["name"],
            category=r["category"],
            description=r["description"],
            method=r["method"],
            endpoint=r["endpoint"],
            status_code=r.get("status_code", "—"),
            duration=duration,
            row_class=row_class,
            badge_class=badge_class,
            verdict=verdict,
            reason_html=reason_html,
        ))

    passed = sum(1 for r in results if r["verdict"] == "PASS")
    failed = len(results) - passed
    html = _HTML_TEMPLATE.format(
        base_url=base_url,
        total=len(results),
        passed=passed,
        failed=failed,
        rows="".join(rows),
    )
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  HTML report → {html_path}")


# ---------------------------------------------------------------------------
# Core executor
# ---------------------------------------------------------------------------

def run_tests(
    test_cases: list[TestCase],
    base_url: str,
    global_headers: dict | None = None,
    html_path: str | None = None,
) -> int:
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
    results: list[dict] = []

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

        result: dict = {
            "num": i,
            "name": tc.name,
            "category": tc.category,
            "description": tc.description,
            "method": tc.input.method,
            "endpoint": tc.input.endpoint,
            "duration_ms": None,
            "status_code": None,
            "verdict": "FAIL",
            "reason": "",
        }

        try:
            t0 = time.monotonic()
            resp = requests.request(
                method=tc.input.method,
                url=url,
                json=tc.input.payload,
                headers=merged_headers,
                timeout=5,
            )
            elapsed_ms = (time.monotonic() - t0) * 1000
            result["duration_ms"] = elapsed_ms
            result["status_code"] = resp.status_code

            try:
                body = resp.json()
                body_str = _pretty_json(body)
            except Exception:
                body = None
                body_str = resp.text or "—"

            print(f"    {CYAN}← RESPONSE{RESET} {resp.status_code} {resp.reason}  {DIM}({elapsed_ms:.0f}ms){RESET}")
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

            time_ok = True
            if tc.expected_result.max_response_time_ms is not None:
                time_ok = elapsed_ms <= tc.expected_result.max_response_time_ms

            headers_ok = True
            headers_fail_reason = ""
            if tc.expected_result.response_headers:
                for h_key, h_expected in tc.expected_result.response_headers.items():
                    h_actual = resp.headers.get(h_key, "")
                    if h_expected.lower() not in h_actual.lower():
                        headers_ok = False
                        headers_fail_reason = f"header '{h_key}': expected {h_expected!r}, got {h_actual!r}"
                        break

            schema_ok = True
            schema_fail_reason = ""
            if tc.expected_result.response_schema and body is not None:
                try:
                    jsonschema.validate(instance=body, schema=tc.expected_result.response_schema)
                except jsonschema.ValidationError as e:
                    schema_ok = False
                    schema_fail_reason = e.message

            ok = status_ok and key_ok and value_ok and time_ok and headers_ok and schema_ok

            if ok:
                passed += 1
                verdict = f"{GREEN}✓ PASS{RESET}"
                result["verdict"] = "PASS"
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
                if not time_ok:
                    reason_parts.append(
                        f"response took {elapsed_ms:.0f}ms, limit {tc.expected_result.max_response_time_ms}ms"
                    )
                if not headers_ok:
                    reason_parts.append(headers_fail_reason)
                if not schema_ok:
                    reason_parts.append(f"schema: {schema_fail_reason}")
                reason = ", ".join(reason_parts)
                verdict = f"{RED}✗ FAIL{RESET}  ({reason})"
                result["verdict"] = "FAIL"
                result["reason"] = reason

            logger.debug(
                "Test '%s': status=%d key_ok=%s time=%.0fms",
                tc.name, resp.status_code, key_ok, elapsed_ms,
            )

        except requests.exceptions.ConnectionError:
            failed += 1
            verdict = f"{RED}✗ ERROR{RESET}  — could not connect to {base_url}"
            result["verdict"] = "ERROR"
            result["reason"] = f"could not connect to {base_url}"
            logger.error("Connection error for test '%s': %s", tc.name, url)

        except requests.exceptions.Timeout:
            failed += 1
            verdict = f"{RED}✗ ERROR{RESET}  — request timed out"
            result["verdict"] = "ERROR"
            result["reason"] = "request timed out"
            logger.error("Timeout for test '%s': %s", tc.name, url)

        except Exception as e:
            failed += 1
            verdict = f"{RED}✗ ERROR{RESET}  — {e}"
            result["verdict"] = "ERROR"
            result["reason"] = str(e)
            logger.exception("Unexpected error for test '%s'", tc.name)

        results.append(result)
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

    if html_path:
        _write_html_report(results, base_url, html_path)

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
    parser.add_argument(
        "--auth-url",
        metavar="URL",
        help="POST to this URL before running tests to obtain a Bearer token",
    )
    parser.add_argument(
        "--auth-payload",
        metavar="JSON",
        help="JSON payload for the auth request (e.g. '{\"email\":\"x\",\"password\":\"y\"}')",
    )
    parser.add_argument(
        "--auth-token-path",
        metavar="PATH",
        default="token",
        help="Dot-notation path to the token in the auth response (default: token)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the JSON file without sending any HTTP requests",
    )
    parser.add_argument(
        "--html",
        metavar="FILE",
        help="Write an HTML report to FILE  (e.g. report.html)",
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

    if args.auth_url:
        if not args.auth_payload:
            print("--auth-payload is required with --auth-url")
            sys.exit(1)
        token = _fetch_auth_token(args.auth_url, args.auth_payload, args.auth_token_path)
        global_headers["Authorization"] = f"Bearer {token}"

    with open(args.json_file) as f:
        cases = [TestCase.model_validate(tc) for tc in json.load(f)]

    if args.dry_run:
        print(f"{GREEN}✓ Dry run OK{RESET} — {len(cases)} test cases validated in {args.json_file}")
        sys.exit(0)

    sys.exit(run_tests(cases, args.base_url, global_headers=global_headers, html_path=args.html))
