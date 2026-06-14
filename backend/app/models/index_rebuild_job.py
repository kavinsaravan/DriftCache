"""
Index Rebuild Job Model

Tracks FAISS index rebuild operations
"""
from sqlalchemy import Column, Integer, Float, String, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.database.base import Base


class IndexRebuildJob(Base):
    """
    Records index rebuild job executions

    Maintains complete audit trail of vector infrastructure maintenance
    """
    __tablename__ = "index_rebuild_jobs"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Job metadata
    job_id = Column(String(100), nullable=False, unique=True, index=True)
    status = Column(String(50), nullable=False, index=True)  # pending, running, completed, failed
    trigger_reason = Column(Text, nullable=False)
    trigger_source = Column(String(50), nullable=False)  # agent, manual, scheduled

    # Index versions
    old_index_version_id = Column(Integer, nullable=True)
    new_index_version_id = Column(Integer, nullable=True)
    old_index_version = Column(String(100), nullable=True)
    new_index_version = Column(String(100), nullable=True)

    # Health metrics before rebuild
    old_vector_count = Column(Integer, nullable=True)
    active_cache_count = Column(Integer, nullable=True)
    stale_vector_ratio = Column(Float, nullable=True)
    avg_search_latency_ms = Column(Float, nullable=True)
    index_age_hours = Column(Float, nullable=True)

    # Rebuild results
    new_vector_count = Column(Integer, nullable=True)
    vectors_added = Column(Integer, nullable=True)
    vectors_removed = Column(Integer, nullable=True)
    rebuild_duration_ms = Column(Float, nullable=True)

    # Validation results
    validation_passed = Column(String(50), nullable=True)  # passed, failed, skipped
    validation_details = Column(JSON, nullable=True)
    search_latency_after_ms = Column(Float, nullable=True)
    search_quality_score = Column(Float, nullable=True)

    # Error handling
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)

    # File paths
    old_index_path = Column(String(500), nullable=True)
    new_index_path = Column(String(500), nullable=True)
    backup_path = Column(String(500), nullable=True)

    # Tenant isolation
    tenant_id = Column(String(100), nullable=True, index=True)

    # Timestamps
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )

    def __repr__(self):
        return (
            f"<IndexRebuildJob(id={self.id}, "
            f"job_id={self.job_id}, "
            f"status={self.status})>"
        )

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "job_id": self.job_id,
            "status": self.status,
            "trigger_reason": self.trigger_reason,
            "trigger_source": self.trigger_source,
            "index_versions": {
                "old_version": self.old_index_version,
                "new_version": self.new_index_version,
                "old_version_id": self.old_index_version_id,
                "new_version_id": self.new_index_version_id,
            },
            "health_before": {
                "old_vector_count": self.old_vector_count,
                "active_cache_count": self.active_cache_count,
                "stale_vector_ratio": self.stale_vector_ratio,
                "avg_search_latency_ms": self.avg_search_latency_ms,
                "index_age_hours": self.index_age_hours,
            },
            "rebuild_results": {
                "new_vector_count": self.new_vector_count,
                "vectors_added": self.vectors_added,
                "vectors_removed": self.vectors_removed,
                "rebuild_duration_ms": self.rebuild_duration_ms,
            },
            "validation": {
                "passed": self.validation_passed,
                "details": self.validation_details,
                "search_latency_after_ms": self.search_latency_after_ms,
                "search_quality_score": self.search_quality_score,
            },
            "error": {
                "message": self.error_message,
                "details": self.error_details,
            } if self.error_message else None,
            "file_paths": {
                "old_index": self.old_index_path,
                "new_index": self.new_index_path,
                "backup": self.backup_path,
            },
            "tenant_id": self.tenant_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
        }
