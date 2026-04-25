import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class OpenAPIRequest:
    name: str
    method: str
    path: str
    payload: dict | None
    headers: dict
    description: str | None = None


def _resolve_ref(ref: str, root: dict) -> dict:
    parts = ref.lstrip("#/").split("/")
    node = root
    for p in parts:
        node = node[p]
    return node


def _example_from_schema(schema: dict, root: dict, _depth: int = 0) -> dict | None:
    if _depth > 4:
        return {}
    if "$ref" in schema:
        schema = _resolve_ref(schema["$ref"], root)
    if "example" in schema:
        return schema["example"]
    if "properties" not in schema:
        return None
    result = {}
    required = set(schema.get("required", []))
    for prop, prop_schema in schema.get("properties", {}).items():
        if prop not in required and _depth > 0:
            continue
        if "$ref" in prop_schema:
            prop_schema = _resolve_ref(prop_schema["$ref"], root)
        t = prop_schema.get("type", "string")
        ex = prop_schema.get("example")
        if ex is not None:
            result[prop] = ex
        elif t == "string":
            result[prop] = prop_schema.get("default", f"example_{prop}")
        elif t == "integer":
            result[prop] = prop_schema.get("default", 1)
        elif t == "number":
            result[prop] = prop_schema.get("default", 1.0)
        elif t == "boolean":
            result[prop] = prop_schema.get("default", True)
        elif t == "array":
            result[prop] = []
        elif t == "object":
            result[prop] = _example_from_schema(prop_schema, root, _depth + 1) or {}
    return result or None


def _base_url_from_spec(spec: dict) -> str:
    # OpenAPI 3.x
    servers = spec.get("servers", [])
    if servers:
        url = servers[0].get("url", "")
        if url and not url.startswith("http"):
            url = "http://localhost" + url
        return url.rstrip("/")
    # Swagger 2.x
    host = spec.get("host", "localhost")
    base = spec.get("basePath", "/").rstrip("/")
    schemes = spec.get("schemes", ["http"])
    return f"{schemes[0]}://{host}{base}"


def load_spec(file_path: str) -> tuple[str, list[OpenAPIRequest]]:
    text = Path(file_path).read_text(encoding="utf-8")
    spec: dict = yaml.safe_load(text) if file_path.endswith((".yaml", ".yml")) else json.loads(text)

    base_url = _base_url_from_spec(spec)
    root = spec
    requests: list[OpenAPIRequest] = []

    for path, path_item in spec.get("paths", {}).items():
        # path-level parameters (shared across methods)
        path_params = path_item.get("parameters", [])

        for method in ("get", "post", "put", "patch", "delete"):
            op = path_item.get(method)
            if not op:
                continue

            name = op.get("summary") or op.get("operationId") or f"{method.upper()} {path}"
            description = op.get("description") or op.get("summary")

            # request body (OpenAPI 3.x)
            payload = None
            body = op.get("requestBody", {})
            if body:
                content = body.get("content", {})
                json_content = content.get("application/json", {})
                schema = json_content.get("schema", {})
                if schema:
                    payload = _example_from_schema(schema, root)

            # Swagger 2.x body parameter
            if payload is None:
                for param in list(path_params) + list(op.get("parameters", [])):
                    if param.get("in") == "body":
                        schema = param.get("schema", {})
                        payload = _example_from_schema(schema, root)
                        break

            requests.append(OpenAPIRequest(
                name=name,
                method=method.upper(),
                path=path,
                payload=payload,
                headers={},
                description=description,
            ))

    if not requests:
        raise ValueError(f"No operations found in {file_path}")
    return base_url, requests
