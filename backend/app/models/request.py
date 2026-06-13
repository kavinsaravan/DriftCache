"""
Request Model

Stores every incoming user request for historical analysis
"""
from sqlalchemy import Column, String, Text, Boolean, DateTime, JSON, Integer
from sqlalchemy.sql import func
from datetime import datetime

from app.database.base import Base


class Request(Base):
    """
    Request table

    Records all incoming API requests for observability and drift detection
    """
    __tablename__ = "requests"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Request identification
    request_id = Column(String(36), unique=True, nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True, default="default")

    # Model and configuration
    model = Column(String(100), nullable=False, index=True)
    stream = Column(Boolean, default=False)

    # Prompt data
    messages_json = Column(JSON, nullable=False)  # Full message array
    prompt_text = Column(Text, nullable=False)  # Extracted user prompt
    prompt_hash = Column(String(64), nullable=False, index=True)  # SHA256 hash
    system_prompt = Column(Text, nullable=True)

    # User context
    user_id = Column(String(100), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Request(id={self.id}, request_id={self.request_id[:8]}..., model={self.model})>"
