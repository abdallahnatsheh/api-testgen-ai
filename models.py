import json

from pydantic import BaseModel, field_validator


class TestInput(BaseModel):
    method: str
    endpoint: str
    payload: dict | None = None
    headers: dict = {}

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


class TestCase(BaseModel):
    name: str
    category: str          # functional | negative | edge_case | validation
    description: str
    input: TestInput
    expected_result: ExpectedResult
