"""
Database engine, session factory, and initialization.
"""
import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from coursegen.db.models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/coursegen.db")

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Create all tables (idempotent)."""
    # Ensure the directory for SQLite file exists
    if DATABASE_URL.startswith("sqlite:///") and not DATABASE_URL.startswith(
        "sqlite:////"
    ):
        db_path = DATABASE_URL.replace("sqlite:///", "")
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
    Base.metadata.create_all(engine)


@contextmanager
def get_session():
    """Yield a session that auto-closes, suitable for Streamlit re-runs."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
