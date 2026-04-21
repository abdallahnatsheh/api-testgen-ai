import json
from urllib.parse import urlparse

from pydantic import BaseModel, field_validator

VALID_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
VALID_CATEGORIES = {"functional", "negative", "edge_case", "validation"}

# Aliases AI models sometimes use
_CATEGORY_ALIASES = {
    "positive": "functional", "happy_path": "functional", "success": "functional",
    "error": "negative", "invalid": "negative", "failure": "negative",
    "boundary": "edge_case", "edge": "edge_case",
}


class TestInput(BaseModel):
    method: str
    endpoint: str
    payload: dict | None = None
    headers: dict = {}

    @field_validator("method", mode="before")
    @classmethod
    def normalize_method(cls, v):
        if isinstance(v, str):
            v = v.upper().strip()
            if v not in VALID_METHODS:
                raise ValueError(f"invalid HTTP method: {v!r}")
        return v

    @field_validator("endpoint", mode="before")
    @classmethod
    def normalize_endpoint(cls, v):
        if isinstance(v, str):
            v = v.strip()
            # AI sometimes returns a full URL — extract just the path
            if v.startswith("http"):
                v = urlparse(v).path or "/"
            if not v.startswith("/"):
                v = "/" + v
        return v

    @field_validator("payload", mode="before")
    @classmethod
    def coerce_payload(cls, v):
        if isinstance(v, list):
            return None
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, dict) else None
            except (json.JSONDecodeError, ValueError):
                return None
        return v


class ExpectedResult(BaseModel):
    status_code: int
    contains_key: str | None = None
    contains_value: dict | None = None  # e.g. {"key": "expected_value"}

    @field_validator("status_code")
    @classmethod
    def valid_status_code(cls, v):
        if not (100 <= v <= 599):
            raise ValueError(f"invalid HTTP status code: {v}")
        return v


class TestCase(BaseModel):
    name: str
    category: str          # functional | negative | edge_case | validation
    description: str
    input: TestInput
    expected_result: ExpectedResult

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, v):
        if isinstance(v, str):
            v = v.lower().strip()
            if v in VALID_CATEGORIES:
                return v
            return _CATEGORY_ALIASES.get(v, "functional")
        return v
