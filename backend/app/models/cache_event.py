"""
Cache Event Model

Records every cache decision for analytics and drift detection
"""
from sqlalchemy import Column, String, Float, DateTime, Integer, Enum as SQLEnum
from sqlalchemy.sql import func
from datetime import datetime
import enum

from app.database.base import Base


class CacheStatus(str, enum.Enum):
    """Cache decision status"""
    HIT = "HIT"
    MISS = "MISS"
    EXPIRED = "EXPIRED"
    THRESHOLD_NOT_MET = "THRESHOLD_NOT_MET"
    MODEL_MISMATCH = "MODEL_MISMATCH"
    SYSTEM_MISMATCH = "SYSTEM_MISMATCH"
    BYPASS = "BYPASS"
    ERROR = "ERROR"


class CacheEvent(Base):
    """
    Cache events table

    CRITICAL TABLE: Records every cache decision

    This enables:
    - Cache hit rate analysis
    - Similarity score drift detection
    - Threshold optimization
    - Latency tracking
    - False hit investigation
    """
    __tablename__ = "cache_events"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Request linkage
    request_id = Column(String(36), nullable=False, index=True)

    # Cache decision
    cache_status = Column(
        SQLEnum(CacheStatus),
        nullable=False,
        index=True
    )

    # Match information
    matched_cache_id = Column(String(36), nullable=True, index=True)  # NULL for misses
    similarity_score = Column(Float, nullable=True)  # NULL for misses

    # Decision parameters
    threshold_used = Column(Float, nullable=False)  # Threshold at time of decision
    threshold_version_id = Column(Integer, nullable=True)  # Link to threshold_versions

    # Performance metrics
    latency_ms = Column(Float, nullable=True)  # Cache lookup latency
    retrieval_source = Column(String(20), nullable=True)  # "redis" or "legacy"

    # Context
    tenant_id = Column(String(100), nullable=False, index=True)
    model = Column(String(100), nullable=False, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<CacheEvent(id={self.id}, status={self.cache_status.value}, similarity={self.similarity_score})>"
