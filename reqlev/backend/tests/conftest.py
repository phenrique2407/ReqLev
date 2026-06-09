"""
ReqLev – Shared pytest fixtures

Strategy
--------
We set DATABASE_URL to a SQLite in-memory URI **before** any app module is
imported. `database.py` reads the env var at import time and builds an engine
with StaticPool so every connection—create_all, get_db sessions, auth
operations—shares the same single in-memory database.

We then reuse the app's engine/Base/SessionLocal directly instead of
creating a second, parallel engine. This eliminates the "no such table"
failure that occurs when create_all and the request session use
different connections (= different in-memory DBs).
"""

import os

# ── Must happen BEFORE any backend import ─────────────────────────────────────
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient


# ── DB fixture ────────────────────────────────────────────────────────────────

@pytest.fixture()
def db():
    """
    Provides a fresh SQLite session for each test.
    All tables are created before the test and dropped after.
    """
    # Import here so env override is already in effect
    from backend.app.database import engine, Base, SessionLocal
    from backend.app import models  # noqa: F401 – registers ORM models

    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


# ── Client fixture ────────────────────────────────────────────────────────────

@pytest.fixture()
def client(db):
    """
    TestClient whose `get_db` dependency is replaced with the test session.
    Startup lifecycle is suppressed so create_tables() doesn't re-create
    the engine with a potentially different URL.
    """
    from backend.app.main import app
    from backend.app.database import get_db

    def _override():
        yield db

    app.dependency_overrides[get_db] = _override

    # raise_server_exceptions=True surfaces 500-level errors in tests
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()


# ── Helper factories ──────────────────────────────────────────────────────────

def create_user_via_api(client, username, email, password):
    r = client.post("/api/auth/register", json={
        "username": username,
        "email":    email,
        "password": password,
    })
    assert r.status_code == 201, r.json()
    return r.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def create_project_via_api(client, token, name, description=None):
    r = client.post(
        "/api/projects",
        json={"name": name, "description": description},
        headers=auth_headers(token),
    )
    assert r.status_code == 201, r.json()
    return r.json()


def create_req_via_api(client, token, project_id, name,
                       req_type="RF", status="todo"):
    r = client.post(
        f"/api/projects/{project_id}/requirements",
        json={"name": name, "type": req_type, "status": status},
        headers=auth_headers(token),
    )
    assert r.status_code == 201, r.json()
    return r.json()
