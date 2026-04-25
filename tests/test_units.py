"""Unit and sanity tests for models, tester, postman_importer, and main CLI args."""
import json
import sys
import types
import pytest
from unittest.mock import patch, MagicMock

from models import TestCase, TestInput, ExpectedResult
from postman_importer import load_collection, PostmanRequest
from tester import _build_url, _truncate, _pretty_json


# ---------------------------------------------------------------------------
# models.py
# ---------------------------------------------------------------------------

class TestModels:
    def test_valid_testcase(self):
        tc = TestCase.model_validate({
            "name": "test",
            "category": "functional",
            "description": "desc",
            "input": {"method": "GET", "endpoint": "/users", "payload": None, "headers": {}},
            "expected_result": {"status_code": 200}
        })
        assert tc.input.method == "GET"
        assert tc.expected_result.status_code == 200

    def test_method_normalized_to_uppercase(self):
        tc = TestCase.model_validate({
            "name": "t", "category": "functional", "description": "d",
            "input": {"method": "post", "endpoint": "/login", "payload": None, "headers": {}},
            "expected_result": {"status_code": 200}
        })
        assert tc.input.method == "POST"

    def test_endpoint_gets_leading_slash(self):
        tc = TestCase.model_validate({
            "name": "t", "category": "functional", "description": "d",
            "input": {"method": "GET", "endpoint": "users", "payload": None, "headers": {}},
            "expected_result": {"status_code": 200}
        })
        assert tc.input.endpoint == "/users"

    def test_full_url_stripped_to_path(self):
        tc = TestCase.model_validate({
            "name": "t", "category": "functional", "description": "d",
            "input": {"method": "GET", "endpoint": "http://localhost:8000/users", "payload": None, "headers": {}},
            "expected_result": {"status_code": 200}
        })
        assert tc.input.endpoint == "/users"

    def test_category_alias_positive_maps_to_functional(self):
        tc = TestCase.model_validate({
            "name": "t", "category": "positive", "description": "d",
            "input": {"method": "GET", "endpoint": "/users", "payload": None, "headers": {}},
            "expected_result": {"status_code": 200}
        })
        assert tc.category == "functional"

    def test_invalid_status_code_raises(self):
        with pytest.raises(Exception):
            TestCase.model_validate({
                "name": "t", "category": "functional", "description": "d",
                "input": {"method": "GET", "endpoint": "/users", "payload": None, "headers": {}},
                "expected_result": {"status_code": 99}
            })

    def test_invalid_method_raises(self):
        with pytest.raises(Exception):
            TestCase.model_validate({
                "name": "t", "category": "functional", "description": "d",
                "input": {"method": "INVALID", "endpoint": "/users", "payload": None, "headers": {}},
                "expected_result": {"status_code": 200}
            })

    def test_payload_string_coerced_to_dict(self):
        tc = TestCase.model_validate({
            "name": "t", "category": "functional", "description": "d",
            "input": {"method": "POST", "endpoint": "/login",
                      "payload": '{"email": "a@b.com"}', "headers": {}},
            "expected_result": {"status_code": 200}
        })
        assert isinstance(tc.input.payload, dict)
        assert tc.input.payload["email"] == "a@b.com"

    # --- ExpectedResult new fields ---

    def test_contains_value_string_coerced_to_none(self):
        """AI sometimes returns a string instead of a dict for contains_value."""
        tc = TestCase.model_validate({
            "name": "t", "category": "negative", "description": "d",
            "input": {"method": "POST", "endpoint": "/login", "payload": None, "headers": {}},
            "expected_result": {"status_code": 401, "contains_value": "Invalid password"}
        })
        assert tc.expected_result.contains_value is None

    def test_contains_value_list_coerced_to_none(self):
        tc = TestCase.model_validate({
            "name": "t", "category": "negative", "description": "d",
            "input": {"method": "GET", "endpoint": "/users", "payload": None, "headers": {}},
            "expected_result": {"status_code": 200, "contains_value": ["item1", "item2"]}
        })
        assert tc.expected_result.contains_value is None

    def test_contains_value_dict_kept(self):
        tc = TestCase.model_validate({
            "name": "t", "category": "functional", "description": "d",
            "input": {"method": "GET", "endpoint": "/users", "payload": None, "headers": {}},
            "expected_result": {"status_code": 200, "contains_value": {"role": "admin"}}
        })
        assert tc.expected_result.contains_value == {"role": "admin"}

    def test_response_headers_string_coerced_to_none(self):
        tc = TestCase.model_validate({
            "name": "t", "category": "functional", "description": "d",
            "input": {"method": "GET", "endpoint": "/users", "payload": None, "headers": {}},
            "expected_result": {"status_code": 200, "response_headers": "application/json"}
        })
        assert tc.expected_result.response_headers is None

    def test_response_headers_dict_kept(self):
        tc = TestCase.model_validate({
            "name": "t", "category": "functional", "description": "d",
            "input": {"method": "GET", "endpoint": "/users", "payload": None, "headers": {}},
            "expected_result": {"status_code": 200, "response_headers": {"Content-Type": "application/json"}}
        })
        assert tc.expected_result.response_headers == {"Content-Type": "application/json"}

    def test_response_schema_bool_coerced_to_none(self):
        tc = TestCase.model_validate({
            "name": "t", "category": "functional", "description": "d",
            "input": {"method": "GET", "endpoint": "/users", "payload": None, "headers": {}},
            "expected_result": {"status_code": 200, "response_schema": True}
        })
        assert tc.expected_result.response_schema is None

    def test_response_schema_dict_kept(self):
        schema = {"type": "object", "properties": {"id": {"type": "integer"}}}
        tc = TestCase.model_validate({
            "name": "t", "category": "functional", "description": "d",
            "input": {"method": "GET", "endpoint": "/users/1", "payload": None, "headers": {}},
            "expected_result": {"status_code": 200, "response_schema": schema}
        })
        assert tc.expected_result.response_schema == schema

    def test_max_response_time_float_coerced_to_int(self):
        tc = TestCase.model_validate({
            "name": "t", "category": "functional", "description": "d",
            "input": {"method": "GET", "endpoint": "/users", "payload": None, "headers": {}},
            "expected_result": {"status_code": 200, "max_response_time_ms": 2000.0}
        })
        assert tc.expected_result.max_response_time_ms == 2000
        assert isinstance(tc.expected_result.max_response_time_ms, int)

    def test_max_response_time_string_digit_coerced_to_int(self):
        tc = TestCase.model_validate({
            "name": "t", "category": "functional", "description": "d",
            "input": {"method": "GET", "endpoint": "/users", "payload": None, "headers": {}},
            "expected_result": {"status_code": 200, "max_response_time_ms": "3000"}
        })
        assert tc.expected_result.max_response_time_ms == 3000


