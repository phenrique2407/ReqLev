"""ReqLev – Activities Router: /api/projects/{id}/activities"""

from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..auth import get_current_user
from ..schemas import ActivityLogOut
from .. import models

router = APIRouter(prefix="/api/projects/{project_id}/activities",
                   tags=["Activities"])


def _has_access(project_id: int, user: models.User, db: Session) -> bool:
    proj = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not proj:
        return False
    if proj.owner_id == user.id:
        return True
    perm = (
        db.query(models.ProjectPermission)
        .filter_by(project_id=project_id, user_id=user.id)
        .first()
    )
    return perm is not None


@router.get("", response_model=List[ActivityLogOut],
            summary="Get activity log for a project (all users with access can see it)")
def get_activities(
    project_id:   int,
    limit:        int         = Query(100, ge=1, le=500),
    offset:       int         = Query(0,   ge=0),
    current_user: models.User = Depends(get_current_user),
    db:           Session     = Depends(get_db),
):
    from fastapi import HTTPException, status
    if not _has_access(project_id, current_user, db):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")

    logs = (
        db.query(models.ActivityLog)
        .options(joinedload(models.ActivityLog.user))
        .filter(models.ActivityLog.project_id == project_id)
        .order_by(models.ActivityLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return logs
