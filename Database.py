"""
database.py
-----------
Sets up the SQLAlchemy engine and session factory.

- Uses PostgreSQL if DATABASE_URL is set in .env
- Automatically falls back to SQLite for local dev

Usage:
    from app.database import get_db, engine, Base
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings


# SQLite needs a special connect_args to work with FastAPI's threads
connect_args = {}
db_url = settings.database_url
if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(db_url, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """All SQLAlchemy models inherit from this."""
    pass


def get_db():
    """
    FastAPI dependency — yields a DB session per request,
    closes it automatically when the request finishes.

    Usage in a route:
        @router.get("/jobs")
        def list_jobs(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()