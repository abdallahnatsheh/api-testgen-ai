---
name: api-review
description: Review api.py for security issues, design problems, and correctness. Use before sharing or deploying the API.
allowed-tools:
  - Read
  - Grep
---

# API Review

Reviews `api.py` for security vulnerabilities, design issues, and correctness against project standards.

## When to Use

- Before sharing the project publicly
- After adding a new endpoint
- When onboarding someone to the codebase

## Review Checklist

### Security
- [ ] No hardcoded credentials beyond the demo `VALID_CREDENTIALS` dict
- [ ] No API keys or secrets in source code
- [ ] All error responses use `HTTPException` — no internal details leaked
- [ ] Locked accounts checked before password comparison (not after)
- [ ] No `# BUG:` markers present (intentional bugs removed)

### Design
- [ ] Every endpoint has a Pydantic model for the request body (POST/PUT)
- [ ] Error status codes follow REST conventions (404 = not found, 401 = bad creds, 403 = forbidden, 422 = schema error)
- [ ] Success responses return a consistent dict structure
- [ ] No `return (dict, status_code)` tuples — FastAPI ignores the status code in tuples

### Correctness
- [ ] `LOCKED_ACCOUNTS` check happens after user lookup (so unknown emails still get 404, not 403)
- [ ] Empty string inputs are caught explicitly (Pydantic passes empty strings — they need manual checks)
- [ ] `VALID_CREDENTIALS` and `LOCKED_ACCOUNTS` are in sync — locked users must exist in credentials

## Reporting Format

For each issue found:
1. **Severity**: High / Medium / Low
2. **Location**: file and line number
3. **Issue**: what is wrong
4. **Fix**: what to change
