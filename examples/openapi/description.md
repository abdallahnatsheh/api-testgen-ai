# API Testgen Sample API

Sample FastAPI server with 3 endpoints. Base URL: http://localhost:8000

## GET /users
Returns all users. Always 200.
Response: { "users": [ {id, name, email, role} ], "count": 3 }
Always returns exactly 3 users. No auth required.

## GET /users/{user_id}
Returns a single user by numeric ID.
- 200: valid ID (1, 2, or 3) → { id, name, email, role }
- 404: ID not found → { "detail": "User not found" }
- 422: non-numeric user_id (FastAPI validation error)

## POST /login
Request body: { "email": string, "password": string }

Responses:
- 200: valid credentials → { "token": "fake-jwt-token-xyz", "email": "..." }
- 400: empty email or password string → { "detail": "Email and password are required" }
- 401: wrong password → { "detail": "Invalid password" }
- 404: email not in system → { "detail": "User not found" }
- 422: missing email or password field entirely (FastAPI validation)
- KNOWN BUG: locked@example.com returns 200 (not 403) — test should expect 200

Valid credentials:
- admin@example.com / admin123
- user@example.com / user123

Invalid email (not in system): alice@example.com, bob@example.com → 404
Locked account: locked@example.com / locked123 → returns 200 (bug, should be 403)

IMPORTANT:
- Missing field → 422 (not 400)
- Empty string field → 400 (not 422)
- Wrong password for valid email → 401
- Unknown email → 404
