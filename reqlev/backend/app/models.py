"""ReqLev – SQLAlchemy ORM Models

Tables:
    users               – registered accounts
    projects            – projects owned by users
    project_permissions – shared access control (view | edit)
    requirements        – requirements within each project
    activity_logs       – immutable audit trail
"""

import enum
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey,
    Enum as SAEnum, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


# ── Enumerations ────────────────────────────────────────────────────────────

class PermissionLevel(str, enum.Enum):
    view = "view"
    edit = "edit"


class RequirementType(str, enum.Enum):
    RF  = "RF"
    RNF = "RNF"


class RequirementStatus(str, enum.Enum):
    todo        = "todo"
    in_progress = "in_progress"
    done        = "done"


class ObjectType(str, enum.Enum):
    project     = "project"
    requirement = "requirement"


# ── ORM Models ───────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    username      = Column(String(50),  unique=True, nullable=False, index=True)
    email         = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at    = Column(DateTime, server_default=func.now())

    # relationships
    owned_projects      = relationship("Project",           back_populates="owner",
                                       foreign_keys="Project.owner_id")
    project_permissions = relationship("ProjectPermission", back_populates="user",
                                       cascade="all, delete-orphan")
    activity_logs       = relationship("ActivityLog",       back_populates="user")

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"


class Project(Base):
    __tablename__ = "projects"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(100), nullable=False)
    description = Column(Text,        nullable=True)
    owner_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at  = Column(DateTime, server_default=func.now())
    updated_at  = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # relationships
    owner        = relationship("User",              foreign_keys=[owner_id],
                                back_populates="owned_projects")
    requirements = relationship("Requirement",       back_populates="project",
                                cascade="all, delete-orphan", order_by="Requirement.id")
    permissions  = relationship("ProjectPermission", back_populates="project",
                                cascade="all, delete-orphan")
    activity_logs = relationship("ActivityLog",      back_populates="project",
                                 cascade="all, delete-orphan",
                                 order_by="ActivityLog.created_at.desc()")

    def __repr__(self) -> str:
        return f"<Project id={self.id} name={self.name!r}>"


class ProjectPermission(Base):
    __tablename__ = "project_permissions"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_user"),
    )

    id         = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id    = Column(Integer, ForeignKey("users.id",    ondelete="CASCADE"), nullable=False)
    permission = Column(SAEnum(PermissionLevel), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    # relationships
    project = relationship("Project", back_populates="permissions")
    user    = relationship("User",    back_populates="project_permissions")

    def __repr__(self) -> str:
        return f"<ProjectPermission project={self.project_id} user={self.user_id} perm={self.permission}>"


class Requirement(Base):
    __tablename__ = "requirements"

    id          = Column(Integer, primary_key=True, index=True)
    project_id  = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name        = Column(String(200), nullable=False)
    description = Column(Text,        nullable=True)
    type        = Column(SAEnum(RequirementType),   nullable=False)
    status      = Column(SAEnum(RequirementStatus), nullable=False,
                         default=RequirementStatus.todo)
    created_by  = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at  = Column(DateTime, server_default=func.now())
    updated_at  = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # relationships
    project = relationship("Project", back_populates="requirements")
    creator = relationship("User",    foreign_keys=[created_by])

    def __repr__(self) -> str:
        return f"<Requirement id={self.id} name={self.name!r} type={self.type}>"


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id          = Column(Integer, primary_key=True, index=True)
    project_id  = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id     = Column(Integer, ForeignKey("users.id",    ondelete="SET NULL"), nullable=True)
    action      = Column(String(100), nullable=False)
    object_type = Column(SAEnum(ObjectType), nullable=False)
    object_id   = Column(Integer, nullable=True)
    object_name = Column(String(200), nullable=True)
    details     = Column(Text, nullable=True)
    created_at  = Column(DateTime, server_default=func.now())

    # relationships
    project = relationship("Project", back_populates="activity_logs")
    user    = relationship("User",    back_populates="activity_logs")

    def __repr__(self) -> str:
        return f"<ActivityLog id={self.id} action={self.action!r}>"
