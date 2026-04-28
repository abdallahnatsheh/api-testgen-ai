from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
import jwt
import datetime

app = FastAPI(title="AI API Test Assistant — Sample API")

SECRET_KEY = "dev-secret-key-for-local-testing-only-32b"
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 60


def _create_token(email: str, role: str) -> str:
    payload = {
        "sub": email,
        "role": role,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

USERS = [
    {"id": 1, "name": "Alice", "email": "alice@example.com", "role": "admin"},
    {"id": 2, "name": "Bob",   "email": "bob@example.com",   "role": "user"},
    {"id": 3, "name": "Carol", "email": "carol@example.com", "role": "user"},
]

VALID_CREDENTIALS = {
    "alice@example.com":  "alice123",
    "bob@example.com":    "bob123",
    "carol@example.com":  "carol123",
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


@app.get("/users/{user_id}")
def get_user(user_id: int):
    """Return a single user by ID."""
    user = next((u for u in USERS if u["id"] == user_id), None)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


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

    user = next((u for u in USERS if u["email"] == body.email), None)
    role = user["role"] if user else "user"
    token = _create_token(body.email, role)
    return {"token": token, "email": body.email}


@app.get("/me")
def get_me(authorization: str = Header(default=None)):
    """Return the current user's profile. Requires Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.removeprefix("Bearer ")
    payload = _decode_token(token)
    email = payload.get("sub")
    user = next((u for u in USERS if u["email"] == email), None)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
