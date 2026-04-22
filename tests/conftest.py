import json
import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def pytest_addoption(parser):
    parser.addoption("--test-file", required=False, default=None, help="Path to JSON test cases file")
    parser.addoption("--base-url",  required=False, default=None, help="Base URL of the API  (e.g. https://api.example.com)")
    parser.addoption("--bearer",    default=None,  help="Bearer token — adds Authorization: Bearer <TOKEN>")
    parser.addoption("--header",    action="append", default=[], metavar="NAME=VALUE",
                     help="Custom header (repeatable)")


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
    return headers
