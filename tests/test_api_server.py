"""Tests for api.py — covers /login, /users, /users/{id}, and /me."""
import sys
import os
import datetime
import pytest
import jwt
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from api import app, SECRET_KEY, ALGORITHM

client = TestClient(app)


def _login(email, password):
    return client.post("/login", json={"email": email, "password": password})


def _valid_token(email="alice@example.com", role="admin"):
    payload = {
        "sub": email,
        "role": role,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=60),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ---------------------------------------------------------------------------
# POST /login
# ---------------------------------------------------------------------------

class TestLogin:
    def test_valid_alice(self):
        r = _login("alice@example.com", "alice123")
        assert r.status_code == 200
        body = r.json()
        assert "token" in body
        assert body["email"] == "alice@example.com"

    def test_valid_bob(self):
        r = _login("bob@example.com", "bob123")
        assert r.status_code == 200
        assert "token" in r.json()

    def test_valid_carol(self):
        r = _login("carol@example.com", "carol123")
        assert r.status_code == 200
        assert "token" in r.json()

    def test_token_is_valid_jwt(self):
        r = _login("alice@example.com", "alice123")
        token = r.json()["token"]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "alice@example.com"
        assert "role" in payload
        assert "exp" in payload

    def test_wrong_password_returns_401(self):
        r = _login("alice@example.com", "wrongpassword")
        assert r.status_code == 401

    def test_unknown_email_returns_404(self):
        r = _login("nobody@example.com", "whatever")
        assert r.status_code == 404

    def test_empty_email_returns_400(self):
        r = _login("", "alice123")
        assert r.status_code == 400

    def test_empty_password_returns_400(self):
        r = _login("alice@example.com", "")
        assert r.status_code == 400

    def test_missing_fields_returns_422(self):
        r = client.post("/login", json={"email": "alice@example.com"})
        assert r.status_code == 422

    def test_locked_account_bug(self):
        # BUG: locked@example.com currently returns 200 instead of 403
        r = _login("locked@example.com", "locked123")
        assert r.status_code == 200  # documents the known bug


# ---------------------------------------------------------------------------
# GET /users
# ---------------------------------------------------------------------------

class TestGetUsers:
    def test_returns_200(self):
        r = client.get("/users")
        assert r.status_code == 200

    def test_returns_users_list(self):
        body = client.get("/users").json()
        assert "users" in body
        assert isinstance(body["users"], list)
        assert len(body["users"]) == 3

    def test_returns_count(self):
        body = client.get("/users").json()
        assert body["count"] == 3

    def test_user_fields_present(self):
        users = client.get("/users").json()["users"]
        for u in users:
            assert "id" in u
            assert "name" in u
            assert "email" in u
            assert "role" in u

    def test_no_auth_required(self):
        r = client.get("/users")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# GET /users/{user_id}
# ---------------------------------------------------------------------------

class TestGetUserById:
    def test_user_1_returns_alice(self):
        r = client.get("/users/1")
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "Alice"
        assert body["email"] == "alice@example.com"
        assert body["role"] == "admin"

    def test_user_2_returns_bob(self):
        r = client.get("/users/2")
        assert r.status_code == 200
        assert r.json()["name"] == "Bob"

    def test_user_3_returns_carol(self):
        r = client.get("/users/3")
        assert r.status_code == 200
        assert r.json()["name"] == "Carol"

    def test_missing_user_returns_404(self):
        r = client.get("/users/999")
        assert r.status_code == 404

    def test_invalid_id_type_returns_422(self):
        r = client.get("/users/abc")
        assert r.status_code == 422

    def test_zero_id_returns_404(self):
        r = client.get("/users/0")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------

class TestGetMe:
    def test_valid_token_returns_user(self):
        token = _valid_token("alice@example.com")
        r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == "alice@example.com"
        assert body["name"] == "Alice"

    def test_token_from_login_works(self):
        token = _login("bob@example.com", "bob123").json()["token"]
        r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["name"] == "Bob"

    def test_no_auth_header_returns_401(self):
        r = client.get("/me")
        assert r.status_code == 401

    def test_invalid_token_returns_401(self):
        r = client.get("/me", headers={"Authorization": "Bearer notavalidtoken"})
        assert r.status_code == 401

    def test_malformed_header_no_bearer_prefix_returns_401(self):
        token = _valid_token()
        r = client.get("/me", headers={"Authorization": token})
        assert r.status_code == 401

    def test_expired_token_returns_401(self):
        payload = {
            "sub": "alice@example.com",
            "role": "admin",
            "exp": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1),
        }
        expired_token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        r = client.get("/me", headers={"Authorization": f"Bearer {expired_token}"})
        assert r.status_code == 401

    def test_token_with_unknown_email_returns_404(self):
        token = _valid_token("ghost@example.com")
        r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 404

    def test_response_includes_role(self):
        token = _valid_token("alice@example.com")
        r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert "role" in r.json()
