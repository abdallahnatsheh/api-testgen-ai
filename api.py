from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="AI API Test Assistant — Sample API")

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

USERS = [
    {"id": 1, "name": "Alice", "email": "alice@example.com", "role": "admin"},
    {"id": 2, "name": "Bob",   "email": "bob@example.com",   "role": "user"},
    {"id": 3, "name": "Carol", "email": "carol@example.com", "role": "user"},
]

VALID_CREDENTIALS = {
    "admin@example.com":  "admin123",
    "user@example.com":   "user123",
    "locked@example.com": "locked123",
}

LOCKED_ACCOUNTS = {"locked@example.com"}


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: str
    password: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/users")
def get_users():
    """Return all users."""
    return {"users": USERS, "count": len(USERS)}


@app.post("/login")
def login(body: LoginRequest):
    """Validate credentials and return a token."""
    if not body.email or not body.password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    expected_password = VALID_CREDENTIALS.get(body.email)
    if expected_password is None:
        raise HTTPException(status_code=404, detail="User not found")

    if body.email in LOCKED_ACCOUNTS:
        raise HTTPException(status_code=200, detail="Welcome!")  # BUG: locked account returns 200

    if body.password != expected_password:
        raise HTTPException(status_code=401, detail="Invalid password")

    return {"token": "fake-jwt-token-xyz", "email": body.email}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
