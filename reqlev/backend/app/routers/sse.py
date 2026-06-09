"""ReqLev – SSE Router: /api/sse/*

Provides a Server-Sent Events stream per project so every connected browser
tab receives live updates without polling or page refresh.

The token is passed as a query parameter because the browser's native
EventSource API does not support custom HTTP headers.
"""

import asyncio
from typing import Dict, Set

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user_from_query
from ..sse_manager import sse_manager
from .. import models

router = APIRouter(prefix="/api/sse", tags=["Real-time SSE"])

# ── In-memory editing state ───────────────────────────────────────────────────
# Maps project_id → {req_id → {user_id: username}}
_editing: Dict[int, Dict[int, Dict[int, str]]] = {}


def _get_editing_state(project_id: int) -> dict:
    return {
        str(req_id): list(users.values())
        for req_id, users in _editing.get(project_id, {}).items()
    }


# ── SSE Stream ────────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}",
            summary="Open SSE stream for a project (pass ?token= for auth)")
async def project_stream(
    project_id:   int,
    request:      Request,
    current_user: models.User = Depends(get_current_user_from_query),
    db:           Session     = Depends(get_db),
):
    """
    Long-lived SSE connection. Events emitted:
      connected            – initial handshake with project_id
      project_updated      – project metadata changed
      project_deleted      – project was deleted
      requirement_created  – new requirement added
      requirement_updated  – requirement edited
      requirement_deleted  – requirement removed
      permission_added     – new collaborator
      permission_removed   – collaborator removed
      editing_start        – user started editing a requirement
      editing_stop         – user stopped editing a requirement
      heartbeat (comment)  – keep-alive every 30 s
    """
    # Verify access
    proj = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not proj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    is_owner = proj.owner_id == current_user.id
    has_perm = (
        db.query(models.ProjectPermission)
        .filter_by(project_id=project_id, user_id=current_user.id)
        .first()
    )
    if not is_owner and not has_perm:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")

    queue = sse_manager.connect(project_id)

    return StreamingResponse(
        sse_manager.stream(project_id, queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control":              "no-cache",
            "X-Accel-Buffering":          "no",     # for nginx
            "Access-Control-Allow-Origin": "*",
        },
    )


# ── Editing indicators ────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/editing/start",
             summary="Signal that the current user started editing a requirement")
async def editing_start(
    project_id:    int,
    requirement_id: int,
    current_user:  models.User = Depends(get_current_user_from_query),
    db:            Session     = Depends(get_db),
):
    if project_id not in _editing:
        _editing[project_id] = {}
    if requirement_id not in _editing[project_id]:
        _editing[project_id][requirement_id] = {}
    _editing[project_id][requirement_id][current_user.id] = current_user.username

    await sse_manager.broadcast(project_id, "editing_start", {
        "requirement_id": requirement_id,
        "user_id":        current_user.id,
        "username":       current_user.username,
    })
    return {"ok": True}


@router.post("/projects/{project_id}/editing/stop",
             summary="Signal that the current user stopped editing a requirement")
async def editing_stop(
    project_id:    int,
    requirement_id: int,
    current_user:  models.User = Depends(get_current_user_from_query),
    db:            Session     = Depends(get_db),
):
    try:
        del _editing[project_id][requirement_id][current_user.id]
        if not _editing[project_id][requirement_id]:
            del _editing[project_id][requirement_id]
        if not _editing[project_id]:
            del _editing[project_id]
    except KeyError:
        pass

    await sse_manager.broadcast(project_id, "editing_stop", {
        "requirement_id": requirement_id,
        "user_id":        current_user.id,
    })
    return {"ok": True}


@router.get("/projects/{project_id}/editing",
            summary="Get current editing state for a project")
def get_editing(
    project_id:   int,
    current_user: models.User = Depends(get_current_user_from_query),
    db:           Session     = Depends(get_db),
):
    return _get_editing_state(project_id)
