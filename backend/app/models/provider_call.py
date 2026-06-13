"""
Provider Call Model

Records actual LLM provider calls for cost tracking and analysis
"""
from sqlalchemy import Column, String, Integer, Float, DateTime
from sqlalchemy.sql import func
from datetime import datetime

from app.database.base import Base


class ProviderCall(Base):
    """
    Provider calls table

    ONLY records requests that actually went to an LLM provider

    Key insight:
    - Cache HIT = NO provider_call row created
    - Cache MISS = provider_call row created

    This proves cost savings by comparing:
    - Total requests (requests table)
    - Actual LLM calls (provider_calls table)
    - Savings = requests - provider_calls
    """
    __tablename__ = "provider_calls"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Request linkage
    request_id = Column(String(36), nullable=False, index=True)

    # Provider information
    provider = Column(String(50), nullable=False, index=True)  # "openai", "anthropic", "ollama"
    model = Column(String(100), nullable=False, index=True)

    # Token usage
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)

    # Cost estimation
    estimated_cost = Column(Float, nullable=True)  # USD
    cost_currency = Column(String(3), default="USD")

    # Performance
    latency_ms = Column(Float, nullable=True)  # Provider response time

    # Context
    tenant_id = Column(String(100), nullable=False, index=True)
    user_id = Column(String(100), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<ProviderCall(id={self.id}, provider={self.provider}, model={self.model}, tokens={self.total_tokens})>"
