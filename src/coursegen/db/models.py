"""
SQLAlchemy ORM model for generation records.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.types import JSON
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class GenerationRecord(Base):
    __tablename__ = "generation_records"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    topic = Column(String, nullable=False)
    language = Column(String, nullable=False)
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    generation_time_sec = Column(Float, nullable=True)
    iteration_count = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    total_cost_usd = Column(Float, nullable=True)
    roadmap_json = Column(JSON, nullable=False)
    content_map_json = Column(JSON, nullable=True)
    content_order_json = Column(JSON, nullable=True)
    content_failed_nodes_json = Column(JSON, nullable=True)
