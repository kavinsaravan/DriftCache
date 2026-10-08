"""
Drift Alert Model

Tracks semantic drift detection results over time
"""
from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, Text, JSON
from sqlalchemy.sql import func
from app.database.base import Base


class DriftAlert(Base):
    """
    Records drift detection results

    Tracks shifts in cache-similarity distributions that may indicate
    changing traffic or matching behavior
    """
    __tablename__ = "drift_alerts"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Overall drift assessment
    drift_score = Column(Float, nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)  # low, medium, high, critical

    # Statistical signals
    centroid_shift = Column(Float, nullable=False)
    variance_shift = Column(Float, nullable=False)
    ks_p_value = Column(Float, nullable=True)  # Kolmogorov-Smirnov test p-value
    wasserstein_distance = Column(Float, nullable=True)
    drift_detected = Column(Boolean, nullable=False, default=False, index=True)
    reasons = Column(JSON, nullable=True)

    # Similarity metrics
    avg_similarity_recent = Column(Float, nullable=True)
    avg_similarity_reference = Column(Float, nullable=True)
    similarity_drop = Column(Float, nullable=True)

    # Cache performance correlation
    cache_hit_rate_recent = Column(Float, nullable=True)
    cache_hit_rate_reference = Column(Float, nullable=True)
    hit_rate_drop = Column(Float, nullable=True)

    # Window metadata
    reference_window_start = Column(DateTime(timezone=True), nullable=False)
    reference_window_end = Column(DateTime(timezone=True), nullable=False)
    reference_sample_size = Column(Integer, nullable=False)

    recent_window_start = Column(DateTime(timezone=True), nullable=False)
    recent_window_end = Column(DateTime(timezone=True), nullable=False)
    recent_sample_size = Column(Integer, nullable=False)

    # Recommendations
    recommended_action = Column(String(100), nullable=True)
    action_details = Column(Text, nullable=True)

    # Alert lifecycle
    is_resolved = Column(Boolean, default=False, nullable=False, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_notes = Column(Text, nullable=True)

    # Tenant isolation
    tenant_id = Column(String(100), nullable=True, index=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    def __repr__(self):
        return f"<DriftAlert(id={self.id}, score={self.drift_score:.3f}, severity={self.severity})>"
