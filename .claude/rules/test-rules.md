---
paths:
  - "*.json"
  - "!settings.json"
---

# Test Case Rules

- Use `422` for missing or wrong-type fields — FastAPI Pydantic validation always returns 422, not 400
- Use `400` only for empty string inputs that are caught by explicit app logic (`if not body.email`)
- Set `contains_key` to `"detail"` for all error responses (FastAPI error format)
- Set `contains_key` to the primary success key (e.g. `"token"`, `"users"`) for 200 responses
- Set `contains_key` to `null` only when the response body doesn't matter for the assertion
- `endpoint` must be path only — never include the base URL (e.g. `/login` not `http://localhost:8000/login`)
- Every file must cover all 4 categories: functional, negative, edge_case, validation
