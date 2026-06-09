"""ReqLev – Auth Router: /api/auth/*"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import hash_password, verify_password, create_access_token, get_current_user
from ..schemas import UserRegister, UserLogin, Token, UserOut
from .. import models

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=Token, status_code=201,
             summary="Register a new user account")
def register(payload: UserRegister, db: Session = Depends(get_db)):
    """Create a new user. Returns a JWT token ready for immediate use."""
    # Uniqueness checks
    if db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    if db.query(models.User).filter(models.User.username == payload.username).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")

    user = models.User(
        username      = payload.username,
        email         = payload.email,
        password_hash = hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return Token(access_token=token)


@router.post("/login", response_model=Token,
             summary="Log in with email + password")
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """Authenticate and receive a JWT token (no automatic expiry)."""
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    token = create_access_token(user.id)
    return Token(access_token=token)


@router.get("/me", response_model=UserOut,
            summary="Get current authenticated user")
def me(current_user: models.User = Depends(get_current_user)):
    return current_user
