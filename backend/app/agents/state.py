"""
Agent Workflow State

Defines the state object for LangGraph workflows
"""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class WorkflowStatus(str, Enum):
    """Status of workflow execution"""
    INITIALIZING = "initializing"
    ANALYZING = "analyzing"
    DECIDING = "deciding"
    EXECUTING = "executing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


class ActionDecision(str, Enum):
    """Possible action decisions"""
    NO_ACTION = "no_action"
    RAISE_THRESHOLD = "raise_threshold"
    LOWER_THRESHOLD = "lower_threshold"
    INVALIDATE_RISKY_CACHE = "invalidate_risky_cache"
    SCHEDULE_INDEX_REBUILD = "schedule_index_rebuild"
    RUN_MORE_EVALUATION = "run_more_evaluation"


class DriftSeverity(str, Enum):
    """Drift severity levels"""
    NO_DRIFT = "no_drift"
    MODERATE_DRIFT = "moderate_drift"
    HIGH_DRIFT = "high_drift"


@dataclass
class AgentState:
    """
    State object for cache maintenance agent workflow

    Maintained across all workflow nodes
    """
    # Workflow metadata
    workflow_id: str
    workflow_status: WorkflowStatus = WorkflowStatus.INITIALIZING
    trigger_type: str = "manual"  # manual, scheduled, alert
    tenant_id: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.utcnow)

    # System state (from tools)
    metrics: Optional[Dict[str, Any]] = None
    current_threshold: Optional[float] = None
    drift_analysis: Optional[Dict[str, Any]] = None
    cache_quality: Optional[Dict[str, Any]] = None
    index_status: Optional[Dict[str, Any]] = None
    latency_metrics: Optional[Dict[str, Any]] = None

    # Analysis results
    drift_severity: Optional[DriftSeverity] = None
    quality_acceptable: Optional[bool] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    false_hit_rate: Optional[float] = None
    false_miss_rate: Optional[float] = None

    # Decision
    decision: Optional[ActionDecision] = None
    decision_reason: Optional[str] = None
    decision_confidence: Optional[float] = None

    # Action
    action_taken: Optional[str] = None
    action_result: Optional[Dict[str, Any]] = None
    old_threshold: Optional[float] = None
    new_threshold: Optional[float] = None

    # Validation
    validation_result: Optional[Dict[str, Any]] = None
    validation_passed: Optional[bool] = None
    validation_summary: Optional[str] = None

    # Report
    agent_report_id: Optional[int] = None
    report_summary: Optional[str] = None

    # Error handling
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Completion
    completed_at: Optional[datetime] = None
    execution_time_ms: Optional[float] = None

    def add_error(self, error: str):
        """Add error message"""
        self.errors.append(error)
        self.workflow_status = WorkflowStatus.FAILED

    def add_warning(self, warning: str):
        """Add warning message"""
        self.warnings.append(warning)

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for API responses"""
        return {
            "workflow_id": self.workflow_id,
            "workflow_status": self.workflow_status.value,
            "trigger_type": self.trigger_type,
            "tenant_id": self.tenant_id,
            "started_at": self.started_at.isoformat(),
            "system_state": {
                "metrics": self.metrics,
                "current_threshold": self.current_threshold,
                "precision": self.precision,
                "recall": self.recall,
                "false_hit_rate": self.false_hit_rate,
                "false_miss_rate": self.false_miss_rate,
            },
            "analysis": {
                "drift_severity": self.drift_severity.value if self.drift_severity else None,
                "quality_acceptable": self.quality_acceptable,
                "drift_analysis": self.drift_analysis,
                "cache_quality": self.cache_quality,
            },
            "decision": {
                "action": self.decision.value if self.decision else None,
                "reason": self.decision_reason,
                "confidence": self.decision_confidence,
            },
            "action": {
                "taken": self.action_taken,
                "result": self.action_result,
                "old_threshold": self.old_threshold,
                "new_threshold": self.new_threshold,
            },
            "validation": {
                "passed": self.validation_passed,
                "summary": self.validation_summary,
                "result": self.validation_result,
            },
            "errors": self.errors,
            "warnings": self.warnings,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time_ms": self.execution_time_ms,
        }

    def get_summary(self) -> str:
        """Generate human-readable summary"""
        if self.workflow_status == WorkflowStatus.FAILED:
            return f"Workflow failed: {', '.join(self.errors)}"

        if self.decision == ActionDecision.NO_ACTION:
            return f"No action needed. System healthy (precision={self.precision:.2f}, recall={self.recall:.2f})"

        if self.decision == ActionDecision.RAISE_THRESHOLD:
            return (
                f"Raised threshold from {self.old_threshold} to {self.new_threshold}. "
                f"Reason: {self.decision_reason}"
            )

        if self.decision == ActionDecision.LOWER_THRESHOLD:
            return (
                f"Lowered threshold from {self.old_threshold} to {self.new_threshold}. "
                f"Reason: {self.decision_reason}"
            )

        if self.decision == ActionDecision.SCHEDULE_INDEX_REBUILD:
            return f"Scheduled index rebuild. Reason: {self.decision_reason}"

        return f"Decision: {self.decision.value}. Reason: {self.decision_reason}"
