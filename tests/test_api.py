import requests
from models import TestCase


def test_endpoint(test_case, base_url, global_headers):
    tc = TestCase.model_validate(test_case)

    path = tc.input.endpoint if tc.input.endpoint.startswith("/") else f"/{tc.input.endpoint}"
    url  = f"{base_url}{path}"
    merged_headers = {**global_headers, **tc.input.headers}

    resp = requests.request(
        method=tc.input.method,
        url=url,
        json=tc.input.payload,
        headers=merged_headers,
        timeout=5,
    )

    assert resp.status_code == tc.expected_result.status_code, (
        f"Expected status {tc.expected_result.status_code}, got {resp.status_code}\n"
        f"Response: {resp.text[:300]}"
    )

    if tc.expected_result.contains_key:
        body = resp.json()
        assert isinstance(body, dict), (
            f"Expected JSON object to check key '{tc.expected_result.contains_key}', "
            f"got {type(body).__name__}"
        )
        assert tc.expected_result.contains_key in body, (
            f"Key '{tc.expected_result.contains_key}' not found in response: {list(body.keys())}"
        )
