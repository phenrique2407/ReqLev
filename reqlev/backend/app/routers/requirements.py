"""ReqLev – Requirements Router: /api/projects/{id}/requirements/*

Permission rules:
  owner / edit  – create, update, delete any requirement
  view          – read only
"""

import asyncio
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..auth import get_current_user
from ..schemas import RequirementCreate, RequirementUpdate, RequirementOut
from .. import models
from ..activity_service import log as activity_log
from ..sse_manager import sse_manager

router = APIRouter(prefix="/api/projects/{project_id}/requirements",
                   tags=["Requirements"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_project_or_404(project_id: int, db: Session) -> models.Project:
    proj = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not proj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return proj


def _get_user_permission(project: models.Project, user: models.User) -> Optional[str]:
    if project.owner_id == user.id:
        return "owner"
    for perm in (
        db_perm
        for db_perm in project.permissions
    ):
        if perm.user_id == user.id:
            return perm.permission.value
    return None


def _check_access(project_id: int, user: models.User, db: Session, need_edit=False):
    """Returns (project, permission_str). Raises 403/404 as needed."""
    proj = (
        db.query(models.Project)
        .options(joinedload(models.Project.permissions))
        .filter(models.Project.id == project_id)
        .first()
    )
    if not proj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    perm = _get_user_permission(proj, user)
    if perm is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")
    if need_edit and perm not in ("owner", "edit"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Edit permission required")
    return proj, perm


def _serialize_req(req: models.Requirement) -> dict:
    return {
        "id":          req.id,
        "project_id":  req.project_id,
        "name":        req.name,
        "description": req.description,
        "type":        req.type.value  if req.type   else None,
        "status":      req.status.value if req.status else None,
        "created_by":  req.created_by,
        "created_at":  req.created_at.isoformat() if req.created_at else None,
        "updated_at":  req.updated_at.isoformat() if req.updated_at else None,
        "creator": {
            "id":         req.creator.id,
            "username":   req.creator.username,
            "email":      req.creator.email,
            "created_at": req.creator.created_at.isoformat() if req.creator.created_at else None,
        } if req.creator else None,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", summary="List requirements for a project (optionally filtered by status)")
def list_requirements(
    project_id:   int,
    status_filter: Optional[str] = Query(None, alias="status",
                                          description="Filter: todo | in_progress | done"),
    current_user: models.User   = Depends(get_current_user),
    db:           Session       = Depends(get_db),
):
    _check_access(project_id, current_user, db)

    q = (
        db.query(models.Requirement)
        .options(joinedload(models.Requirement.creator))
        .filter(models.Requirement.project_id == project_id)
    )

    if status_filter:
        try:
            s = models.RequirementStatus(status_filter)
            q = q.filter(models.Requirement.status == s)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                "Invalid status; use: todo, in_progress, done")

    return [_serialize_req(r) for r in q.order_by(models.Requirement.id).all()]


@router.post("", status_code=201,
             summary="Create a new requirement (edit permission required)")
async def create_requirement(
    project_id:   int,
    payload:      RequirementCreate,
    current_user: models.User       = Depends(get_current_user),
    db:           Session           = Depends(get_db),
):
    _check_access(project_id, current_user, db, need_edit=True)

    req = models.Requirement(
        project_id  = project_id,
        name        = payload.name,
        description = payload.description,
        type        = payload.type,
        status      = payload.status,
        created_by  = current_user.id,
    )
    db.add(req)
    db.flush()

    activity_log(
        db, project_id, current_user.id,
        action="Criou requisito",
        object_type=models.ObjectType.requirement,
        object_id=req.id,
        object_name=req.name,
        details=f"Tipo: {req.type.value}, Status: {req.status.value}",
    )
    db.commit()

    # Eager load creator
    db.refresh(req)
    req_with_creator = (
        db.query(models.Requirement)
        .options(joinedload(models.Requirement.creator))
        .filter(models.Requirement.id == req.id)
        .first()
    )
    data = _serialize_req(req_with_creator)
    asyncio.ensure_future(
        sse_manager.broadcast(project_id, "requirement_created", data)
    )
    return data


@router.get("/{req_id}", summary="Get a single requirement")
def get_requirement(
    project_id:   int,
    req_id:       int,
    current_user: models.User = Depends(get_current_user),
    db:           Session     = Depends(get_db),
):
    _check_access(project_id, current_user, db)
    req = (
        db.query(models.Requirement)
        .options(joinedload(models.Requirement.creator))
        .filter(models.Requirement.id == req_id,
                models.Requirement.project_id == project_id)
        .first()
    )
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Requirement not found")
    return _serialize_req(req)


@router.put("/{req_id}", summary="Update a requirement (edit permission required)")
async def update_requirement(
    project_id:   int,
    req_id:       int,
    payload:      RequirementUpdate,
    current_user: models.User       = Depends(get_current_user),
    db:           Session           = Depends(get_db),
):
    _check_access(project_id, current_user, db, need_edit=True)

    req = (
        db.query(models.Requirement)
        .options(joinedload(models.Requirement.creator))
        .filter(models.Requirement.id == req_id,
                models.Requirement.project_id == project_id)
        .first()
    )
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Requirement not found")

    changed = []
    if payload.name is not None and payload.name != req.name:
        changed.append(f"nome: '{req.name}' → '{payload.name}'")
        req.name = payload.name
    if payload.description is not None and payload.description != req.description:
        changed.append("descrição atualizada")
        req.description = payload.description
    if payload.type is not None and payload.type != req.type:
        changed.append(f"tipo: {req.type.value} → {payload.type.value}")
        req.type = payload.type
    if payload.status is not None and payload.status != req.status:
        status_labels = {"todo": "A fazer", "in_progress": "Em andamento", "done": "Concluído"}
        old_l = status_labels.get(req.status.value, req.status.value)
        new_l = status_labels.get(payload.status.value, payload.status.value)
        changed.append(f"status: {old_l} → {new_l}")
        req.status = payload.status

    if changed:
        activity_log(
            db, project_id, current_user.id,
            action="Editou requisito",
            object_type=models.ObjectType.requirement,
            object_id=req.id,
            object_name=req.name,
            details="; ".join(changed),
        )
        db.commit()
        db.refresh(req)

        data = _serialize_req(req)
        asyncio.ensure_future(
            sse_manager.broadcast(project_id, "requirement_updated", data)
        )

    return _serialize_req(req)


@router.delete("/{req_id}", status_code=204,
               summary="Delete a requirement (edit permission required)")
async def delete_requirement(
    project_id:   int,
    req_id:       int,
    current_user: models.User = Depends(get_current_user),
    db:           Session     = Depends(get_db),
):
    _check_access(project_id, current_user, db, need_edit=True)

    req = (
        db.query(models.Requirement)
        .filter(models.Requirement.id == req_id,
                models.Requirement.project_id == project_id)
        .first()
    )
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Requirement not found")

    req_name = req.name
    req_id_val = req.id

    activity_log(
        db, project_id, current_user.id,
        action="Deletou requisito",
        object_type=models.ObjectType.requirement,
        object_id=req_id_val,
        object_name=req_name,
    )
    db.delete(req)
    db.commit()

    asyncio.ensure_future(
        sse_manager.broadcast(project_id, "requirement_deleted",
                              {"id": req_id_val, "project_id": project_id})
    )
    return Response(status_code=204)
