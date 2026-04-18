---
name: run-tests
description: Run the tester against a JSON test case file and a live API server. Use when executing test suites, checking pass/fail results, or validating API behaviour after a change.
allowed-tools:
  - Bash
  - Read
  - Glob
---

# Run Tests

Executes a JSON test case file against a live API server and reports results.

## When to Use

- After making any change to `api.py` — verify nothing broke
- After generating new test cases — validate them against the live server
- After introducing or fixing a bug — confirm the tester catches or clears it
- Against a real external API with auth headers

## Steps — Local Sample API

1. Check if the API server is running on port 8000:
```bash
curl -s http://localhost:8000/users > /dev/null && echo "running" || echo "not running"
```

2. If not running, start it in the background:
```bash
python3 api.py &
sleep 2
```

3. Run the tester:
```bash
python3 tester.py <json_file> http://localhost:8000
```

## Steps — Real External API

No auth:
```bash
python3 tester.py <json_file> https://api.example.com
```

With Bearer token:
```bash
python3 tester.py <json_file> https://api.example.com --bearer eyJ0eXAiOiJKV1Q...
```

With API key header:
```bash
python3 tester.py <json_file> https://api.example.com --header "X-API-Key=abc123"
```

Multiple headers (repeatable):
```bash
python3 tester.py <json_file> https://api.example.com --bearer <token> --header "X-Tenant=acme"
```

## Reporting

- Report the final summary line (N passed, N failed)
- Flag any unexpected failures — a failure is unexpected if it is NOT caused by a known intentional `# BUG:` in `api.py`
- For real APIs, all failures are unexpected unless the user has explained known issues

## Known test files

| File | Endpoint | Notes |
|------|----------|-------|
| `test_cases.json` | `/login` | Focused set including bug scenarios |
| `GM_TEST_CASE.json` | `/login` | Gemini-generated, 12 cases, includes locked account |
