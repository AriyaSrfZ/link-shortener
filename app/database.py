"""
Database engine and session management.
SQLite is the default (zero-config, single file, fits a local service).
To move to PostgreSQL later: change DATABASE_URL in .env to something like
postgresql://user:pass@host:5432/dbname and add psycopg2-binary to requirements.txt.
No other code in this project needs to change.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

connect_args = {}
if settings.database_url.startswith("sqlite"):
    # Needed for SQLite when accessed from multiple threads (FastAPI's default).
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
