GET /users/{user_id} — returns a single user object by integer ID.

Response (200):
  { "id": 1, "name": "Alice", "email": "alice@example.com", "role": "admin" }

Errors:
  404 — user ID not found ("User not found")
  422 — non-integer ID (FastAPI path param validation)

Known user IDs: 1 (Alice, admin), 2 (Bob, user), 3 (Carol, user).
Valid roles are "admin" and "user" only.
