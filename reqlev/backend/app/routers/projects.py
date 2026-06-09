"""ReqLev – Projects Router: /api/projects/*

Permission rules:
  owner            – all actions (create, read, update, delete, share, export)
  permission=edit  – read, update project, manage requirements, export
  permission=view  – read, view activity log, export
"""

import asyncio
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse as FastAPIStreaming
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..auth import get_current_user
from ..schemas import (
    ProjectCreate, ProjectUpdate, ProjectOut, ProjectSummary,
    ShareProject, PermissionOut, UpdatePermission,
)
from .. import models
from ..activity_service import log as activity_log
from ..sse_manager import sse_manager
from ..pdf_service import generate_project_pdf

router = APIRouter(prefix="/api/projects", tags=["Projects"])


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_project_or_404(project_id: int, db: Session) -> models.Project:
    proj = (
        db.query(models.Project)
        .options(
            joinedload(models.Project.owner),
            joinedload(models.Project.permissions).joinedload(models.ProjectPermission.user),
        )
        .filter(models.Project.id == project_id)
        .first()
    )
    if not proj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return proj


def _get_user_permission(
    project: models.Project, user: models.User
) -> Optional[str]:
    """Return 'owner', 'edit', 'view', or None."""
    if project.owner_id == user.id:
        return "owner"
    for perm in project.permissions:
        if perm.user_id == user.id:
            return perm.permission.value
    return None


def _require_access(project: models.Project, user: models.User) -> str:
    """Raise 403 if user has no access; return effective permission string."""
    perm = _get_user_permission(project, user)
    if perm is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")
    return perm


