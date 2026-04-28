---
name: add-bug
description: Introduce an intentional bug into api.py for demonstration or testing purposes. Use when showing how the tester detects regressions.
allowed-tools:
  - Read
  - Edit
---

# Add Bug

Introduces a labelled intentional bug into `api.py` so the test suite can demonstrate detection.

## When to Use

- Demonstrating how the tester catches regressions
- Teaching what a specific category of bug looks like
- Setting up a failing test scenario

## Available Bugs

### `auth` — Flipped password check
Correct passwords get rejected, wrong passwords are accepted (auth bypass).

```python
# BEFORE (correct)
if body.password != expected_password:
    raise HTTPException(status_code=401, detail="Invalid password")

# AFTER (bug)
if body.password == expected_password:  # BUG: condition flipped — auth bypass
    raise HTTPException(status_code=401, detail="Invalid password")
```

**Caught by:** any functional login test (e.g. "Valid login — alice", "Valid login — bob") and "Wrong password returns 401"

---

### `locked` — Locked account returns 200
Locked accounts are silently let through instead of being blocked with 403.

> **Note:** This bug is already present in the codebase (it ships as the intentional demo bug). Use `/fix-bug` to restore 403 first, then re-introduce with this skill if needed.

```python
# BEFORE (correct — after fix-bug restores it)
if body.email in LOCKED_ACCOUNTS:
    raise HTTPException(status_code=403, detail="Account is locked")

# AFTER (bug)
if body.email in LOCKED_ACCOUNTS:
    raise HTTPException(status_code=200, detail="Welcome!")  # BUG: locked account returns 200
```

**Caught by:** any test asserting `locked@example.com` → 403

## Steps

1. If no bug type given, ask: `auth` or `locked`?
2. Read `api.py` to find the target line.
3. Apply the edit and add the `# BUG:` comment.
4. Remind the user to restart `api.py` for the change to take effect.
5. Tell the user which test cases will now fail.

## Rule

Always mark bugs with `# BUG:` so they are easy to find and the `fix-bug` skill can remove them.
