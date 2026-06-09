"""
ReqLev – Tests: Projects & Permissions

Covers:
  - CRUD: create, list, get, update, delete
  - Ownership rules (only owner can delete)
  - Shared access: view-only and edit
  - Sharing: share, update permission, revoke
  - User search
  - Activity log creation on each action
"""

import pytest
from .conftest import (
    create_user_via_api, auth_headers,
    create_project_via_api, create_req_via_api,
)


# ── Projects CRUD ─────────────────────────────────────────────────────────────

class TestProjectCRUD:
    def test_create_project(self, client):
        token = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        r = client.post("/api/projects",
            json={"name": "Proj A", "description": "Desc"},
            headers=auth_headers(token))
        assert r.status_code == 201
        d = r.json()
        assert d["name"]        == "Proj A"
        assert d["description"] == "Desc"
        assert d["owner"]["username"] == "alice"
        assert d["user_permission"]   == "owner"

    def test_create_project_no_description(self, client):
        token = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        r = client.post("/api/projects",
            json={"name": "Minimal"},
            headers=auth_headers(token))
        assert r.status_code == 201
        assert r.json()["description"] is None

    def test_create_project_empty_name(self, client):
        token = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        r = client.post("/api/projects",
            json={"name": "   "},
            headers=auth_headers(token))
        assert r.status_code == 422

    def test_list_projects_only_own(self, client):
        t1 = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        t2 = create_user_via_api(client, "bob",   "bob@test.com",   "secret123")
        create_project_via_api(client, t1, "Alice Project")
        create_project_via_api(client, t2, "Bob Project")
        r = client.get("/api/projects", headers=auth_headers(t1))
        assert r.status_code == 200
        names = [p["name"] for p in r.json()]
        assert "Alice Project" in names
        assert "Bob Project"   not in names

    def test_get_project(self, client):
        token = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        proj  = create_project_via_api(client, token, "Get Me")
        r = client.get(f"/api/projects/{proj['id']}", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["name"] == "Get Me"

    def test_get_project_not_found(self, client):
        token = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        r = client.get("/api/projects/99999", headers=auth_headers(token))
        assert r.status_code == 404

    def test_update_project(self, client):
        token = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        proj  = create_project_via_api(client, token, "Old Name")
        r = client.put(f"/api/projects/{proj['id']}",
            json={"name": "New Name"},
            headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["name"] == "New Name"

    def test_delete_project_by_owner(self, client):
        token = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        proj  = create_project_via_api(client, token, "Delete Me")
        r = client.delete(f"/api/projects/{proj['id']}", headers=auth_headers(token))
        assert r.status_code == 204
        r2 = client.get(f"/api/projects/{proj['id']}", headers=auth_headers(token))
        assert r2.status_code == 404

    def test_delete_project_by_non_owner(self, client):
        t1   = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        t2   = create_user_via_api(client, "bob",   "bob@test.com",   "secret123")
        proj = create_project_via_api(client, t1, "Alice Project")
        r    = client.delete(f"/api/projects/{proj['id']}", headers=auth_headers(t2))
        assert r.status_code == 403

    def test_unauthenticated_access(self, client):
        r = client.get("/api/projects")
        assert r.status_code == 401


# ── Permissions & Sharing ─────────────────────────────────────────────────────

class TestPermissions:
    def _setup(self, client):
        t1   = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        t2   = create_user_via_api(client, "bob",   "bob@test.com",   "secret123")
        proj = create_project_via_api(client, t1, "Shared Project")
        return t1, t2, proj

    def test_share_view(self, client):
        t1, t2, proj = self._setup(client)
        # Get bob's id
        me_r = client.get("/api/auth/me", headers=auth_headers(t2))
        bob_id = me_r.json()["id"]

        r = client.post(f"/api/projects/{proj['id']}/permissions",
            json={"user_id": bob_id, "permission": "view"},
            headers=auth_headers(t1))
        assert r.status_code == 201
        assert r.json()["permission"] == "view"

    def test_view_user_can_read_project(self, client):
        t1, t2, proj = self._setup(client)
        bob_id = client.get("/api/auth/me", headers=auth_headers(t2)).json()["id"]
        client.post(f"/api/projects/{proj['id']}/permissions",
            json={"user_id": bob_id, "permission": "view"},
            headers=auth_headers(t1))

        r = client.get(f"/api/projects/{proj['id']}", headers=auth_headers(t2))
        assert r.status_code == 200
        assert r.json()["user_permission"] == "view"

    def test_view_user_cannot_edit_project(self, client):
        t1, t2, proj = self._setup(client)
        bob_id = client.get("/api/auth/me", headers=auth_headers(t2)).json()["id"]
        client.post(f"/api/projects/{proj['id']}/permissions",
            json={"user_id": bob_id, "permission": "view"},
            headers=auth_headers(t1))

        r = client.put(f"/api/projects/{proj['id']}",
            json={"name": "Hacked"},
            headers=auth_headers(t2))
        assert r.status_code == 403

    def test_view_user_cannot_delete_project(self, client):
        t1, t2, proj = self._setup(client)
        bob_id = client.get("/api/auth/me", headers=auth_headers(t2)).json()["id"]
        client.post(f"/api/projects/{proj['id']}/permissions",
            json={"user_id": bob_id, "permission": "view"},
            headers=auth_headers(t1))

        r = client.delete(f"/api/projects/{proj['id']}", headers=auth_headers(t2))
        assert r.status_code == 403

    def test_edit_user_can_modify_project(self, client):
        t1, t2, proj = self._setup(client)
        bob_id = client.get("/api/auth/me", headers=auth_headers(t2)).json()["id"]
        client.post(f"/api/projects/{proj['id']}/permissions",
            json={"user_id": bob_id, "permission": "edit"},
            headers=auth_headers(t1))

        r = client.put(f"/api/projects/{proj['id']}",
            json={"name": "Updated by Bob"},
            headers=auth_headers(t2))
        assert r.status_code == 200
        assert r.json()["name"] == "Updated by Bob"

    def test_edit_user_cannot_delete_project(self, client):
        t1, t2, proj = self._setup(client)
        bob_id = client.get("/api/auth/me", headers=auth_headers(t2)).json()["id"]
        client.post(f"/api/projects/{proj['id']}/permissions",
            json={"user_id": bob_id, "permission": "edit"},
            headers=auth_headers(t1))

        r = client.delete(f"/api/projects/{proj['id']}", headers=auth_headers(t2))
        assert r.status_code == 403

    def test_shared_project_in_list(self, client):
        t1, t2, proj = self._setup(client)
        bob_id = client.get("/api/auth/me", headers=auth_headers(t2)).json()["id"]
        client.post(f"/api/projects/{proj['id']}/permissions",
            json={"user_id": bob_id, "permission": "view"},
            headers=auth_headers(t1))

        r = client.get("/api/projects", headers=auth_headers(t2))
        names = [p["name"] for p in r.json()]
        assert "Shared Project" in names

    def test_no_access_returns_403(self, client):
        t1   = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        t2   = create_user_via_api(client, "bob",   "bob@test.com",   "secret123")
        proj = create_project_via_api(client, t1, "Private")

        r = client.get(f"/api/projects/{proj['id']}", headers=auth_headers(t2))
        assert r.status_code == 403

    def test_cannot_share_with_self(self, client):
        token   = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        proj    = create_project_via_api(client, token, "My Project")
        alice_id = client.get("/api/auth/me", headers=auth_headers(token)).json()["id"]

        r = client.post(f"/api/projects/{proj['id']}/permissions",
            json={"user_id": alice_id, "permission": "view"},
            headers=auth_headers(token))
        assert r.status_code == 400

    def test_duplicate_share_rejected(self, client):
        t1, t2, proj = self._setup(client)
        bob_id = client.get("/api/auth/me", headers=auth_headers(t2)).json()["id"]
        client.post(f"/api/projects/{proj['id']}/permissions",
            json={"user_id": bob_id, "permission": "view"},
            headers=auth_headers(t1))
        r = client.post(f"/api/projects/{proj['id']}/permissions",
            json={"user_id": bob_id, "permission": "edit"},
            headers=auth_headers(t1))
        assert r.status_code == 409

    def test_update_permission(self, client):
        t1, t2, proj = self._setup(client)
        bob_id = client.get("/api/auth/me", headers=auth_headers(t2)).json()["id"]
        client.post(f"/api/projects/{proj['id']}/permissions",
            json={"user_id": bob_id, "permission": "view"},
            headers=auth_headers(t1))

        r = client.put(f"/api/projects/{proj['id']}/permissions/{bob_id}",
            json={"permission": "edit"},
            headers=auth_headers(t1))
        assert r.status_code == 200
        assert r.json()["permission"] == "edit"

    def test_revoke_permission(self, client):
        t1, t2, proj = self._setup(client)
        bob_id = client.get("/api/auth/me", headers=auth_headers(t2)).json()["id"]
        client.post(f"/api/projects/{proj['id']}/permissions",
            json={"user_id": bob_id, "permission": "view"},
            headers=auth_headers(t1))

        r = client.delete(
            f"/api/projects/{proj['id']}/permissions/{bob_id}",
            headers=auth_headers(t1))
        assert r.status_code == 204

        r2 = client.get(f"/api/projects/{proj['id']}", headers=auth_headers(t2))
        assert r2.status_code == 403

    def test_only_owner_can_share(self, client):
        t1, t2, proj = self._setup(client)
        t3     = create_user_via_api(client, "charlie", "charlie@test.com", "secret123")
        bob_id = client.get("/api/auth/me", headers=auth_headers(t2)).json()["id"]

        # give bob edit perm
        client.post(f"/api/projects/{proj['id']}/permissions",
            json={"user_id": bob_id, "permission": "edit"},
            headers=auth_headers(t1))

        charlie_id = client.get("/api/auth/me", headers=auth_headers(t3)).json()["id"]
        # bob tries to share → should fail
        r = client.post(f"/api/projects/{proj['id']}/permissions",
            json={"user_id": charlie_id, "permission": "view"},
            headers=auth_headers(t2))
        assert r.status_code == 403


# ── User search ───────────────────────────────────────────────────────────────

class TestUserSearch:
    def test_search_by_username(self, client):
        t1 = create_user_via_api(client, "alice",   "alice@test.com",   "secret123")
        _  = create_user_via_api(client, "roberto", "roberto@test.com", "secret123")

        r = client.get("/api/users/search?q=roberto", headers=auth_headers(t1))
        assert r.status_code == 200
        names = [u["username"] for u in r.json()]
        assert "roberto" in names

    def test_search_by_email(self, client):
        t1 = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        _  = create_user_via_api(client, "bob",   "bob@test.com",   "secret123")

        r = client.get("/api/users/search?q=bob@", headers=auth_headers(t1))
        assert r.status_code == 200
        emails = [u["email"] for u in r.json()]
        assert "bob@test.com" in emails

    def test_search_excludes_self(self, client):
        token = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        r = client.get("/api/users/search?q=alice", headers=auth_headers(token))
        assert r.status_code == 200
        names = [u["username"] for u in r.json()]
        assert "alice" not in names

    def test_search_requires_auth(self, client):
        r = client.get("/api/users/search?q=alice")
        assert r.status_code == 401


# ── Activity log ──────────────────────────────────────────────────────────────

class TestActivityLog:
    def test_create_project_logs_activity(self, client):
        token = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        proj  = create_project_via_api(client, token, "Logged Project")

        r = client.get(f"/api/projects/{proj['id']}/activities",
            headers=auth_headers(token))
        assert r.status_code == 200
        logs = r.json()
        assert any("Criou o projeto" in l["action"] for l in logs)

    def test_view_user_can_see_activity(self, client):
        t1   = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        t2   = create_user_via_api(client, "bob",   "bob@test.com",   "secret123")
        proj = create_project_via_api(client, t1, "Shared Project")
        bob_id = client.get("/api/auth/me", headers=auth_headers(t2)).json()["id"]
        client.post(f"/api/projects/{proj['id']}/permissions",
            json={"user_id": bob_id, "permission": "view"},
            headers=auth_headers(t1))

        r = client.get(f"/api/projects/{proj['id']}/activities",
            headers=auth_headers(t2))
        assert r.status_code == 200

    def test_no_access_cannot_see_activity(self, client):
        t1   = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        t2   = create_user_via_api(client, "bob",   "bob@test.com",   "secret123")
        proj = create_project_via_api(client, t1, "Private Project")

        r = client.get(f"/api/projects/{proj['id']}/activities",
            headers=auth_headers(t2))
        assert r.status_code == 403
