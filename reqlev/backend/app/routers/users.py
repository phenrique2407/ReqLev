"""ReqLev – Users Router: /api/users/*"""

from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user
from ..schemas import UserSearch
from .. import models

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/search", response_model=List[UserSearch],
            summary="Search registered users by email or username")
def search_users(
    q:            str            = Query(..., min_length=1, description="Search term (email or username)"),
    current_user: models.User   = Depends(get_current_user),
    db:           Session       = Depends(get_db),
):
    """
    Returns up to 20 users whose username OR email contains the search term.
    The calling user is excluded from results.
    """
    term = f"%{q.strip()}%"
    users = (
        db.query(models.User)
        .filter(
            models.User.id != current_user.id,
            (models.User.username.ilike(term)) | (models.User.email.ilike(term)),
        )
        .limit(20)
        .all()
    )
    return users
