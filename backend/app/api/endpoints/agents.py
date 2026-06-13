"""
Agent Endpoints

API endpoints for triggering and monitoring autonomous agent workflows
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.database.session import get_db
from app.models.agent_action import AgentAction
from app.agents.workflows.cache_maintenance import CacheMaintenanceWorkflow
from app.agents.state import AgentState, WorkflowStatus

router = APIRouter()


@router.post("/cache-maintenance/run")
def run_cache_maintenance(
    trigger_type: str = "manual",
    tenant_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Trigger cache maintenance workflow

    This is the primary endpoint for autonomous infrastructure management.

    Workflow steps:
    1. Load system state (metrics, drift, thresholds)
    2. Analyze drift severity
    3. Analyze cache quality (precision, recall, false rates)
    4. Decide action based on priority logic
    5. Execute action (dry-run mode for Week 6)
    6. Validate result
    7. Write audit report to database

    Args:
        trigger_type: How workflow was triggered (manual, scheduled, alert)
        tenant_id: Optional tenant isolation

    Returns:
        Complete workflow state with decision and action details

    Example response:
    {
        "workflow_status": "completed",
        "workflow_id": "wf_20240613_123456_abc",
        "system_state": {
            "current_threshold": 0.90,
            "precision": 0.88,
            "recall": 0.82,
            "false_hit_rate": 0.12
        },
        "analysis": {
            "drift_severity": "high",
            "quality_acceptable": false
        },
        "decision": {
            "action": "raise_threshold",
            "reason": "High false hit rate (12.0%) is dangerous",
            "confidence": 0.85
        },
        "action": {
            "taken": "threshold_update_0.90_to_0.92",
            "result": {...}
        },
        "validation": {
            "passed": true,
            "summary": "Simulated impact: +2.5% precision, -1.2% recall"
        },
        "execution_time_ms": 1234.5
    }
    """
    try:
        # Create and run workflow
        workflow = CacheMaintenanceWorkflow(db_session=db)
        state = workflow.run(trigger_type=trigger_type, tenant_id=tenant_id)

        # Return structured response
        response = state.to_dict()

        # Add summary for convenience
        response["summary"] = state.get_summary()

        return response

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Workflow execution failed: {str(e)}"
        )


@router.get("/actions")
def list_agent_actions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    workflow_status: Optional[str] = None,
    decision: Optional[str] = None,
    drift_severity: Optional[str] = None,
    tenant_id: Optional[str] = None,
    since_hours: Optional[int] = Query(None, description="Only actions in last N hours"),
    db: Session = Depends(get_db)
):
    """
    List agent action history

    Provides complete audit trail of autonomous decisions and actions.

    Query filters:
    - workflow_status: Filter by status (completed, failed)
    - decision: Filter by decision type (no_action, raise_threshold, etc)
    - drift_severity: Filter by drift level (no_drift, moderate_drift, high_drift)
    - tenant_id: Filter by tenant
    - since_hours: Only show recent actions (e.g., last 24 hours)
    - limit/offset: Pagination

    Returns:
        List of agent actions with full context

    Example:
    GET /agents/actions?decision=raise_threshold&since_hours=24&limit=10

    Response:
    {
        "total": 3,
        "actions": [
            {
                "id": 123,
                "workflow_id": "wf_20240613_123456_abc",
                "decision": "raise_threshold",
                "decision_reason": "High false hit rate (12.0%) is dangerous",
                "old_threshold": 0.90,
                "new_threshold": 0.92,
                "precision": 0.88,
                "recall": 0.82,
                "validation_passed": true,
                "started_at": "2024-06-13T12:34:56Z",
                "execution_time_ms": 1234.5
            },
            ...
        ]
    }
    """
    try:
        # Build query
        query = db.query(AgentAction)

        # Apply filters
        if workflow_status:
            query = query.filter(AgentAction.workflow_status == workflow_status)

        if decision:
            query = query.filter(AgentAction.decision == decision)

        if drift_severity:
            query = query.filter(AgentAction.drift_severity == drift_severity)

        if tenant_id:
            query = query.filter(AgentAction.tenant_id == tenant_id)

        if since_hours:
            cutoff = datetime.utcnow() - timedelta(hours=since_hours)
            query = query.filter(AgentAction.started_at >= cutoff)

        # Get total count
        total = query.count()

        # Order by most recent first
        query = query.order_by(AgentAction.started_at.desc())

        # Apply pagination
        actions = query.offset(offset).limit(limit).all()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "actions": [action.to_dict() for action in actions]
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list actions: {str(e)}"
        )