# ---------------------------------------------------------------------------
# tester.py helpers
# ---------------------------------------------------------------------------

class TestTesterHelpers:
    def test_build_url_with_leading_slash(self):
        assert _build_url("http://localhost:8000", "/login") == "http://localhost:8000/login"

    def test_build_url_without_leading_slash(self):
        assert _build_url("http://localhost:8000", "login") == "http://localhost:8000/login"

    def test_build_url_strips_trailing_slash_from_base(self):
        assert _build_url("http://localhost:8000/", "/login") == "http://localhost:8000/login"

    def test_truncate_short_string(self):
        assert _truncate("hello", 10) == "hello"

    def test_truncate_long_string(self):
        result = _truncate("a" * 200, 120)
        assert len(result) == 121  # 120 + ellipsis char
        assert result.endswith("…")

    def test_pretty_json_dict(self):
        result = _pretty_json({"key": "value"})
        assert "key" in result
        assert "value" in result

    def test_pretty_json_non_serializable_falls_back(self):
        result = _pretty_json(object())
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# postman_importer.py
# ---------------------------------------------------------------------------

class TestPostmanImporter:
    def test_load_sample_collection(self):
        reqs = load_collection("examples/postman/api-testgen-sample.postman_collection.json")
        assert len(reqs) == 5
        methods = [r.method for r in reqs]
        assert "POST" in methods
        assert "GET" in methods

    def test_request_paths_have_leading_slash(self):
        reqs = load_collection("examples/postman/api-testgen-sample.postman_collection.json")
        for r in reqs:
            assert r.path.startswith("/")

    def test_payload_parsed_as_dict(self):
        reqs = load_collection("examples/postman/api-testgen-sample.postman_collection.json")
        post_reqs = [r for r in reqs if r.method == "POST" and r.payload]
        assert len(post_reqs) > 0
        assert isinstance(post_reqs[0].payload, dict)

    def test_query_params_included_in_path(self):
        reqs = load_collection("examples/postman/api-testgen-sample.postman_collection.json")
        paths = [r.path for r in reqs]
        assert any("limit" in p for p in paths)

    def test_empty_collection_raises(self, tmp_path):
        f = tmp_path / "empty.json"
        f.write_text(json.dumps({"info": {"name": "test"}, "item": []}))
        with pytest.raises(ValueError, match="No requests found"):
            load_collection(str(f))

    def test_nested_folders_are_flattened(self, tmp_path):
        collection = {
            "info": {"name": "test"},
            "item": [{
                "name": "folder",
                "item": [{
                    "name": "nested request",
                    "request": {
                        "method": "GET",
                        "header": [],
                        "url": {"raw": "http://localhost/health", "host": ["localhost"], "path": ["health"]}
                    }
                }]
            }]
        }
        f = tmp_path / "nested.json"
        f.write_text(json.dumps(collection))
        reqs = load_collection(str(f))
        assert len(reqs) == 1
        assert reqs[0].path == "/health"


