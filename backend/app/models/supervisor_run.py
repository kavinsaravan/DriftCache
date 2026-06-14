"""
Supervisor Run Model

Tracks supervisor agent orchestration workflows
"""
from sqlalchemy import Column, Integer, Float, String, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.database.base import Base


class SupervisorRun(Base):
    """
    Records supervisor workflow executions

    The supervisor coordinates all infrastructure agents
    """
    __tablename__ = "supervisor_runs"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Run metadata
    run_id = Column(String(100), nullable=False, unique=True, index=True)
    trigger_source = Column(String(50), nullable=False)  # alert, scheduled, manual
    trigger_reason = Column(Text, nullable=False)

    # Initial system state
    initial_drift_score = Column(Float, nullable=True)
    initial_drift_severity = Column(String(50), nullable=True)
    initial_precision = Column(Float, nullable=True)
    initial_recall = Column(Float, nullable=True)
    initial_false_hit_rate = Column(Float, nullable=True)
    initial_cache_hit_rate = Column(Float, nullable=True)
    initial_stale_vector_ratio = Column(Float, nullable=True)

    # Diagnosis
    diagnosis = Column(String(100), nullable=False)  # cache_precision_degradation, high_drift, etc.
    diagnosis_details = Column(JSON, nullable=True)

    # Decision path
    decision_path = Column(JSON, nullable=True)  # List of decisions made
    actions_taken = Column(JSON, nullable=True)  # List of actions executed

    # Agents invoked
    threshold_optimizer_run_id = Column(Integer, nullable=True)
    index_rebuild_job_id = Column(Integer, nullable=True)
    cache_invalidation_count = Column(Integer, nullable=True)

    # Final system state
    final_precision = Column(Float, nullable=True)
    final_recall = Column(Float, nullable=True)
    final_false_hit_rate = Column(Float, nullable=True)
    final_drift_score = Column(Float, nullable=True)

    # Validation
    validation_passed = Column(String(50), nullable=True)  # passed, failed, partial
    validation_details = Column(JSON, nullable=True)

    # Status
    final_status = Column(String(50), nullable=False)  # resolved, partial, failed, no_action
    status_reason = Column(Text, nullable=True)

    # Report
    report_summary = Column(Text, nullable=True)
    recommendations = Column(JSON, nullable=True)

    # Execution metrics
    total_execution_time_ms = Column(Float, nullable=True)
    agents_invoked_count = Column(Integer, nullable=True)

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
            f"<SupervisorRun(id={self.id}, "
            f"run_id={self.run_id}, "
            f"diagnosis={self.diagnosis}, "
            f"final_status={self.final_status})>"
        )

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "trigger_source": self.trigger_source,
            "trigger_reason": self.trigger_reason,
            "initial_state": {
                "drift_score": self.initial_drift_score,
                "drift_severity": self.initial_drift_severity,
                "precision": self.initial_precision,
                "recall": self.initial_recall,
                "false_hit_rate": self.initial_false_hit_rate,
                "cache_hit_rate": self.initial_cache_hit_rate,
                "stale_vector_ratio": self.initial_stale_vector_ratio,
            },
            "diagnosis": self.diagnosis,
            "diagnosis_details": self.diagnosis_details,
            "decision_path": self.decision_path,
            "actions_taken": self.actions_taken,
            "agents_invoked": {
                "threshold_optimizer_run_id": self.threshold_optimizer_run_id,
                "index_rebuild_job_id": self.index_rebuild_job_id,
                "cache_invalidation_count": self.cache_invalidation_count,
            },
            "final_state": {
                "precision": self.final_precision,
                "recall": self.final_recall,
                "false_hit_rate": self.final_false_hit_rate,
                "drift_score": self.final_drift_score,
            },
            "validation": {
                "passed": self.validation_passed,
                "details": self.validation_details,
            },
            "final_status": self.final_status,
            "status_reason": self.status_reason,
            "report_summary": self.report_summary,
            "recommendations": self.recommendations,
            "execution": {
                "total_time_ms": self.total_execution_time_ms,
                "agents_invoked": self.agents_invoked_count,
            },
            "tenant_id": self.tenant_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
        }
