"""Tests for node-progress persistence (DB layer).

Covers the datetime serialization boundary, the update/load round-trip,
user scoping + demo guard, and the lightweight startup migration.
"""
import os
import tempfile

# Bind the DB to a throwaway file BEFORE importing any coursegen.db module — the
# module-level engine reads DATABASE_URL at import time. Forced (not setdefault)
# so the destructive drop_all/create_all in the fixture can never hit a real DB.
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"

from datetime import datetime  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import inspect, text  # noqa: E402

from coursegen.db import crud  # noqa: E402
from coursegen.db.database import _add_missing_columns, engine  # noqa: E402
from coursegen.db.models import Base  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    """Give each test a clean schema (with the new column)."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    _add_missing_columns()
    yield
    Base.metadata.drop_all(engine)


def _make_record(user_id: str = "alice") -> str:
    return crud.save_generation(
        user_id=user_id,
        topic="X",
        language="zh-TW",
        roadmap={"topic": "X", "nodes": [{"id": "a", "type": "concept"}]},
    )


# ── serialization boundary ────────────────────────────────────────────────

def test_serialize_roundtrips_datetimes():
    now = datetime(2026, 5, 30, 12, 0, 0)
    progress = {"a": {"status": "completed", "completed_at": now, "notes": "x"}}

    raw = crud._serialize_node_progress(progress)
    assert raw["a"]["completed_at"] == now.isoformat()  # stored as a string
    assert isinstance(raw["a"]["completed_at"], str)

    restored = crud._deserialize_node_progress(raw)
    assert restored["a"]["completed_at"] == now  # back to a datetime
    assert restored["a"]["status"] == "completed"
    assert restored["a"]["notes"] == "x"


def test_deserialize_none_returns_empty():
    assert crud._deserialize_node_progress(None) == {}
    assert crud._deserialize_node_progress({}) == {}


def test_deserialize_tolerates_bad_timestamp():
    restored = crud._deserialize_node_progress({"a": {"started_at": "not-a-date"}})
    assert restored["a"]["started_at"] is None


# ── DB round-trip ─────────────────────────────────────────────────────────

def test_fresh_record_has_empty_progress():
    rid = _make_record()
    assert crud.load_generation(rid, user_id="alice")["node_progress"] == {}


def test_update_and_load_roundtrip():
    rid = _make_record()
    now = datetime(2026, 5, 30, 9, 30, 0)
    progress = {"a": {"status": "completed", "completed_at": now}}

    assert crud.update_node_progress(rid, progress, user_id="alice") is True

    loaded = crud.load_generation(rid, user_id="alice")["node_progress"]
    assert loaded["a"]["status"] == "completed"
    assert loaded["a"]["completed_at"] == now  # survived JSON persistence


# ── guards & scoping ──────────────────────────────────────────────────────

def test_update_rejects_example_user():
    with pytest.raises(PermissionError):
        crud.update_node_progress("any", {}, user_id="example")


def test_update_missing_record_returns_false():
    assert crud.update_node_progress("nope", {}, user_id="alice") is False


def test_update_scoped_to_owner():
    rid = _make_record(user_id="alice")
    # bob must not be able to write to alice's record
    assert (
        crud.update_node_progress(rid, {"a": {"status": "completed"}}, user_id="bob")
        is False
    )
    assert crud.load_generation(rid, user_id="alice")["node_progress"] == {}


# ── migration ─────────────────────────────────────────────────────────────

def test_migration_adds_column_to_legacy_table():
    # Simulate an older DB whose generation_records table predates the column.
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE generation_records ("
                "id VARCHAR PRIMARY KEY, user_id VARCHAR, topic VARCHAR, "
                "language VARCHAR, created_at DATETIME, roadmap_json JSON)"
            )
        )
    cols = {c["name"] for c in inspect(engine).get_columns("generation_records")}
    assert "node_progress_json" not in cols

    _add_missing_columns()
    cols = {c["name"] for c in inspect(engine).get_columns("generation_records")}
    assert "node_progress_json" in cols

    _add_missing_columns()  # idempotent — must not raise