# ---------------------------------------------------------------------------
# main.py — CLI arg parsing
# ---------------------------------------------------------------------------

class TestCLIArgs:
    def _parse(self, argv):
        with patch("sys.argv", ["main.py"] + argv):
            import main
            return main._parse_args()

    def test_url_arg(self):
        args = self._parse(["--url", "http://localhost:8000/login"])
        assert args.url == "http://localhost:8000/login"

    def test_postman_arg(self):
        args = self._parse(["--postman", "collection.json", "--base-url", "http://localhost:8000"])
        assert args.postman == "collection.json"
        assert args.base_url == "http://localhost:8000"

    def test_url_and_postman_mutually_exclusive(self):
        with pytest.raises(SystemExit):
            self._parse(["--url", "http://x.com/a", "--postman", "file.json"])

    def test_count_parsed_as_int(self):
        args = self._parse(["--url", "http://localhost/x", "--count", "5"])
        assert args.count == 5

    def test_run_flag(self):
        args = self._parse(["--url", "http://localhost/x", "--run"])
        assert args.run is True

    def test_bearer_arg(self):
        args = self._parse(["--url", "http://localhost/x", "--bearer", "mytoken"])
        assert args.bearer == "mytoken"

    def test_build_auth_headers_bearer(self):
        import main
        args = MagicMock()
        args.bearer = "tok123"
        args.headers = None
        result = main._build_auth_headers(args)
        assert result == {"Authorization": "Bearer tok123"}

    def test_build_auth_headers_custom(self):
        import main
        args = MagicMock()
        args.bearer = None
        args.headers = ["X-API-Key=abc"]
        result = main._build_auth_headers(args)
        assert result == {"X-API-Key": "abc"}

    def test_build_auth_headers_invalid_format_exits(self):
        import main
        args = MagicMock()
        args.bearer = None
        args.headers = ["BADFORMAT"]
        with pytest.raises(SystemExit):
            main._build_auth_headers(args)
