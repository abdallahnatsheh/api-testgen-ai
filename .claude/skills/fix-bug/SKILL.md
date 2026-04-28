---
name: fix-bug
description: Remove all intentional bugs from api.py and restore correct behaviour. Use after a bug demonstration is complete.
allowed-tools:
  - Read
  - Edit
  - Grep
---

# Fix Bug

Finds and removes all intentional `# BUG:` markers from `api.py`, restoring correct logic.

## When to Use

- After a bug demonstration is complete
- Before running a clean test suite to verify all tests pass
- Before committing or pushing code

## Steps

1. Search for all bug markers:
```bash
grep -n "# BUG:" api.py
```

2. For each marked line, apply the correct fix:

| Bug | Broken line | Correct line |
|-----|-------------|--------------|
| `auth` | `if body.password == expected_password:` | `if body.password != expected_password:` |
| `locked` | `raise HTTPException(status_code=200, detail="Welcome!")` | `raise HTTPException(status_code=403, detail="Account is locked")` |

> **Note on `locked`:** The `locked` bug ships in the codebase intentionally as a regression demo. Fixing it changes `locked@example.com` from 200 → 403, which will cause the existing example test cases (which expect 200) to fail. Only fix it when the user explicitly wants a clean all-pass run.

3. Confirm all `# BUG:` comments are removed.
4. Remind the user to restart `api.py`.
5. Suggest running the tester to confirm everything passes.
