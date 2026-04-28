GET /me — returns the authenticated user's profile. Requires a valid JWT Bearer token.

## Request
- Method: GET
- No request body
- Required header: `Authorization: Bearer <token>`

## How auth works in this test run
- The tester is invoked with `--bearer <alice_token>` — Alice's JWT is injected globally into every test
- For happy-path (200) tests: use `headers: {}` — the global token is used automatically
- For 401 negative tests: override the header in `headers` with a bad/missing value to bypass the global token
- Because only Alice's token is injected globally, ALL happy-path tests will return Alice's profile — do NOT generate multiple functional tests expecting different users (Bob, Carol). Generate ONE functional test.

## Response codes and bodies

| Scenario                                    | Status | Body                                                     |
|---------------------------------------------|--------|----------------------------------------------------------|
| Valid unexpired token                        | 200    | `{"id": 1, "name": "Alice", "email": "alice@example.com", "role": "admin"}` |
| No Authorization header                     | 401    | `{"detail": "Missing or invalid Authorization header"}` |
| Header present but missing "Bearer " prefix | 401    | `{"detail": "Missing or invalid Authorization header"}` |
| Invalid / tampered / random token string    | 401    | `{"detail": "Invalid token"}`                            |

## Important: do NOT generate these test cases
- Do NOT test "valid token for unknown email → 404": the AI cannot mint a cryptographically signed JWT for an arbitrary email. Skip this case entirely.
- Do NOT generate multiple happy-path tests for Bob and Carol — they all use Alice's token and return Alice's profile, making them duplicates.

## What to test (exactly)
- **functional** (1 test): valid global token → 200, `contains_key: "id"`, `contains_key: "email"` optional
- **negative** (3 tests):
  - No Authorization header at all: set `headers: {"Authorization": ""}` → expect 401
  - Bad token string: set `headers: {"Authorization": "Bearer thisisnotavalidtoken"}` → expect 401
  - No "Bearer " prefix: set `headers: {"Authorization": "justaplainstring"}` → expect 401
- **validation** (2 tests):
  - Empty Bearer value: `headers: {"Authorization": "Bearer "}` → expect 401
  - Wrong scheme: `headers: {"Authorization": "Token somevalue"}` → expect 401
- **edge_case** (1 test): verify `role` field is present in 200 response — `contains_key: "role"`

## Field reference for 200 response
```json
{"id": 1, "name": "Alice", "email": "alice@example.com", "role": "admin"}
```
All four fields are always present. Use `contains_key` to assert individual fields.
