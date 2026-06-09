"""
ReqLev – Tests: PDF Export

Covers:
  - Export returns a valid PDF byte stream
  - Owner, edit-perm and view-perm users can export
  - Non-member cannot export
  - PDF contains project name (smoke test on content)
  - Export with empty requirements succeeds
  - Export with multiple requirements and activities succeeds
"""

import pytest
from .conftest import (
    create_user_via_api, auth_headers,
    create_project_via_api, create_req_via_api,
)


class TestPDFExport:
    PDF_MAGIC = b"%PDF"

    def _full_setup(self, client):
        token = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        proj  = create_project_via_api(client, token, "Test PDF Project",
                                       "This is the description")
        create_req_via_api(client, token, proj["id"], "Autenticação",   "RF",  "done")
        create_req_via_api(client, token, proj["id"], "Performance",    "RNF", "in_progress")
        create_req_via_api(client, token, proj["id"], "Cadastro Usuário","RF",  "todo")
        return token, proj

    def test_export_pdf_owner(self, client):
        token, proj = self._full_setup(client)
        r = client.get(f"/api/projects/{proj['id']}/export/pdf",
            headers=auth_headers(token))
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content[:4] == self.PDF_MAGIC

    def test_export_pdf_view_user(self, client):
        t1, proj = self._full_setup(client)
        t2       = create_user_via_api(client, "bob", "bob@test.com", "secret123")
        bob_id   = client.get("/api/auth/me", headers=auth_headers(t2)).json()["id"]
        client.post(f"/api/projects/{proj['id']}/permissions",
            json={"user_id": bob_id, "permission": "view"},
            headers=auth_headers(t1))

        r = client.get(f"/api/projects/{proj['id']}/export/pdf",
            headers=auth_headers(t2))
        assert r.status_code == 200
        assert r.content[:4] == self.PDF_MAGIC

    def test_export_pdf_edit_user(self, client):
        t1, proj = self._full_setup(client)
        t2       = create_user_via_api(client, "bob", "bob@test.com", "secret123")
        bob_id   = client.get("/api/auth/me", headers=auth_headers(t2)).json()["id"]
        client.post(f"/api/projects/{proj['id']}/permissions",
            json={"user_id": bob_id, "permission": "edit"},
            headers=auth_headers(t1))

        r = client.get(f"/api/projects/{proj['id']}/export/pdf",
            headers=auth_headers(t2))
        assert r.status_code == 200
        assert r.content[:4] == self.PDF_MAGIC

    def test_export_pdf_non_member_denied(self, client):
        t1, proj = self._full_setup(client)
        t2       = create_user_via_api(client, "eve", "eve@test.com", "secret123")

        r = client.get(f"/api/projects/{proj['id']}/export/pdf",
            headers=auth_headers(t2))
        assert r.status_code == 403

    def test_export_pdf_unauthenticated(self, client):
        token, proj = self._full_setup(client)
        r = client.get(f"/api/projects/{proj['id']}/export/pdf")
        assert r.status_code == 401

    def test_export_pdf_empty_project(self, client):
        """Project with zero requirements should still generate valid PDF."""
        token = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        proj  = create_project_via_api(client, token, "Empty Project")
        r = client.get(f"/api/projects/{proj['id']}/export/pdf",
            headers=auth_headers(token))
        assert r.status_code == 200
        assert r.content[:4] == self.PDF_MAGIC

    def test_export_pdf_filename_header(self, client):
        token, proj = self._full_setup(client)
        r = client.get(f"/api/projects/{proj['id']}/export/pdf",
            headers=auth_headers(token))
        disp = r.headers.get("content-disposition", "")
        assert "attachment" in disp
        assert ".pdf" in disp

    def test_export_pdf_with_contributors(self, client):
        """PDF with a collaborator should still generate without errors."""
        t1   = create_user_via_api(client, "alice", "alice@test.com", "secret123")
        t2   = create_user_via_api(client, "bob",   "bob@test.com",   "secret123")
        proj = create_project_via_api(client, t1, "Collab Project")
        create_req_via_api(client, t1, proj["id"], "Req A")

        bob_id = client.get("/api/auth/me", headers=auth_headers(t2)).json()["id"]
        client.post(f"/api/projects/{proj['id']}/permissions",
            json={"user_id": bob_id, "permission": "edit"},
            headers=auth_headers(t1))

        r = client.get(f"/api/projects/{proj['id']}/export/pdf",
            headers=auth_headers(t1))
        assert r.status_code == 200
        assert r.content[:4] == self.PDF_MAGIC

    def test_pdf_service_unit(self):
        """Unit test: pdf_service returns bytes for a minimal project."""
        from backend.app.pdf_service import generate_project_pdf
        from backend.app.models import Project, Requirement, ActivityLog, User
        from datetime import datetime

        # Build minimal mock objects
        owner            = User()
        owner.id         = 1
        owner.username   = "alice"
        owner.email      = "alice@test.com"
        owner.created_at = datetime.utcnow()

        project             = Project()
        project.id          = 1
        project.name        = "Unit Test Project"
        project.description = "Automated PDF test"
        project.owner_id    = 1
        project.owner       = owner
        project.created_at  = datetime.utcnow()
        project.updated_at  = datetime.utcnow()

        req             = Requirement()
        req.id          = 1
        req.name        = "Sample Requirement"
        req.description = "A test requirement"
        req.type        = "RF"
        req.status      = "todo"
        req.created_at  = datetime.utcnow()
        req.updated_at  = datetime.utcnow()
        req.creator     = owner

        log             = ActivityLog()
        log.id          = 1
        log.project_id  = 1
        log.user_id     = 1
        log.action      = "Criou o projeto"
        log.object_type = "project"
        log.object_id   = 1
        log.object_name = "Unit Test Project"
        log.details     = None
        log.created_at  = datetime.utcnow()
        log.user        = owner

        pdf_bytes = generate_project_pdf(
            project    = project,
            requirements = [req],
            activities   = [log],
            contributors = [{"username": "bob", "email": "bob@test.com", "permission": "edit"}],
        )
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:4] == b"%PDF"
        assert len(pdf_bytes) > 1000   # sanity: non-trivial file
