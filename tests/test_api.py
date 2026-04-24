import time

import jsonschema
import requests
from models import TestCase


def test_endpoint(test_case, base_url, global_headers):
    tc = TestCase.model_validate(test_case)

    path = tc.input.endpoint if tc.input.endpoint.startswith("/") else f"/{tc.input.endpoint}"
    url  = f"{base_url}{path}"
    merged_headers = {**global_headers, **tc.input.headers}

    t0 = time.monotonic()
    resp = requests.request(
        method=tc.input.method,
        url=url,
        json=tc.input.payload,
        headers=merged_headers,
        timeout=5,
    )
    elapsed_ms = (time.monotonic() - t0) * 1000

    assert resp.status_code == tc.expected_result.status_code, (
        f"Expected status {tc.expected_result.status_code}, got {resp.status_code}\n"
        f"Response: {resp.text[:300]}"
    )

    if tc.expected_result.contains_key or tc.expected_result.contains_value:
        body = resp.json()
        assert isinstance(body, dict), (
            f"Expected JSON object for key/value assertions, got {type(body).__name__}"
        )
        if tc.expected_result.contains_key:
            assert tc.expected_result.contains_key in body, (
                f"Key '{tc.expected_result.contains_key}' not found in response: {list(body.keys())}"
            )
        if tc.expected_result.contains_value:
            for k, expected in tc.expected_result.contains_value.items():
                assert body.get(k) == expected, (
                    f"Expected {k}={expected!r}, got {body.get(k)!r}"
                )

    if tc.expected_result.max_response_time_ms is not None:
        assert elapsed_ms <= tc.expected_result.max_response_time_ms, (
            f"Response took {elapsed_ms:.0f}ms, limit is {tc.expected_result.max_response_time_ms}ms"
        )

    if tc.expected_result.response_headers:
        for h_key, h_expected in tc.expected_result.response_headers.items():
            h_actual = resp.headers.get(h_key, "")
            assert h_expected.lower() in h_actual.lower(), (
                f"Header '{h_key}': expected {h_expected!r}, got {h_actual!r}"
            )

    if tc.expected_result.response_schema is not None:
        try:
            body = resp.json()
        except Exception:
            body = None
        try:
            jsonschema.validate(instance=body, schema=tc.expected_result.response_schema)
        except jsonschema.ValidationError as e:
            raise AssertionError(f"Response schema validation failed: {e.message}") from e
