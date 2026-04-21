GET /users — returns the full list of registered users.

## Request
- Method: GET
- No request body
- No authentication required
- Query parameters are not supported and will be silently ignored

## Response codes and exact bodies

| Scenario          | Status | Body                                              |
|-------------------|--------|---------------------------------------------------|
| Success           | 200    | `{"users": [...], "count": 3}`                    |
| Wrong HTTP method | 405    | `{"detail": "Method Not Allowed"}`                |

## Response body structure
- `users`: array of exactly 3 user objects (fixed dataset — never changes)
- `count`: integer, always `3`

Each user object:
```json
{ "id": int, "name": str, "email": str, "role": "admin" | "user" }
```

## Fixed dataset (always returned, in this order)
| id | name  | email               | role  |
|----|-------|---------------------|-------|
| 1  | Alice | alice@example.com   | admin |
| 2  | Bob   | bob@example.com     | user  |
| 3  | Carol | carol@example.com   | user  |

## Strict rules
- The dataset is static — always exactly 3 users, `count` is always `3`
- No filtering, search, or pagination — all query params are ignored
- Wrong HTTP methods (POST, PUT, DELETE, PATCH) → 405
- No auth required — any GET request to `/users` returns 200

## What to test
Generate a balanced mix across all 4 categories:
- **functional**: GET returns 200 with `users` and `count` keys; assert `{"count": 3}`
- **negative**: POST → 405, DELETE → 405, PUT → 405
- **validation**: response body always contains both `users` and `count` keys; `count` equals 3
- **edge_case**: request with query params still returns 200 with all 3 users; request with custom/unknown headers still returns 200
