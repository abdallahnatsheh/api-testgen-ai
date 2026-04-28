---
paths:
  - "api.py"
---

# API Rules

- Always use `raise HTTPException(status_code=..., detail=...)` for errors — never `return (dict, status_code)`
- Check `LOCKED_ACCOUNTS` after the user lookup, not before — unknown emails must still return 404
- Empty string inputs must be caught manually — Pydantic accepts empty strings and passes them through
- Mark intentional bugs with `# BUG:` inline comment — never leave silent broken logic
- Keep `LOCKED_ACCOUNTS` in sync with `VALID_CREDENTIALS` — every locked email must have a password entry
- Never leak internal error details in HTTPException messages — keep them user-facing and generic
- `GET /me` requires `Authorization: Bearer <token>` — missing or non-Bearer header → 401 "Missing or invalid Authorization header"; invalid/expired JWT → 401 "Invalid token"
- `locked@example.com` currently returns 200 with `{"detail":"Welcome!"}` — this is the intentional demo bug marked with `# BUG:`
