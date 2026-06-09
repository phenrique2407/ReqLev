"""
ReqLev – Tests: Authentication

Covers:
  - User registration (success, duplicate email, duplicate username, weak password)
  - User login (success, wrong password, unknown email)
  - Token persistence (me endpoint)
  - Input validation (missing fields, invalid email)
"""

import pytest
from .conftest import create_user_via_api, auth_headers


# ── Registration ──────────────────────────────────────────────────────────────

class TestRegister:
    def test_register_success(self, client):
        r = client.post("/api/auth/register", json={
            "username": "alice",
            "email":    "alice@test.com",
            "password": "secret123",
        })
        assert r.status_code == 201
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_register_duplicate_email(self, client):
        client.post("/api/auth/register", json={
            "username": "alice", "email": "alice@test.com", "password": "secret123",
        })
        r = client.post("/api/auth/register", json={
            "username": "alice2", "email": "alice@test.com", "password": "secret123",
        })
        assert r.status_code == 409
        assert "Email" in r.json()["detail"]

    def test_register_duplicate_username(self, client):
        client.post("/api/auth/register", json={
            "username": "alice", "email": "alice@test.com", "password": "secret123",
        })
        r = client.post("/api/auth/register", json={
            "username": "alice", "email": "alice2@test.com", "password": "secret123",
        })
        assert r.status_code == 409
        assert "Username" in r.json()["detail"]

    def test_register_weak_password(self, client):
        r = client.post("/api/auth/register", json={
            "username": "bob", "email": "bob@test.com", "password": "abc",
        })
        assert r.status_code == 422

    def test_register_invalid_email(self, client):
        r = client.post("/api/auth/register", json={
            "username": "bob", "email": "not-an-email", "password": "secret123",
        })
        assert r.status_code == 422

    def test_register_short_username(self, client):
        r = client.post("/api/auth/register", json={
            "username": "ab", "email": "ab@test.com", "password": "secret123",
        })
        assert r.status_code == 422

    def test_register_missing_fields(self, client):
        r = client.post("/api/auth/register", json={"username": "bob"})
        assert r.status_code == 422


# ── Login ────────────────────────────────────────────────────────────────────

class TestLogin:
    def test_login_success(self, client):
        create_user_via_api(client, "alice", "alice@test.com", "secret123")
        r = client.post("/api/auth/login", json={
            "email": "alice@test.com", "password": "secret123",
        })
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_login_wrong_password(self, client):
        create_user_via_api(client, "alice", "alice@test.com", "secret123")
        r = client.post("/api/auth/login", json={
            "email": "alice@test.com", "password": "wrongpass",
        })
        assert r.status_code == 401

    def test_login_unknown_email(self, client):
        r = client.post("/api/auth/login", json={
            "email": "ghost@test.com", "password": "secret123",
        })
        assert r.status_code == 401

    def test_login_missing_field(self, client):
        r = client.post("/api/auth/login", json={"email": "alice@test.com"})
        assert r.status_code == 422


# ── /me endpoint ─────────────────────────────────────────────────────────────

class TestMe:
    def test_me_authenticated(self, client):
        token = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        r = client.get("/api/auth/me", headers=auth_headers(token))
        assert r.status_code == 200
        data = r.json()
        assert data["username"] == "alice"
        assert data["email"]    == "alice@test.com"
        assert "password_hash" not in data

    def test_me_no_token(self, client):
        r = client.get("/api/auth/me")
        assert r.status_code == 401

    def test_me_invalid_token(self, client):
        r = client.get("/api/auth/me",
                        headers={"Authorization": "Bearer invalidtoken"})
        assert r.status_code == 401


# ── Password hashing unit test ────────────────────────────────────────────────

def test_password_hashing():
    from backend.app.auth import hash_password, verify_password
    h = hash_password("mysecret")
    assert h != "mysecret"
    assert verify_password("mysecret", h)
    assert not verify_password("wrong", h)


def test_token_roundtrip():
    from backend.app.auth import create_access_token, decode_token
    token = create_access_token(42)
    assert decode_token(token) == 42

def test_token_invalid():
    from backend.app.auth import decode_token
    assert decode_token("garbage.token.here") is None
