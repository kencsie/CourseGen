"""
Database engine, session factory, and initialization.
"""
import os
from contextlib import contextmanager

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from coursegen.db.models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/coursegen.db")

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)


def _add_missing_columns():
    """Additively patch columns added after a table was first created.

    The project has no migration framework; create_all() creates new tables but
    never ALTERs existing ones. We patch known new columns on startup so older
    SQLite files keep working. Idempotent.
    """
    cols = {c["name"] for c in inspect(engine).get_columns("generation_records")}
    if "node_progress_json" not in cols:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE generation_records "
                    "ADD COLUMN node_progress_json JSON"
                )
            )


def init_db():
    """Create all tables (idempotent) and seed example user."""
    # Ensure the directory for SQLite file exists
    if DATABASE_URL.startswith("sqlite:///") and not DATABASE_URL.startswith(
        "sqlite:////"
    ):
        db_path = DATABASE_URL.replace("sqlite:///", "")
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
    Base.metadata.create_all(engine)
    _add_missing_columns()

    # Seed reference roadmaps for 'example' user (no-op if already seeded)
    from coursegen.db.seed import seed_example_user

    with get_session() as session:
        seed_example_user(session)


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
