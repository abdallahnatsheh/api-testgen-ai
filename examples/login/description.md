POST /login — authenticates a user and returns a signed JWT token.

## Request
- Method: POST
- Content-Type: application/json
- Body: `{ "email": string, "password": string }`
- Both fields are required. Extra fields in the body are silently ignored.

## Response codes and exact bodies

| Scenario                          | Status | Body                                                        |
|-----------------------------------|--------|-------------------------------------------------------------|
| Valid credentials                 | 200    | `{"token": "<JWT string>", "email": "<email>"}`             |
| Missing field (email or password) | 422    | `{"detail": [...]}` — FastAPI/Pydantic validation array     |
| Empty string (email or password)  | 400    | `{"detail": "Email and password are required"}`             |
| Email not registered              | 404    | `{"detail": "User not found"}`                              |
| Wrong password (email exists)     | 401    | `{"detail": "Invalid password"}`                            |
| Locked account (BUG)              | 200    | `{"detail": "Welcome!"}` — BUG: returns 200 instead of 403 |

## Valid credentials (copy exactly — no variations)
- `alice@example.com` / `alice123`
- `bob@example.com` / `bob123`
- `carol@example.com` / `carol123`

## Locked account (known bug)
- `locked@example.com` / `locked123`
- BUG: returns HTTP 200 with body `{"detail": "Welcome!"}` instead of 403
- The response does NOT contain a `token` key — it contains `detail`
- Test must assert: status_code=200, contains_key="detail"

## What the token looks like
The `token` field is a real JWT string (three base64 segments separated by dots).
- Use `contains_key: "token"` to assert the key exists on 200 responses
- Do NOT assert `contains_key: "token"` for the locked account — its body has `detail`, not `token`
- Do NOT hardcode the JWT token value in any assertion

## Strict matching rules
- Email and password matching is EXACT: case-sensitive and whitespace-sensitive
- `"ALICE@example.com"` → 404 (not found, not 401)
- `" alice@example.com "` (leading/trailing spaces) → 404
- `"Alice123"` as password → 401 (wrong password, email exists)
- The API does NOT trim, normalise, or lowercase any input
- The API does NOT validate email format — `"not_an_email"` is valid input, returns 404 if unknown
- The API does NOT enforce length limits

## What to test
Generate a balanced mix across all 4 categories:
- **functional** (3 tests): happy path for alice, bob, carol — each expects status 200 and `contains_key: "token"`
- **negative** (3 tests): wrong password → 401, unknown email → 404, locked account → 200 with `contains_key: "detail"` (NOT "token")
- **validation** (4 tests): missing `email` → 422, missing `password` → 422, empty string email → 400, empty string password → 400
- **edge_case** (2 tests): extra fields in payload → 200, uppercase email → 404

Do NOT generate tests that assume the API trims or normalises input.
