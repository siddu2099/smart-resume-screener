"""Database infrastructure, engine setup, and session management."""

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Database connection URL from environment or default SQLite DB
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./resume_screener.db")

# Create engine (connect_args only needed for SQLite)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Declarative base class for ORM models
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(engine_override=None) -> None:
    """Explicitly create database tables.

    Import all models first to register them with Base.metadata.
    """
    import app.models  # noqa: F401

    target_engine = engine_override or engine
    Base.metadata.create_all(bind=target_engine)
