"""ReqLev – Activity Log Service

Central helper used by every router to record actions.
"""

from sqlalchemy.orm import Session
from . import models


def log(
    db:          Session,
    project_id:  int,
    user_id:     int,
    action:      str,
    object_type: models.ObjectType,
    object_id:   int | None     = None,
    object_name: str | None     = None,
    details:     str | None     = None,
) -> models.ActivityLog:
    """Create and persist an ActivityLog entry; returns the new record."""
    entry = models.ActivityLog(
        project_id  = project_id,
        user_id     = user_id,
        action      = action,
        object_type = object_type,
        object_id   = object_id,
        object_name = object_name,
        details     = details,
    )
    db.add(entry)
    db.flush()   # assigns entry.id inside current transaction
    return entry
