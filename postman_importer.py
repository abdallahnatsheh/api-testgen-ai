import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse, urlencode


@dataclass
class PostmanRequest:
    name: str
    method: str
    path: str
    payload: dict | None
    headers: dict


def _extract_items(items: list) -> list[PostmanRequest]:
    requests = []
    for item in items:
        if "item" in item:
            requests.extend(_extract_items(item["item"]))
        elif "request" in item:
            req = item["request"]
            method = req.get("method", "GET").upper()

            url_obj = req.get("url", {})
            if isinstance(url_obj, str):
                parsed = urlparse(url_obj)
                path = parsed.path or "/"
            else:
                path_parts = url_obj.get("path", [])
                path = "/" + "/".join(path_parts) if path_parts else "/"
                query = url_obj.get("query", [])
                if query:
                    qs = urlencode({q["key"]: q.get("value", "") for q in query if not q.get("disabled")})
                    path = f"{path}?{qs}"

            payload = None
            body = req.get("body", {})
            if body and body.get("mode") == "raw":
                raw = body.get("raw", "").strip()
                if raw:
                    try:
                        payload = json.loads(raw)
                    except json.JSONDecodeError:
                        pass

            headers = {}
            for h in req.get("header", []):
                if not h.get("disabled") and h.get("key", "").lower() != "content-type":
                    headers[h["key"]] = h["value"]

            requests.append(PostmanRequest(
                name=item.get("name", path),
                method=method,
                path=path,
                payload=payload,
                headers=headers,
            ))
    return requests


def load_collection(file_path: str) -> list[PostmanRequest]:
    data = json.loads(Path(file_path).read_text())
    items = data.get("item", [])
    requests = _extract_items(items)
    if not requests:
        raise ValueError(f"No requests found in {file_path}")
    return requests
