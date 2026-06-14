"""
Optimization Run Model

Stores threshold optimization execution history and results
"""
from sqlalchemy import Column, Integer, Float, String, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.database.base import Base


class OptimizationRun(Base):
    """
    Records threshold optimization executions

    Each run tests multiple candidate thresholds and selects the best one
    """
    __tablename__ = "optimization_runs"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Run metadata
    run_id = Column(String(100), nullable=False, unique=True, index=True)
    trigger_source = Column(String(50), nullable=False)  # "agent", "manual", "scheduled"

    # Current state before optimization
    old_threshold = Column(Float, nullable=False)
    precision_before = Column(Float, nullable=True)
    recall_before = Column(Float, nullable=True)
    false_hit_rate_before = Column(Float, nullable=True)
    false_miss_rate_before = Column(Float, nullable=True)
    f1_score_before = Column(Float, nullable=True)

    # Optimization result
    new_threshold = Column(Float, nullable=False)
    precision_after_estimate = Column(Float, nullable=True)
    recall_after_estimate = Column(Float, nullable=True)
    false_hit_rate_after_estimate = Column(Float, nullable=True)
    false_miss_rate_after_estimate = Column(Float, nullable=True)
    f1_score_after_estimate = Column(Float, nullable=True)

    # Decision
    decision = Column(String(50), nullable=False)  # "deploy", "no_change", "rejected"
    decision_reason = Column(Text, nullable=False)
    optimization_score = Column(Float, nullable=True)  # Score of selected threshold

    # Candidates tested
    candidates_tested = Column(JSON, nullable=True)  # List of thresholds tested
    candidate_scores = Column(JSON, nullable=True)  # Scores for each candidate

    # Scoring weights used
    precision_weight = Column(Float, nullable=True)
    recall_weight = Column(Float, nullable=True)
    cost_weight = Column(Float, nullable=True)
    latency_weight = Column(Float, nullable=True)

    # Execution details
    dataset_name = Column(String(100), nullable=True)
    dataset_size = Column(Integer, nullable=True)
    execution_time_ms = Column(Float, nullable=True)

    # Safety constraints applied
    constraints_applied = Column(JSON, nullable=True)  # Policy constraints that were checked

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
            f"<OptimizationRun(id={self.id}, "
            f"run_id={self.run_id}, "
            f"old_threshold={self.old_threshold}, "
            f"new_threshold={self.new_threshold})>"
        )

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "trigger_source": self.trigger_source,
            "before": {
                "threshold": self.old_threshold,
                "precision": self.precision_before,
                "recall": self.recall_before,
                "false_hit_rate": self.false_hit_rate_before,
                "false_miss_rate": self.false_miss_rate_before,
                "f1_score": self.f1_score_before,
            },
            "after_estimate": {
                "threshold": self.new_threshold,
                "precision": self.precision_after_estimate,
                "recall": self.recall_after_estimate,
                "false_hit_rate": self.false_hit_rate_after_estimate,
                "false_miss_rate": self.false_miss_rate_after_estimate,
                "f1_score": self.f1_score_after_estimate,
            },
            "decision": self.decision,
            "decision_reason": self.decision_reason,
            "optimization_score": self.optimization_score,
            "candidates_tested": self.candidates_tested,
            "candidate_scores": self.candidate_scores,
            "scoring_weights": {
                "precision": self.precision_weight,
                "recall": self.recall_weight,
                "cost": self.cost_weight,
                "latency": self.latency_weight,
            },
            "execution": {
                "dataset_name": self.dataset_name,
                "dataset_size": self.dataset_size,
                "execution_time_ms": self.execution_time_ms,
            },
            "constraints_applied": self.constraints_applied,
            "tenant_id": self.tenant_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
        }
