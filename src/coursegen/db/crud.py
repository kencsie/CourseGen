"""
CRUD operations for generation records.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from coursegen.db.auth import EXAMPLE_USER_ID
from coursegen.db.database import get_session
from coursegen.db.models import GenerationRecord


def save_generation(
    *,
    user_id: str,
    topic: str,
    language: str,
    roadmap: dict,
    content_map: dict | None = None,
    content_order: list[str] | None = None,
    content_failed_nodes: list[str] | None = None,
    generation_time_sec: float | None = None,
    iteration_count: int | None = None,
    total_tokens: int | None = None,
    total_cost_usd: float | None = None,
    raw_content_chars: int | None = None,
    cleaned_content_chars: int | None = None,
) -> str:
    """Save a generation record and return its ID."""
    if user_id == EXAMPLE_USER_ID:
        raise PermissionError("example is a demo user — cannot create records")
    record_id = str(uuid.uuid4())
    record = GenerationRecord(
        id=record_id,
        user_id=user_id,
        topic=topic,
        language=language,
        created_at=datetime.now(UTC),
        generation_time_sec=generation_time_sec,
        iteration_count=iteration_count,
        total_tokens=total_tokens,
        total_cost_usd=total_cost_usd,
        raw_content_chars=raw_content_chars,
        cleaned_content_chars=cleaned_content_chars,
        roadmap_json=roadmap,
        content_map_json=content_map or {},
        content_order_json=content_order or [],
        content_failed_nodes_json=content_failed_nodes or [],
    )
    with get_session() as session:
        session.add(record)
    return record_id


def list_generations(limit: int = 20, *, user_id: str | None) -> list[dict]:
    """Return a summary list of recent generation records.

    Pass user_id='alice' to scope to one user; pass user_id=None to see all
    (admin mode — used by eval CLI only). The keyword-only no-default signature
    forces every call site to make an explicit choice.
    """
    with get_session() as session:
        query = session.query(GenerationRecord).order_by(
            GenerationRecord.created_at.desc()
        )
        if user_id is not None:
            query = query.filter(GenerationRecord.user_id == user_id)
        records = query.limit(limit).all()
        return [
            {
                "id": r.id,
                "topic": r.topic,
                "language": r.language,
                "created_at": r.created_at,
                "node_count": len(r.roadmap_json.get("nodes", []))
                if r.roadmap_json
                else 0,
            }
            for r in records
        ]


def load_generation(record_id: str, *, user_id: str | None) -> dict | None:
    """Load a full generation record by ID.

    user_id semantics match list_generations: explicit value scopes to user,
    explicit None disables the filter (admin).
    """
    with get_session() as session:
        query = session.query(GenerationRecord).filter(
            GenerationRecord.id == record_id
        )
        if user_id is not None:
            query = query.filter(GenerationRecord.user_id == user_id)
        record = query.first()
        if not record:
            return None
        return {
            "id": record.id,
            "topic": record.topic,
            "language": record.language,
            "created_at": record.created_at,
            "generation_time_sec": record.generation_time_sec,
            "iteration_count": record.iteration_count,
            "total_tokens": record.total_tokens,
            "total_cost_usd": record.total_cost_usd,
            "raw_content_chars": record.raw_content_chars,
            "cleaned_content_chars": record.cleaned_content_chars,
            "roadmap": record.roadmap_json,
            "content_map": record.content_map_json or {},
            "content_order": record.content_order_json or [],
            "content_failed_nodes": record.content_failed_nodes_json or [],
        }


def delete_generation(record_id: str, *, user_id: str | None) -> bool:
    """Delete a generation record. Returns True if found and deleted.

    user_id semantics match list_generations.
    """
    if user_id == EXAMPLE_USER_ID:
        raise PermissionError("example is a demo user — cannot delete records")
    with get_session() as session:
        query = session.query(GenerationRecord).filter(
            GenerationRecord.id == record_id
        )
        if user_id is not None:
            query = query.filter(GenerationRecord.user_id == user_id)
        record = query.first()
        if not record:
            return False
        session.delete(record)
        return True
