import json
import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def pytest_addoption(parser):
    parser.addoption("--test-file",        required=False, default=None, help="Path to JSON test cases file")
    parser.addoption("--base-url",         required=False, default=None, help="Base URL of the API  (e.g. https://api.example.com)")
    parser.addoption("--bearer",           default=None,   help="Bearer token — adds Authorization: Bearer <TOKEN>")
    parser.addoption("--header",           action="append", default=[], metavar="NAME=VALUE", help="Custom header (repeatable)")
    parser.addoption("--auth-url",         default=None,   help="POST to this URL before tests to obtain a Bearer token")
    parser.addoption("--auth-payload",     default=None,   help="JSON payload for the auth request")
    parser.addoption("--auth-token-path",  default="token", help="Dot-notation path to token in auth response (default: token)")


def pytest_generate_tests(metafunc):
    if "test_case" in metafunc.fixturenames:
        path = metafunc.config.getoption("--test-file")
        if not path:
            metafunc.parametrize("test_case", [])
            return
        with open(path) as f:
            cases = json.load(f)
        metafunc.parametrize("test_case", cases, ids=[c["name"] for c in cases])


@pytest.fixture(scope="session")
def base_url(request):
    return request.config.getoption("--base-url").rstrip("/")


@pytest.fixture(scope="session")
def global_headers(request):
    headers = {}
    bearer = request.config.getoption("--bearer")
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    for h in request.config.getoption("--header"):
        if "=" in h:
            name, _, value = h.partition("=")
            headers[name.strip()] = value.strip()
    auth_url = request.config.getoption("--auth-url")
    if auth_url:
        auth_payload = request.config.getoption("--auth-payload")
        if not auth_payload:
            pytest.exit("--auth-payload is required with --auth-url", returncode=1)
        token_path = request.config.getoption("--auth-token-path")
        from tester import _fetch_auth_token
        token = _fetch_auth_token(auth_url, auth_payload, token_path)
        headers["Authorization"] = f"Bearer {token}"
    return headers
