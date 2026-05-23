"""
SQLAlchemy ORM model for generation records.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class GenerationRecord(Base):
    __tablename__ = "generation_records"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(64), nullable=False, index=True)
    topic = Column(String, nullable=False)
    language = Column(String, nullable=False)
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )
    generation_time_sec = Column(Float, nullable=True)
    iteration_count = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    total_cost_usd = Column(Float, nullable=True)
    roadmap_json = Column(JSON, nullable=False)
    raw_content_chars = Column(Integer, nullable=True)
    cleaned_content_chars = Column(Integer, nullable=True)
    content_map_json = Column(JSON, nullable=True)
    content_order_json = Column(JSON, nullable=True)
    content_failed_nodes_json = Column(JSON, nullable=True)


class User(Base):
    __tablename__ = "users"

    user_id = Column(String(64), primary_key=True)
    password_hash = Column(String(128), nullable=False)
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    token = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )
    expires_at = Column(DateTime, nullable=False, index=True)
