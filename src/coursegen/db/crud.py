"""
CRUD operations for generation records.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from coursegen.db.database import get_session
from coursegen.db.models import GenerationRecord


def save_generation(
    *,
    topic: str,
    difficulty: str,
    goal: str,
    language: str,
    roadmap: dict,
    content_map: dict | None = None,
    content_order: list[str] | None = None,
    content_failed_nodes: list[str] | None = None,
    generation_time_sec: float | None = None,
    iteration_count: int | None = None,
    total_tokens: int | None = None,
    total_cost_usd: float | None = None,
) -> str:
    """Save a generation record and return its ID."""
    record_id = str(uuid.uuid4())
    record = GenerationRecord(
        id=record_id,
        topic=topic,
        difficulty=difficulty,
        goal=goal,
        language=language,
        created_at=datetime.now(timezone.utc),
        generation_time_sec=generation_time_sec,
        iteration_count=iteration_count,
        total_tokens=total_tokens,
        total_cost_usd=total_cost_usd,
        roadmap_json=roadmap,
        content_map_json=content_map or {},
        content_order_json=content_order or [],
        content_failed_nodes_json=content_failed_nodes or [],
    )
    with get_session() as session:
        session.add(record)
    return record_id


def list_generations(limit: int = 20) -> list[dict]:
    """Return a summary list of recent generation records."""
    with get_session() as session:
        records = (
            session.query(GenerationRecord)
            .order_by(GenerationRecord.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "topic": r.topic,
                "difficulty": r.difficulty,
                "goal": r.goal,
                "language": r.language,
                "created_at": r.created_at,
                "node_count": len(r.roadmap_json.get("nodes", []))
                if r.roadmap_json
                else 0,
            }
            for r in records
        ]


def load_generation(record_id: str) -> dict | None:
    """Load a full generation record by ID."""
    with get_session() as session:
        record = session.get(GenerationRecord, record_id)
        if not record:
            return None
        return {
            "id": record.id,
            "topic": record.topic,
            "difficulty": record.difficulty,
            "goal": record.goal,
            "language": record.language,
            "created_at": record.created_at,
            "generation_time_sec": record.generation_time_sec,
            "iteration_count": record.iteration_count,
            "total_tokens": record.total_tokens,
            "total_cost_usd": record.total_cost_usd,
            "roadmap": record.roadmap_json,
            "content_map": record.content_map_json or {},
            "content_order": record.content_order_json or [],
            "content_failed_nodes": record.content_failed_nodes_json or [],
        }


def delete_generation(record_id: str) -> bool:
    """Delete a generation record. Returns True if found and deleted."""
    with get_session() as session:
        record = session.get(GenerationRecord, record_id)
        if not record:
            return False
        session.delete(record)
        return True
