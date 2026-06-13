"""
Agent Action Model

Stores autonomous agent decisions and actions for auditability
"""
from sqlalchemy import Column, Integer, Float, String, DateTime, Text, Boolean, JSON
from sqlalchemy.sql import func
from app.database.base import Base


class AgentAction(Base):
    """
    Records agent workflow executions and decisions

    Provides complete audit trail for autonomous infrastructure actions
    """
    __tablename__ = "agent_actions"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Workflow metadata
    workflow_id = Column(String(100), nullable=False, unique=True, index=True)
    workflow_status = Column(String(50), nullable=False, index=True)  # completed, failed
    trigger_type = Column(String(50), nullable=False, index=True)  # manual, scheduled, alert
    execution_time_ms = Column(Float, nullable=True)

    # System state at decision time
    current_threshold = Column(Float, nullable=True)
    cache_hit_rate = Column(Float, nullable=True)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    false_hit_rate = Column(Float, nullable=True)
    false_miss_rate = Column(Float, nullable=True)

    # Analysis results
    drift_severity = Column(String(50), nullable=True, index=True)  # no_drift, moderate, high
    drift_score = Column(Float, nullable=True)
    quality_acceptable = Column(Boolean, nullable=True)

    # Decision
    decision = Column(String(100), nullable=False, index=True)  # no_action, raise_threshold, etc
    decision_reason = Column(Text, nullable=True)
    decision_confidence = Column(Float, nullable=True)

    # Action taken
    action_taken = Column(String(200), nullable=True)
    old_threshold = Column(Float, nullable=True)
    new_threshold = Column(Float, nullable=True)
    action_result = Column(JSON, nullable=True)  # Structured action output

    # Validation
    validation_passed = Column(Boolean, nullable=True)
    validation_summary = Column(Text, nullable=True)
    validation_result = Column(JSON, nullable=True)

    # Report
    report_summary = Column(Text, nullable=True)
    errors = Column(JSON, nullable=True)  # List of error messages
    warnings = Column(JSON, nullable=True)  # List of warnings

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
            f"<AgentAction(id={self.id}, "
            f"workflow_id={self.workflow_id}, "
            f"decision={self.decision})>"
        )

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "workflow_status": self.workflow_status,
            "trigger_type": self.trigger_type,
            "decision": self.decision,
            "decision_reason": self.decision_reason,
            "decision_confidence": self.decision_confidence,
            "action_taken": self.action_taken,
            "old_threshold": self.old_threshold,
            "new_threshold": self.new_threshold,
            "validation_passed": self.validation_passed,
            "validation_summary": self.validation_summary,
            "report_summary": self.report_summary,
            "drift_severity": self.drift_severity,
            "precision": self.precision,
            "recall": self.recall,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time_ms": self.execution_time_ms,
            "errors": self.errors,
            "warnings": self.warnings,
        }
