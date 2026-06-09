"""ReqLev – Database Engine & Session Factory"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

# Read DATABASE_URL at call time so test env override works
def _get_url():
    return os.environ.get(
        "DATABASE_URL",
        "mysql+pymysql://root:@localhost:3306/reqlev"
    )

def _make_engine():
    url = _get_url()
    if url.startswith("sqlite"):
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_size=10,
        max_overflow=20,
    )

# Module-level engine – built once when module is first imported.
# Tests override DATABASE_URL *before* importing this module, so
# the correct engine is built from the start.
engine = _make_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables if they don't exist."""
    from . import models  # noqa: F401 – ensure models are registered
    Base.metadata.create_all(bind=engine)