@router.get("/latest-report")
def get_latest_report(
    tenant_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get most recent agent action report

    Useful for dashboards and status checks.

    Args:
        tenant_id: Optional tenant filter

    Returns:
        Most recent agent action with full details

    Example:
    GET /agents/latest-report

    Response:
    {
        "id": 123,
        "workflow_id": "wf_20240613_123456_abc",
        "workflow_status": "completed",
        "decision": "raise_threshold",
        "decision_reason": "High false hit rate (12.0%) is dangerous",
        "action_taken": "threshold_update_0.90_to_0.92",
        "validation_passed": true,
        "report_summary": "Raised threshold from 0.90 to 0.92. Reason: High false hit rate (12.0%) is dangerous",
        "started_at": "2024-06-13T12:34:56Z",
        "completed_at": "2024-06-13T12:35:12Z",
        "execution_time_ms": 1234.5,
        "precision": 0.88,
        "recall": 0.82,
        "false_hit_rate": 0.12
    }
    """
    try:
        # Build query
        query = db.query(AgentAction)

        # Apply tenant filter if provided
        if tenant_id:
            query = query.filter(AgentAction.tenant_id == tenant_id)

        # Get most recent action
        latest_action = query.order_by(AgentAction.started_at.desc()).first()

        if not latest_action:
            raise HTTPException(
                status_code=404,
                detail="No agent actions found"
            )

        return latest_action.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get latest report: {str(e)}"
        )


@router.get("/actions/{workflow_id}")
def get_action_by_workflow_id(
    workflow_id: str,
    db: Session = Depends(get_db)
):
    """
    Get specific agent action by workflow ID

    Useful for tracking individual workflow executions.

    Args:
        workflow_id: Unique workflow identifier

    Returns:
        Complete agent action details

    Example:
    GET /agents/actions/wf_20240613_123456_abc
    """
    try:
        action = db.query(AgentAction).filter(
            AgentAction.workflow_id == workflow_id
        ).first()

        if not action:
            raise HTTPException(
                status_code=404,
                detail=f"Action with workflow_id={workflow_id} not found"
            )

        return action.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get action: {str(e)}"
        )


@router.get("/stats")
def get_agent_stats(
    since_hours: int = Query(24, description="Calculate stats for last N hours"),
    tenant_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get agent statistics and performance metrics

    Provides insights into agent behavior and decision patterns.

    Args:
        since_hours: Time window for statistics (default: 24 hours)
        tenant_id: Optional tenant filter

    Returns:
        Agent performance statistics

    Example:
    GET /agents/stats?since_hours=168  # Last week

    Response:
    {
        "period_hours": 168,
        "total_workflows": 42,
        "completed_workflows": 40,
        "failed_workflows": 2,
        "success_rate": 0.952,
        "decisions": {
            "no_action": 25,
            "raise_threshold": 10,
            "lower_threshold": 3,
            "schedule_index_rebuild": 2
        },
        "validation_success_rate": 0.975,
        "avg_execution_time_ms": 1234.5,
        "actions_taken": 15,
        "actions_simulated": 15
    }
    """
    try:
        # Calculate time window
        cutoff = datetime.utcnow() - timedelta(hours=since_hours)

        # Build base query
        query = db.query(AgentAction).filter(AgentAction.started_at >= cutoff)

        if tenant_id:
            query = query.filter(AgentAction.tenant_id == tenant_id)

        # Get all actions in window
        actions = query.all()

        if not actions:
            return {
                "period_hours": since_hours,
                "total_workflows": 0,
                "message": "No agent actions in this time window"
            }

        # Calculate statistics
        total = len(actions)
        completed = sum(1 for a in actions if a.workflow_status == "completed")
        failed = sum(1 for a in actions if a.workflow_status == "failed")

        # Decision breakdown
        decisions = {}
        for action in actions:
            decision = action.decision or "unknown"
            decisions[decision] = decisions.get(decision, 0) + 1

        # Validation stats
        validated_actions = [a for a in actions if a.validation_passed is not None]
        validation_success = sum(1 for a in validated_actions if a.validation_passed)
        validation_rate = validation_success / len(validated_actions) if validated_actions else 0

        # Execution time stats
        execution_times = [a.execution_time_ms for a in actions if a.execution_time_ms]
        avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0

        # Action stats
        actions_taken = sum(1 for a in actions if a.action_taken and a.action_taken != "no_action")

        return {
            "period_hours": since_hours,
            "period_start": cutoff.isoformat(),
            "period_end": datetime.utcnow().isoformat(),
            "total_workflows": total,
            "completed_workflows": completed,
            "failed_workflows": failed,
            "success_rate": completed / total if total > 0 else 0,
            "decisions": decisions,
            "validation_success_rate": validation_rate,
            "avg_execution_time_ms": round(avg_execution_time, 2),
            "actions_taken": actions_taken,
            "tenant_id": tenant_id
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate stats: {str(e)}"
        )
