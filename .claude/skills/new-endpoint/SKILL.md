---
name: new-endpoint
description: Add a new endpoint to the sample API server and generate matching test cases. Use when expanding the API with new routes.
allowed-tools:
  - Read
  - Edit
  - Write
  - Bash
---

# New Endpoint

Scaffolds a new endpoint in `api.py` and writes a matching JSON test case file.

## When to Use

- Expanding the sample API with new functionality
- Demonstrating the tool against a different endpoint type
- Testing a new category of API behaviour (e.g. PUT, DELETE)

## Steps

1. Ask the user for:
   - HTTP method (`GET` / `POST` / `PUT` / `DELETE`)
   - Path (e.g. `/register`, `/users/{id}`)
   - What it should do (brief description)
   - Any request fields needed

2. Implement the endpoint in `api.py` following these patterns:
   - Pydantic `BaseModel` for request body (POST/PUT)
   - `raise HTTPException(...)` for all error responses — never `return (dict, status)`
   - Return a plain dict for success responses

3. Write test cases to `<endpoint_name>_tests.json` covering all 4 categories:

   | Category | What to test |
   |----------|-------------|
   | `functional` | Happy path — valid input, expect 200 + key check |
   | `negative` | Wrong values — expect 401/403/404 |
   | `edge_case` | Empty strings, extra fields, boundary values |
   | `validation` | Missing fields, wrong types — expect **422** (FastAPI Pydantic) |

4. Update the endpoint table in `README.md`.

5. Tell the user to restart `api.py` then run:
```bash
python3 tester.py <endpoint_name>_tests.json http://localhost:8000
```

## FastAPI Status Code Reference

| Situation | Status |
|-----------|--------|
| Missing/wrong-type fields (Pydantic) | `422` |
| Empty string caught by app logic | `400` |
| Not found | `404` |
| Wrong credentials | `401` |
| Forbidden / locked | `403` |
| Success | `200` |
