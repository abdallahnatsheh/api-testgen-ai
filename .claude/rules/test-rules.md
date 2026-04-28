---
paths:
  - "examples/**/*.json"
  - "!settings.json"
---

# Test Case Rules

## Status codes
- Use `422` for missing or wrong-type fields — FastAPI/Pydantic validation always returns 422, not 400
- Use `400` only for empty string inputs caught by explicit app logic (e.g. `if not body.email`)
- Use `404` for unknown/unregistered resources (e.g. email not in the system)
- Use `401` for authentication failures (wrong password)
- Use `403` for authorization failures (account locked, forbidden) — **exception**: `locked@example.com` currently returns `200` due to the intentional demo bug; test cases for that account should expect `200`, not `403`
- Use `405` for wrong HTTP methods on an endpoint

## contains_key
- Set to `"detail"` for all error responses — FastAPI always returns `{"detail": "..."}` on errors
- Set to the primary success key for 200 responses (e.g. `"token"`, `"users"`, `"id"`)
- Set to `null` only when the response body is irrelevant to the assertion

## contains_value
- Use `contains_value` whenever you can assert a specific value — e.g. `{"count": 3}`, `{"detail": "User not found"}`
- Set to `null` for 200 responses where the value is dynamic (e.g. JWT tokens)
- Set to `null` for 422 responses — the detail array structure is complex and varies

## Structure rules
- `endpoint` must be path only — never include the base URL (e.g. `/login` not `http://localhost:8000/login`)
- `payload` must be `null` for GET/DELETE requests — not `{}`
- `headers` should be `{}` unless the test specifically requires a custom header
- Every test file must cover all 4 categories: `functional`, `negative`, `edge_case`, `validation`

## Category definitions
- `functional` — happy path, valid inputs, expected success
- `negative` — invalid credentials, wrong method, missing auth, resource not found
- `validation` — missing fields, empty strings, wrong types → 422/400
- `edge_case` — boundary conditions, extra fields, unusual but valid inputs, case sensitivity
