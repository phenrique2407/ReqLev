"""ReqLev – Authentication: JWT creation, verification, and current-user dependency"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from . import models

# ── Crypto helpers ───────────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[int]:
    """Return user_id from a valid token, or None on any error."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        uid = payload.get("sub")
        if uid is None:
            return None
        return int(uid)
    except (JWTError, ValueError):
        return None


# ── FastAPI dependencies ──────────────────────────────────────────────────────

def _get_user_from_token(token: str, db: Session) -> models.User:
    """Shared logic: decode token and fetch user, raising 401 on failure."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user_id = decode_token(token)
    if user_id is None:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user


def get_current_user(
    token: str   = Depends(oauth2_scheme),
    db:    Session = Depends(get_db),
) -> models.User:
    """Dependency: returns authenticated user from Authorization header."""
    return _get_user_from_token(token, db)


def get_current_user_from_query(
    token: str   = Query(..., description="JWT bearer token"),
    db:    Session = Depends(get_db),
) -> models.User:
    """Dependency: returns authenticated user from ?token= query parameter (used for SSE)."""
    return _get_user_from_token(token, db)
