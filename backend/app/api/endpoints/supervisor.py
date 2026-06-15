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
