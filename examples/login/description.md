POST /login — authenticates a user and returns a JWT token.

## Request
- Method: POST
- Content-Type: application/json
- Body: `{ "email": string, "password": string }`
- Both fields are required. Extra fields in the body are silently ignored.

## Response codes and exact bodies

| Scenario                          | Status | Body                                                      |
|-----------------------------------|--------|-----------------------------------------------------------|
| Valid credentials                 | 200    | `{"token": "fake-jwt-token-xyz", "email": "<email>"}`     |
| Missing field (email or password) | 422    | `{"detail": [...]}` — FastAPI/Pydantic validation array   |
| Empty string (email or password)  | 400    | `{"detail": "Email and password are required"}`           |
| Email not registered              | 404    | `{"detail": "User not found"}`                            |
| Wrong password (email exists)     | 401    | `{"detail": "Invalid password"}`                          |
| Locked account                    | 403    | `{"detail": "Account is locked"}`                         |

## Valid credentials (copy exactly — no variations)
- `admin@example.com` / `admin123`
- `user@example.com` / `user123`

## Locked account
- `locked@example.com` / `locked123` → always returns 403 regardless of password

## Strict matching rules
- Email and password matching is EXACT: case-sensitive and whitespace-sensitive
- `"ADMIN@example.com"` → 404 (not found, not 401)
- `" admin@example.com "` (leading/trailing spaces) → 404
- `"Admin123"` as password → 401 (wrong password, email exists)
- The API does NOT trim, normalise, or lowercase any input
- The API does NOT validate email format — `"not_an_email"` is a valid string, just returns 404 if unknown
- The API does NOT enforce length limits

## What to test
Generate a balanced mix across all 4 categories:
- **functional**: happy path with each valid credential pair (expect 200 + `token` key)
- **negative**: wrong password (401), unknown email (404), locked account (403)
- **validation**: missing `email` field (422), missing `password` field (422), empty string email (400), empty string password (400)
- **edge_case**: extra fields in payload (200), non-email string as email (404), numeric-only email (404), whitespace-padded email (404), whitespace-padded password (401), uppercase email (404), uppercase password (401)

Do NOT generate tests that assume the API normalises or trims input.
