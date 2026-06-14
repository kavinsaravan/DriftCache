"""
Threshold Version Model

Tracks historical similarity thresholds for point-in-time evaluation and autonomous optimization
"""
from sqlalchemy import Column, String, Float, DateTime, Integer, Text, Boolean
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

    # Threshold values
    old_threshold = Column(Float, nullable=True)  # Previous threshold value
    threshold_value = Column(Float, nullable=False, index=True)

    # Change metadata
    reason = Column(Text, nullable=True)  # Why this threshold was chosen
    created_by = Column(String(100), nullable=True)  # "manual", "agent:threshold_optimizer", etc.
    optimization_run_id = Column(Integer, nullable=True)  # Link to optimization run

    # Quality metrics before change
    precision_before = Column(Float, nullable=True)
    recall_before = Column(Float, nullable=True)
    false_hit_rate_before = Column(Float, nullable=True)
    false_miss_rate_before = Column(Float, nullable=True)

    # Expected quality metrics after change (from simulation)
    precision_after_estimate = Column(Float, nullable=True)
    recall_after_estimate = Column(Float, nullable=True)
    false_hit_rate_after_estimate = Column(Float, nullable=True)
    false_miss_rate_after_estimate = Column(Float, nullable=True)

    # Validity period
    active_from = Column(DateTime(timezone=True), nullable=False, index=True)
    active_until = Column(DateTime(timezone=True), nullable=True, index=True)  # NULL = currently active

    # Deployment status
    is_active = Column(Boolean, nullable=False, server_default='true')
    deployed_at = Column(DateTime(timezone=True), nullable=True)

    # Tenant isolation
    tenant_id = Column(String(100), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<ThresholdVersion(id={self.id}, value={self.threshold_value}, active_from={self.active_from})>"

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "old_threshold": self.old_threshold,
            "threshold_value": self.threshold_value,
            "reason": self.reason,
            "created_by": self.created_by,
            "optimization_run_id": self.optimization_run_id,
            "metrics_before": {
                "precision": self.precision_before,
                "recall": self.recall_before,
                "false_hit_rate": self.false_hit_rate_before,
                "false_miss_rate": self.false_miss_rate_before,
            },
            "metrics_after_estimate": {
                "precision": self.precision_after_estimate,
                "recall": self.recall_after_estimate,
                "false_hit_rate": self.false_hit_rate_after_estimate,
                "false_miss_rate": self.false_miss_rate_after_estimate,
            },
            "active_from": self.active_from.isoformat(),
            "active_until": self.active_until.isoformat() if self.active_until else None,
            "is_active": self.is_active,
            "deployed_at": self.deployed_at.isoformat() if self.deployed_at else None,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at.isoformat(),
        }
