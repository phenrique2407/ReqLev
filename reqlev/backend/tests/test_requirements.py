"""
ReqLev – Tests: Requirements

Covers:
  - Create requirement (owner, edit-perm user)
  - View-only user cannot create/edit/delete
  - Edit: any field including type change
  - Delete: any user with edit perm can delete any req (not just their own)
  - Filter by status
  - Activity log entries per action
"""

import pytest
from .conftest import (
    create_user_via_api, auth_headers,
    create_project_via_api, create_req_via_api,
)


class TestRequirements:
    # ── Setup helpers ─────────────────────────────────────────────────────

    def _two_users_project(self, client, bob_perm="edit"):
        t1   = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        t2   = create_user_via_api(client, "bob",   "bob@test.com",   "secret123")
        proj = create_project_via_api(client, t1, "Test Project")
        bob_id = client.get("/api/auth/me", headers=auth_headers(t2)).json()["id"]
        client.post(f"/api/projects/{proj['id']}/permissions",
            json={"user_id": bob_id, "permission": bob_perm},
            headers=auth_headers(t1))
        return t1, t2, proj

    # ── Create ────────────────────────────────────────────────────────────

    def test_create_requirement_by_owner(self, client):
        token = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        proj  = create_project_via_api(client, token, "Project")
        r = client.post(f"/api/projects/{proj['id']}/requirements",
            json={"name": "Login", "type": "RF", "status": "todo"},
            headers=auth_headers(token))
        assert r.status_code == 201
        d = r.json()
        assert d["name"]   == "Login"
        assert d["type"]   == "RF"
        assert d["status"] == "todo"

    def test_create_requirement_by_edit_user(self, client):
        t1, t2, proj = self._two_users_project(client, bob_perm="edit")
        r = client.post(f"/api/projects/{proj['id']}/requirements",
            json={"name": "Bob Req", "type": "RNF", "status": "in_progress"},
            headers=auth_headers(t2))
        assert r.status_code == 201

    def test_create_requirement_by_view_user(self, client):
        t1, t2, proj = self._two_users_project(client, bob_perm="view")
        r = client.post(f"/api/projects/{proj['id']}/requirements",
            json={"name": "No Access", "type": "RF", "status": "todo"},
            headers=auth_headers(t2))
        assert r.status_code == 403

    def test_create_requirement_empty_name(self, client):
        token = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        proj  = create_project_via_api(client, token, "Project")
        r = client.post(f"/api/projects/{proj['id']}/requirements",
            json={"name": "", "type": "RF", "status": "todo"},
            headers=auth_headers(token))
        assert r.status_code == 422

    def test_create_requirement_invalid_type(self, client):
        token = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        proj  = create_project_via_api(client, token, "Project")
        r = client.post(f"/api/projects/{proj['id']}/requirements",
            json={"name": "X", "type": "INVALID", "status": "todo"},
            headers=auth_headers(token))
        assert r.status_code == 422

    # ── List & filter ─────────────────────────────────────────────────────

    def test_list_requirements(self, client):
        token = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        proj  = create_project_via_api(client, token, "Project")
        create_req_via_api(client, token, proj["id"], "R1", status="todo")
        create_req_via_api(client, token, proj["id"], "R2", status="done")
        r = client.get(f"/api/projects/{proj['id']}/requirements",
            headers=auth_headers(token))
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_filter_by_status(self, client):
        token = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        proj  = create_project_via_api(client, token, "Project")
        create_req_via_api(client, token, proj["id"], "R1", status="todo")
        create_req_via_api(client, token, proj["id"], "R2", status="done")
        create_req_via_api(client, token, proj["id"], "R3", status="done")

        r = client.get(
            f"/api/projects/{proj['id']}/requirements?status=done",
            headers=auth_headers(token))
        assert r.status_code == 200
        results = r.json()
        assert len(results) == 2
        assert all(req["status"] == "done" for req in results)

    def test_filter_invalid_status(self, client):
        token = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        proj  = create_project_via_api(client, token, "Project")
        r = client.get(
            f"/api/projects/{proj['id']}/requirements?status=invalid",
            headers=auth_headers(token))
        assert r.status_code == 400

    def test_view_user_can_list(self, client):
        t1, t2, proj = self._two_users_project(client, bob_perm="view")
        create_req_via_api(client, t1, proj["id"], "R1")
        r = client.get(f"/api/projects/{proj['id']}/requirements",
            headers=auth_headers(t2))
        assert r.status_code == 200

    # ── Edit ──────────────────────────────────────────────────────────────

    def test_edit_requirement_by_owner(self, client):
        token = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        proj  = create_project_via_api(client, token, "Project")
        req   = create_req_via_api(client, token, proj["id"], "Old Name")
        r = client.put(
            f"/api/projects/{proj['id']}/requirements/{req['id']}",
            json={"name": "New Name"},
            headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["name"] == "New Name"

    def test_edit_changes_type(self, client):
        """Type can be changed at any time by edit-perm users."""
        t1, t2, proj = self._two_users_project(client, bob_perm="edit")
        req = create_req_via_api(client, t1, proj["id"], "Req", req_type="RF")
        r = client.put(
            f"/api/projects/{proj['id']}/requirements/{req['id']}",
            json={"type": "RNF"},
            headers=auth_headers(t2))
        assert r.status_code == 200
        assert r.json()["type"] == "RNF"

    def test_edit_changes_status(self, client):
        token = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        proj  = create_project_via_api(client, token, "Project")
        req   = create_req_via_api(client, token, proj["id"], "R1", status="todo")
        r = client.put(
            f"/api/projects/{proj['id']}/requirements/{req['id']}",
            json={"status": "done"},
            headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["status"] == "done"

    def test_edit_user_can_edit_any_req(self, client):
        """Bob (edit-perm) can edit a req created by Alice."""
        t1, t2, proj = self._two_users_project(client, bob_perm="edit")
        req = create_req_via_api(client, t1, proj["id"], "Alice's Req")
        r = client.put(
            f"/api/projects/{proj['id']}/requirements/{req['id']}",
            json={"name": "Edited by Bob"},
            headers=auth_headers(t2))
        assert r.status_code == 200
        assert r.json()["name"] == "Edited by Bob"

    def test_view_user_cannot_edit(self, client):
        t1, t2, proj = self._two_users_project(client, bob_perm="view")
        req = create_req_via_api(client, t1, proj["id"], "Req")
        r = client.put(
            f"/api/projects/{proj['id']}/requirements/{req['id']}",
            json={"name": "Hacked"},
            headers=auth_headers(t2))
        assert r.status_code == 403

    def test_edit_nonexistent_requirement(self, client):
        token = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        proj  = create_project_via_api(client, token, "Project")
        r = client.put(
            f"/api/projects/{proj['id']}/requirements/99999",
            json={"name": "Ghost"},
            headers=auth_headers(token))
        assert r.status_code == 404

    # ── Delete ────────────────────────────────────────────────────────────

    def test_delete_requirement_by_owner(self, client):
        token = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        proj  = create_project_via_api(client, token, "Project")
        req   = create_req_via_api(client, token, proj["id"], "Delete Me")
        r = client.delete(
            f"/api/projects/{proj['id']}/requirements/{req['id']}",
            headers=auth_headers(token))
        assert r.status_code == 204

    def test_edit_user_can_delete_any_req(self, client):
        """Bob (edit-perm) can delete a req created by Alice."""
        t1, t2, proj = self._two_users_project(client, bob_perm="edit")
        req = create_req_via_api(client, t1, proj["id"], "Alice's Req")
        r = client.delete(
            f"/api/projects/{proj['id']}/requirements/{req['id']}",
            headers=auth_headers(t2))
        assert r.status_code == 204

    def test_view_user_cannot_delete(self, client):
        t1, t2, proj = self._two_users_project(client, bob_perm="view")
        req = create_req_via_api(client, t1, proj["id"], "Req")
        r = client.delete(
            f"/api/projects/{proj['id']}/requirements/{req['id']}",
            headers=auth_headers(t2))
        assert r.status_code == 403

    # ── Activity log on req actions ───────────────────────────────────────

    def test_req_create_logs_activity(self, client):
        token = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        proj  = create_project_via_api(client, token, "Project")
        create_req_via_api(client, token, proj["id"], "Logged Req")

        r = client.get(f"/api/projects/{proj['id']}/activities",
            headers=auth_headers(token))
        assert r.status_code == 200
        assert any("Criou requisito" in l["action"] for l in r.json())

    def test_req_update_logs_activity(self, client):
        token = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        proj  = create_project_via_api(client, token, "Project")
        req   = create_req_via_api(client, token, proj["id"], "R1")
        client.put(
            f"/api/projects/{proj['id']}/requirements/{req['id']}",
            json={"name": "Updated"},
            headers=auth_headers(token))

        r = client.get(f"/api/projects/{proj['id']}/activities",
            headers=auth_headers(token))
        assert any("Editou requisito" in l["action"] for l in r.json())

    def test_req_delete_logs_activity(self, client):
        token = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        proj  = create_project_via_api(client, token, "Project")
        req   = create_req_via_api(client, token, proj["id"], "To Delete")
        client.delete(
            f"/api/projects/{proj['id']}/requirements/{req['id']}",
            headers=auth_headers(token))

        r = client.get(f"/api/projects/{proj['id']}/activities",
            headers=auth_headers(token))
        assert any("Deletou requisito" in l["action"] for l in r.json())