def _require_edit(project: models.Project, user: models.User) -> str:
    perm = _require_access(project, user)
    if perm not in ("owner", "edit"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Edit permission required")
    return perm


def _require_owner(project: models.Project, user: models.User) -> None:
    if project.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the project owner can do this")


def _serialize_project(project: models.Project, user_perm: str) -> dict:
    return {
        "id":          project.id,
        "name":        project.name,
        "description": project.description,
        "owner_id":    project.owner_id,
        "created_at":  project.created_at.isoformat() if project.created_at else None,
        "updated_at":  project.updated_at.isoformat() if project.updated_at else None,
        "owner": {
            "id":         project.owner.id,
            "username":   project.owner.username,
            "email":      project.owner.email,
            "created_at": project.owner.created_at.isoformat() if project.owner.created_at else None,
        } if project.owner else None,
        "user_permission": user_perm,
    }


# ── List / Create ─────────────────────────────────────────────────────────────

@router.get("", response_model=List[ProjectSummary],
            summary="List all projects accessible to the current user")
def list_projects(
    current_user: models.User = Depends(get_current_user),
    db:           Session     = Depends(get_db),
):
    """Returns owned projects + projects shared with the user, with requirement counts."""
    # Owned projects
    owned = (
        db.query(models.Project)
        .options(joinedload(models.Project.owner),
                 joinedload(models.Project.requirements))
        .filter(models.Project.owner_id == current_user.id)
        .all()
    )

    # Shared projects
    perms = (
        db.query(models.ProjectPermission)
        .options(joinedload(models.ProjectPermission.project)
                 .joinedload(models.Project.owner),
                 joinedload(models.ProjectPermission.project)
                 .joinedload(models.Project.requirements))
        .filter(models.ProjectPermission.user_id == current_user.id)
        .all()
    )

    result = []
    seen   = set()

    for proj in owned:
        result.append({
            **_serialize_project(proj, "owner"),
            "requirement_count": len(proj.requirements),
        })
        seen.add(proj.id)

    for perm in perms:
        proj = perm.project
        if proj.id not in seen:
            result.append({
                **_serialize_project(proj, perm.permission.value),
                "requirement_count": len(proj.requirements),
            })
            seen.add(proj.id)

    result.sort(key=lambda p: p["updated_at"] or "", reverse=True)
    return result


@router.post("", status_code=201, summary="Create a new project")
async def create_project(
    payload:      ProjectCreate  = ...,
    current_user: models.User   = Depends(get_current_user),
    db:           Session       = Depends(get_db),
):
    proj = models.Project(
        name        = payload.name,
        description = payload.description,
        owner_id    = current_user.id,
    )
    db.add(proj)
    db.flush()

    activity_log(
        db, proj.id, current_user.id,
        action="Criou o projeto",
        object_type=models.ObjectType.project,
        object_id=proj.id,
        object_name=proj.name,
    )
    db.commit()
    db.refresh(proj)

    return {**_serialize_project(proj, "owner"), "requirement_count": 0}


# ── Single project CRUD ───────────────────────────────────────────────────────

@router.get("/{project_id}", summary="Get a single project's details")
def get_project(
    project_id:   int,
    current_user: models.User = Depends(get_current_user),
    db:           Session     = Depends(get_db),
):
    proj = _get_project_or_404(project_id, db)
    perm = _require_access(proj, current_user)
    return _serialize_project(proj, perm)


@router.put("/{project_id}", summary="Edit a project (owner or edit-perm required)")
async def update_project(
    project_id:   int,
    payload:      ProjectUpdate,
    current_user: models.User  = Depends(get_current_user),
    db:           Session      = Depends(get_db),
):
    proj = _get_project_or_404(project_id, db)
    _require_edit(proj, current_user)

    changed = []
    if payload.name is not None and payload.name != proj.name:
        changed.append(f"nome: '{proj.name}' → '{payload.name}'")
        proj.name = payload.name
    if payload.description is not None and payload.description != proj.description:
        changed.append("descrição atualizada")
        proj.description = payload.description

    if changed:
        activity_log(
            db, proj.id, current_user.id,
            action="Editou o projeto",
            object_type=models.ObjectType.project,
            object_id=proj.id,
            object_name=proj.name,
            details="; ".join(changed),
        )
        db.commit()
        db.refresh(proj)

        perm = _get_user_permission(proj, current_user)
        event_data = {**_serialize_project(proj, perm or ""), "type": "project_updated"}
        asyncio.ensure_future(sse_manager.broadcast(project_id, "project_updated", event_data))

    perm = _get_user_permission(proj, current_user)
    return _serialize_project(proj, perm or "")


@router.delete("/{project_id}", status_code=204,
               summary="Delete a project (owner only)")
async def delete_project(
    project_id:   int,
    current_user: models.User = Depends(get_current_user),
    db:           Session     = Depends(get_db),
):
    proj = _get_project_or_404(project_id, db)
    _require_owner(proj, current_user)

    asyncio.ensure_future(
        sse_manager.broadcast(project_id, "project_deleted", {"project_id": project_id})
    )

    db.delete(proj)
    db.commit()
    return Response(status_code=204)


# ── Sharing / Permissions ─────────────────────────────────────────────────────

@router.get("/{project_id}/permissions", response_model=List[PermissionOut],
            summary="List all permissions for a project")
def list_permissions(
    project_id:   int,
    current_user: models.User = Depends(get_current_user),
    db:           Session     = Depends(get_db),
):
    proj = _get_project_or_404(project_id, db)
    _require_access(proj, current_user)
    return proj.permissions


@router.post("/{project_id}/permissions", response_model=PermissionOut, status_code=201,
             summary="Share a project with another user (owner only)")
async def share_project(
    project_id:   int,
    payload:      ShareProject,
    current_user: models.User  = Depends(get_current_user),
    db:           Session      = Depends(get_db),
):
    proj = _get_project_or_404(project_id, db)
    _require_owner(proj, current_user)

    if payload.user_id == current_user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot share with yourself")

    target = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Target user not found")

    existing = (
        db.query(models.ProjectPermission)
        .filter_by(project_id=project_id, user_id=payload.user_id)
        .first()
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "User already has access – use PUT to update")

    perm = models.ProjectPermission(
        project_id = project_id,
        user_id    = payload.user_id,
        permission = payload.permission,
    )
    db.add(perm)
    db.flush()

    perm_label = "Apenas Ver" if payload.permission.value == "view" else "Editar"
    activity_log(
        db, project_id, current_user.id,
        action=f"Compartilhou com {target.username} ({perm_label})",
        object_type=models.ObjectType.project,
        object_id=project_id,
        object_name=proj.name,
    )
    db.commit()
    db.refresh(perm)

    asyncio.ensure_future(
        sse_manager.broadcast(project_id, "permission_added",
                              {"user_id": target.id, "username": target.username,
                               "permission": payload.permission.value})
    )
    return perm


@router.put("/{project_id}/permissions/{user_id}",
            summary="Update a user's permission level (owner only)")
async def update_permission(
    project_id:   int,
    user_id:      int,
    payload:      UpdatePermission,
    current_user: models.User      = Depends(get_current_user),
    db:           Session          = Depends(get_db),
):
    proj = _get_project_or_404(project_id, db)
    _require_owner(proj, current_user)

    perm = (
        db.query(models.ProjectPermission)
        .filter_by(project_id=project_id, user_id=user_id)
        .first()
    )
    if not perm:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Permission record not found")

    perm.permission = payload.permission
    activity_log(
        db, project_id, current_user.id,
        action=f"Atualizou permissão de {perm.user.username} para {payload.permission.value}",
        object_type=models.ObjectType.project,
        object_id=project_id,
        object_name=proj.name,
    )
    db.commit()
    db.refresh(perm)
    return perm


@router.delete("/{project_id}/permissions/{user_id}", status_code=204,
               summary="Revoke a user's access (owner only)")
async def revoke_permission(
    project_id:   int,
    user_id:      int,
    current_user: models.User = Depends(get_current_user),
    db:           Session     = Depends(get_db),
):
    proj = _get_project_or_404(project_id, db)
    _require_owner(proj, current_user)

    perm = (
        db.query(models.ProjectPermission)
        .filter_by(project_id=project_id, user_id=user_id)
        .first()
    )
    if not perm:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Permission record not found")

    username = perm.user.username if perm.user else str(user_id)
    activity_log(
        db, project_id, current_user.id,
        action=f"Removeu acesso de {username}",
        object_type=models.ObjectType.project,
        object_id=project_id,
        object_name=proj.name,
    )
    db.delete(perm)
    db.commit()

    asyncio.ensure_future(
        sse_manager.broadcast(project_id, "permission_removed", {"user_id": user_id})
    )
    return Response(status_code=204)


# ── PDF Export ────────────────────────────────────────────────────────────────

@router.get("/{project_id}/export/pdf",
            summary="Export project to PDF (view or edit permission required)")
def export_pdf(
    project_id:   int,
    current_user: models.User = Depends(get_current_user),
    db:           Session     = Depends(get_db),
):
    """Generate and stream a PDF report for the project."""
    proj = _get_project_or_404(project_id, db)
    _require_access(proj, current_user)

    requirements = (
        db.query(models.Requirement)
        .options(joinedload(models.Requirement.creator))
        .filter(models.Requirement.project_id == project_id)
        .order_by(models.Requirement.id)
        .all()
    )

    activities = (
        db.query(models.ActivityLog)
        .options(joinedload(models.ActivityLog.user))
        .filter(models.ActivityLog.project_id == project_id)
        .order_by(models.ActivityLog.created_at.asc())
        .all()
    )

    # Build contributors list from permissions (not the owner himself)
    contributors = []
    for perm in proj.permissions:
        if perm.user:
            contributors.append({
                "username":   perm.user.username,
                "email":      perm.user.email,
                "permission": perm.permission.value,
            })

    pdf_bytes = generate_project_pdf(proj, requirements, activities, contributors)

    safe_name = proj.name.replace(" ", "_")[:40]
    filename  = f"ReqLev_{safe_name}.pdf"

    return FastAPIStreaming(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
