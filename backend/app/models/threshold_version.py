"""
Threshold Version Model

Tracks historical similarity thresholds for point-in-time evaluation
"""
from sqlalchemy import Column, String, Float, DateTime, Integer, Text
from sqlalchemy.sql import func
from datetime import datetime

from app.database.base import Base


class ThresholdVersion(Base):
    """
    Threshold versions table

    Records changes to similarity threshold over time

    Why this matters:
    When analyzing cache performance, you need to know:
    "Which threshold was active when this decision happened?"

    This enables:
    - Point-in-time evaluation
    - A/B testing different thresholds
    - Agent-driven threshold optimization
    - Historical performance analysis
    """
    __tablename__ = "threshold_versions"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Threshold value
    threshold_value = Column(Float, nullable=False, index=True)

    # Change metadata
    reason = Column(Text, nullable=True)  # Why this threshold was chosen
    created_by = Column(String(100), nullable=True)  # "manual", "agent:threshold_optimizer", etc.

    # Validity period
    active_from = Column(DateTime(timezone=True), nullable=False, index=True)
    active_until = Column(DateTime(timezone=True), nullable=True, index=True)  # NULL = currently active

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<ThresholdVersion(id={self.id}, value={self.threshold_value}, active_from={self.active_from})>"
