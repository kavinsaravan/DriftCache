"""
Supervisor Endpoints

API endpoints for supervisor agent orchestration
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.supervisor_run import SupervisorRun
from app.agents.supervisor import SupervisorAgent
from app.agents.reports.agent_report import AgentReportFormatter

router = APIRouter()


@router.post("/run")
def run_supervisor_workflow(
    trigger_reason: str = "manual_trigger",
    trigger_source: str = "manual",
    tenant_id: Optional[str] = None,
    dry_run: bool = True
):
    """
    Trigger supervisor remediation workflow

    This is the highest-level autonomous operation - the supervisor
    orchestrates all other agents to maintain system health.

    Workflow:
    1. Load system state (drift, quality, metrics)
    2. Diagnose problem
    3. Recommend remediation actions
    4. Execute actions (threshold optimization, index rebuild, etc.)
    5. Validate improvements
    6. Generate comprehensive report

    Args:
        trigger_reason: Why workflow was triggered
        trigger_source: manual, alert, scheduled
        tenant_id: Optional tenant isolation
        dry_run: If True, simulate actions (default for Week 7)

    Returns:
        Complete workflow result with diagnosis, actions, and validation

    Example response:
    {
        "run_id": "sup_20240613_123456_abc",
        "diagnosis": "cache_precision_degradation",
        "actions_taken": [
            {
                "agent": "threshold_optimizer",
                "action": "optimize_threshold",
                "result_summary": "Threshold: 0.90 -> 0.93"
            }
        ],
        "validation": {
            "passed": true,
            "improvements": ["Precision improved by +5.2%"]
        },
        "final_status": "resolved"
    }
    """
    try:
        supervisor = SupervisorAgent(dry_run=dry_run)

        result = supervisor.run_remediation_workflow(
            trigger_reason=trigger_reason,
            trigger_source=trigger_source,
            tenant_id=tenant_id
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Supervisor workflow failed: {str(e)}"
        )


@router.get("/runs")
def list_supervisor_runs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    final_status: Optional[str] = None,
    tenant_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List supervisor workflow history

    Args:
        limit: Number of runs to return
        offset: Pagination offset
        final_status: Filter by status (resolved, partial, failed, no_action)
        tenant_id: Optional tenant filter

    Returns:
        List of supervisor runs

    Example:
    GET /supervisor/runs?final_status=resolved&limit=10
    """
    try:
        query = db.query(SupervisorRun)

        if final_status:
            query = query.filter(SupervisorRun.final_status == final_status)

        if tenant_id:
            query = query.filter(SupervisorRun.tenant_id == tenant_id)

        total = query.count()

        runs = query.order_by(SupervisorRun.created_at.desc()).offset(offset).limit(limit).all()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "runs": [run.to_dict() for run in runs]
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list supervisor runs: {str(e)}"
        )


@router.get("/latest")
def get_latest_supervisor_run(
    tenant_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get most recent supervisor workflow

    Args:
        tenant_id: Optional tenant filter

    Returns:
        Latest supervisor run

    Example:
    GET /supervisor/latest
    """
    try:
        query = db.query(SupervisorRun)

        if tenant_id:
            query = query.filter(SupervisorRun.tenant_id == tenant_id)

        latest = query.order_by(SupervisorRun.created_at.desc()).first()

        if not latest:
            raise HTTPException(
                status_code=404,
                detail="No supervisor runs found"
            )

        return latest.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get latest supervisor run: {str(e)}"
        )


@router.get("/runs/{run_id}")
def get_supervisor_run(
    run_id: str,
    db: Session = Depends(get_db)
):
    """
    Get specific supervisor run by ID

    Args:
        run_id: Supervisor run identifier

    Returns:
        Supervisor run details
    """
    try:
        run = db.query(SupervisorRun).filter(
            SupervisorRun.run_id == run_id
        ).first()

        if not run:
            raise HTTPException(
                status_code=404,
                detail=f"Supervisor run {run_id} not found"
            )

        return run.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get supervisor run: {str(e)}"
        )


@router.get("/runs/{run_id}/report")
def get_supervisor_report(
    run_id: str,
    db: Session = Depends(get_db)
):
    """
    Get formatted report for supervisor run

    Args:
        run_id: Supervisor run identifier

    Returns:
        Human-readable formatted report
    """
    try:
        run = db.query(SupervisorRun).filter(
            SupervisorRun.run_id == run_id
        ).first()

        if not run:
            raise HTTPException(
                status_code=404,
                detail=f"Supervisor run {run_id} not found"
            )

        formatter = AgentReportFormatter()
        report = formatter.format_supervisor_report(run.to_dict())

        return {
            "run_id": run_id,
            "report": report
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate report: {str(e)}"
        )
