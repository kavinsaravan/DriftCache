"""
Cache Entry Model

Permanent record of all cached responses
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, JSON
from sqlalchemy.sql import func
from datetime import datetime

from app.database.base import Base


class CacheEntry(Base):
    """
    Cache entries table

    Permanent storage of cached prompt-response pairs
    Redis may expire entries, but PostgreSQL keeps the history
    """
    __tablename__ = "cache_entries"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Cache identification
    cache_id = Column(String(36), unique=True, nullable=False, index=True)

    # Prompt data
    prompt_text = Column(Text, nullable=False)
    prompt_hash = Column(String(64), nullable=False, index=True)
    system_prompt = Column(Text, nullable=True)
    system_prompt_hash = Column(String(64), nullable=True, index=True)

    # Response data
    response_text = Column(Text, nullable=False)

    # Model and context
    model = Column(String(100), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True, default="default")
    user_id = Column(String(100), nullable=True, index=True)

    # Request parameters
    request_params = Column(JSON, default={})

    # Cache metadata
    cache_hits = Column(Integer, default=0)  # Number of times reused

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_accessed = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<CacheEntry(id={self.id}, cache_id={self.cache_id[:8]}..., hits={self.cache_hits})>"
