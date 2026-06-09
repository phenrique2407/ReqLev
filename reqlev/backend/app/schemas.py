"""ReqLev – Pydantic Schemas (Request / Response validation)"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, field_validator, ConfigDict
from .models import PermissionLevel, RequirementType, RequirementStatus


# ── Helpers ──────────────────────────────────────────────────────────────────

class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Auth ─────────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    username: str
    email:    EmailStr
    password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 50:
            raise ValueError("Username must be between 3 and 50 characters")
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username may only contain letters, numbers, _ and -")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class UserLogin(BaseModel):
    email:    EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type:   str = "bearer"


class UserOut(OrmModel):
    id:         int
    username:   str
    email:      str
    created_at: datetime


class UserSearch(OrmModel):
    id:       int
    username: str
    email:    str


# ── Projects ─────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name:        str
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Project name cannot be empty")
        if len(v) > 100:
            raise ValueError("Project name must be ≤ 100 characters")
        return v


class ProjectUpdate(BaseModel):
    name:        Optional[str] = None
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Project name cannot be empty")
            if len(v) > 100:
                raise ValueError("Project name must be ≤ 100 characters")
        return v


class ProjectOut(OrmModel):
    id:          int
    name:        str
    description: Optional[str]
    owner_id:    int
    created_at:  datetime
    updated_at:  datetime
    owner:       UserOut
    user_permission: Optional[str] = None  # injected after query


class ProjectSummary(OrmModel):
    id:              int
    name:            str
    description:     Optional[str]
    owner_id:        int
    created_at:      datetime
    updated_at:      datetime
    owner:           UserOut
    user_permission: Optional[str] = None
    requirement_count: int = 0


# ── Permissions ───────────────────────────────────────────────────────────────

class ShareProject(BaseModel):
    user_id:    int
    permission: PermissionLevel


class PermissionOut(OrmModel):
    id:         int
    project_id: int
    user_id:    int
    permission: PermissionLevel
    created_at: datetime
    user:       UserOut


class UpdatePermission(BaseModel):
    permission: PermissionLevel


# ── Requirements ─────────────────────────────────────────────────────────────

class RequirementCreate(BaseModel):
    name:        str
    description: Optional[str] = None
    type:        RequirementType
    status:      RequirementStatus = RequirementStatus.todo

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Requirement name cannot be empty")
        if len(v) > 200:
            raise ValueError("Requirement name must be ≤ 200 characters")
        return v


class RequirementUpdate(BaseModel):
    name:        Optional[str] = None
    description: Optional[str] = None
    type:        Optional[RequirementType] = None
    status:      Optional[RequirementStatus] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Requirement name cannot be empty")
            if len(v) > 200:
                raise ValueError("Requirement name must be ≤ 200 characters")
        return v


class RequirementOut(OrmModel):
    id:          int
    project_id:  int
    name:        str
    description: Optional[str]
    type:        RequirementType
    status:      RequirementStatus
    created_by:  Optional[int]
    created_at:  datetime
    updated_at:  datetime
    creator:     Optional[UserOut] = None


# ── Activities ────────────────────────────────────────────────────────────────

class ActivityLogOut(OrmModel):
    id:          int
    project_id:  int
    user_id:     Optional[int]
    action:      str
    object_type: str
    object_id:   Optional[int]
    object_name: Optional[str]
    details:     Optional[str]
    created_at:  datetime
    user:        Optional[UserOut] = None


# ── SSE editing state ─────────────────────────────────────────────────────────

class EditingNotification(BaseModel):
    requirement_id: Optional[int] = None
    project_id:     Optional[int] = None
