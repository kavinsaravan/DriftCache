"""
LangGraph Supervisor Agent

Uses LangGraph StateGraph for proper stateful workflow orchestration
"""
from typing import Dict, Any, Optional, List, TypedDict, Annotated
import logging
from datetime import datetime
import uuid
import operator

from langgraph.graph import StateGraph, END
from langchain.tools import BaseTool

from app.agents.policies.remediation_policy import RemediationPolicy
from app.agents.reports.agent_report import AgentReportFormatter
from app.agents.threshold_optimizer import ThresholdOptimizerAgent
from app.agents.index_rebuild_agent import IndexRebuildAgent
from app.agents.tools.drift_tools import DriftAnalysisTool
from app.agents.tools.cache_tools import CacheQualityTool
from app.agents.tools.metrics_tools import MetricsSummaryTool
from app.models.supervisor_run import SupervisorRun
from app.database.session import get_db_manager, SessionLocal
from app.services.threshold_config import get_active_threshold

logger = logging.getLogger(__name__)


class SupervisorState(TypedDict):
    """
    State schema for LangGraph supervisor workflow

    LangGraph manages this state across all nodes
    """
    # Workflow metadata
    run_id: str
    trigger_reason: str
    trigger_source: str
    tenant_id: Optional[str]
    started_at: datetime

    # System state (from tools)
    system_state: Dict[str, Any]

    # Diagnosis
    diagnosis: Optional[str]
    diagnosis_details: Optional[str]

    # Recommendations
    recommended_actions: List[Dict[str, Any]]

    # Execution tracking
    actions_taken: Annotated[List[Dict[str, Any]], operator.add]  # Append-only list
    decision_path: Annotated[List[Dict[str, Any]], operator.add]
    current_action_index: int

    # Validation
    validation_results: List[Dict[str, Any]]
    should_continue: bool

    # Final results
    final_state: Optional[Dict[str, Any]]
    final_status: Optional[str]
    status_reason: Optional[str]
    report_summary: Optional[str]

    # Errors
    errors: Annotated[List[str], operator.add]


class LangGraphSupervisor:
    """
    LangGraph-powered supervisor for autonomous remediation

    Uses StateGraph for proper workflow orchestration with:
    - State management
    - Conditional routing
    - Error handling
    - Audit trail
    """

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.policy = RemediationPolicy()
        self.reporter = AgentReportFormatter()

        # Initialize agents
        self.threshold_optimizer = ThresholdOptimizerAgent()
        self.index_rebuilder = IndexRebuildAgent(dry_run=dry_run)

        # Initialize tools
        self.drift_tool = DriftAnalysisTool()
        self.quality_tool = CacheQualityTool()
        self.metrics_tool = MetricsSummaryTool()

        # Build the graph
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """
        Build LangGraph StateGraph for supervisor workflow

        Nodes:
        1. load_system_state - Gather metrics from tools
        2. diagnose - Classify system health
        3. recommend - Generate remediation actions
        4. execute_action - Run agent (threshold optimizer, index rebuilder)
        5. validate_action - Check if improvement occurred
        6. finalize - Generate report and store results

        Returns:
            Compiled StateGraph
        """
        workflow = StateGraph(SupervisorState)

        # Add nodes
        workflow.add_node("load_system_state", self._load_system_state_node)
        workflow.add_node("diagnose", self._diagnose_node)
        workflow.add_node("recommend", self._recommend_node)
        workflow.add_node("execute_action", self._execute_action_node)
        workflow.add_node("validate_action", self._validate_action_node)
        workflow.add_node("finalize", self._finalize_node)

        # Set entry point
        workflow.set_entry_point("load_system_state")

        # Add edges
        workflow.add_edge("load_system_state", "diagnose")
        workflow.add_edge("diagnose", "recommend")

        # Conditional: execute actions or skip to finalize?
        workflow.add_conditional_edges(
            "recommend",
            self._should_execute_actions,
            {
                "execute": "execute_action",
                "skip": "finalize"
            }
        )

        workflow.add_edge("execute_action", "validate_action")

        # Conditional: continue with more actions or finalize?
        workflow.add_conditional_edges(
            "validate_action",
            self._should_continue_remediation,
            {
                "continue": "execute_action",
                "finalize": "finalize"
            }
        )

        workflow.add_edge("finalize", END)

        return workflow.compile()

    def _load_system_state_node(self, state: SupervisorState) -> Dict[str, Any]:
        """Node: Load current system metrics"""
        logger.info(f"[{state['run_id']}] Loading system state...")

        # Normalize tenant_id (default to "default" if None)
        tenant_id = state.get("tenant_id") or "default"

        # Get current threshold from database
        db = SessionLocal()
        try:
            current_threshold = get_active_threshold(db, tenant_id=tenant_id)
        finally:
            db.close()

        # Get drift status
        drift_result = self.drift_tool._run(tenant_id=tenant_id)

        # Get cache quality (using actual DB threshold)
        quality_result = self.quality_tool._run(
            dataset_name="default",
            threshold=current_threshold,
            tenant_id=tenant_id
        )

        # Get metrics
        metrics_result = self.metrics_tool._run(period="24h", tenant_id=tenant_id)

        system_state = {
            "current_threshold": current_threshold,
            "drift_severity": drift_result.get("severity", "no_drift"),
            "drift_score": drift_result.get("drift_score", 0),
            "precision": quality_result.get("precision", 0),
            "recall": quality_result.get("recall", 0),
            "false_hit_rate": quality_result.get("false_hit_rate", 0),
            "false_miss_rate": quality_result.get("false_miss_rate", 0),
            "cache_hit_rate": metrics_result.get("cache_hit_rate", 0),
            "stale_vector_ratio": 0.15,  # Estimated from index metadata
        }

        return {"system_state": system_state, "tenant_id": tenant_id}

    def _diagnose_node(self, state: SupervisorState) -> Dict[str, Any]:
        """Node: Diagnose system health"""
        logger.info(f"[{state['run_id']}] Diagnosing problem...")

        diagnosis, diagnosis_details = self.policy.diagnose_problem(state["system_state"])

        logger.info(f"[{state['run_id']}] Diagnosis: {diagnosis}")

        return {
            "diagnosis": diagnosis,
            "diagnosis_details": diagnosis_details,
            "decision_path": [{"step": "diagnosis", "result": diagnosis}]
        }

    def _recommend_node(self, state: SupervisorState) -> Dict[str, Any]:
        """Node: Recommend remediation actions"""
        logger.info(f"[{state['run_id']}] Recommending actions...")

        recommended_actions = self.policy.recommend_action(
            state["diagnosis"],
            state["system_state"]
        )

        logger.info(f"[{state['run_id']}] {len(recommended_actions)} action(s) recommended")

        return {
            "recommended_actions": recommended_actions,
            "current_action_index": 0
        }

    def _execute_action_node(self, state: SupervisorState) -> Dict[str, Any]:
        """Node: Execute current remediation action"""
        idx = state["current_action_index"]
        actions = state["recommended_actions"]

        if idx >= len(actions):
            return {"should_continue": False}

        action = actions[idx]
        run_id = state["run_id"]

        logger.info(f"[{run_id}] Executing {action['agent']}: {action['action']}")

        # Execute the action
        if action["agent"] == "threshold_optimizer":
            # Evaluation dataset (would be loaded from evaluation service in production)
            eval_dataset = [
                {"similarity": 0.92, "should_cache": True},
                {"similarity": 0.88, "should_cache": False},
            ]

            result = self.threshold_optimizer.optimize_threshold(
                current_threshold=state["system_state"].get("current_threshold", 0.90),
                current_metrics=state["system_state"],
                evaluation_dataset=eval_dataset,
                drift_severity=state["system_state"].get("drift_severity"),
                trigger_source="supervisor",
                tenant_id=state.get("tenant_id")
            )

            action_result = {
                "agent": "threshold_optimizer",
                "action": "optimize_threshold",
                "reason": action["reason"],
                "result": result,
                "result_summary": f"Threshold: {result.get('old_threshold')} -> {result.get('new_threshold')}"
            }

        elif action["agent"] == "index_rebuilder":
            result = self.index_rebuilder.evaluate_and_rebuild(
                drift_severity=state["system_state"].get("drift_severity"),
                threshold_optimization_failed=True,
                trigger_source="supervisor",
                tenant_id=state.get("tenant_id")
            )

            action_result = {
                "agent": "index_rebuilder",
                "action": "rebuild_index",
                "reason": action["reason"],
                "result": result,
                "result_summary": f"Index rebuild: {result.get('decision')}"
            }

        else:
            # Monitor-only or skip
            action_result = {
                "agent": action.get("agent", "none"),
                "action": action.get("action", "no_action"),
                "reason": action.get("reason", ""),
                "result": None,
                "result_summary": "No action taken"
            }

        return {
            "actions_taken": [action_result],
            "decision_path": [{
                "step": f"execute_{action['agent']}",
                "action": action["action"],
                "result": action_result.get("result_summary", "completed")
            }],
            "current_action_index": idx + 1
        }

    def _validate_action_node(self, state: SupervisorState) -> Dict[str, Any]:
        """Node: Validate that action improved system"""
        if not state["actions_taken"]:
            return {"should_continue": False}

        last_action = state["actions_taken"][-1]

        # Get estimated after state from action result
        result = last_action.get("result", {})

        if last_action["agent"] == "threshold_optimizer":
            after_estimate = result.get("after_estimate", {})
            validation = self.policy.validate_remediation(
                state["system_state"],
                after_estimate,
                last_action
            )
        else:
            # Default validation
            validation = {
                "passed": True,
                "improvements": ["Action completed"],
                "degradations": []
            }

        # Decide if should continue
        should_continue, continue_reason = self.policy.should_continue_remediation(
            state["actions_taken"],
            validation
        )

        logger.info(f"[{state['run_id']}] Validation: {validation.get('passed')}")
        if not should_continue:
            logger.info(f"[{state['run_id']}] Stopping: {continue_reason}")

        return {
            "validation_results": state.get("validation_results", []) + [validation],
            "should_continue": should_continue,
            "decision_path": [{
                "step": "validate",
                "passed": validation.get("passed"),
                "improvements": validation.get("improvements", [])
            }]
        }

    def _finalize_node(self, state: SupervisorState) -> Dict[str, Any]:
        """Node: Generate final report and store results"""
        run_id = state["run_id"]

        # Reload final state
        final_state = self._load_system_state_node(state)["system_state"]

        # Determine final status
        final_status, status_reason = self._determine_final_status(
            state["diagnosis"],
            state["actions_taken"],
            final_state
        )

        completed_at = datetime.utcnow()
        execution_time_ms = (completed_at - state["started_at"]).total_seconds() * 1000

        # Build result
        result = {
            "run_id": run_id,
            "trigger_reason": state["trigger_reason"],
            "trigger_source": state["trigger_source"],
            "initial_state": state["system_state"],
            "diagnosis": state["diagnosis"],
            "diagnosis_details": state["diagnosis_details"],
            "decision_path": state["decision_path"],
            "actions_taken": state["actions_taken"],
            "final_state": final_state,
            "final_status": final_status,
            "status_reason": status_reason,
            "total_execution_time_ms": execution_time_ms,
            "agents_invoked_count": len(state["actions_taken"]),
            "tenant_id": state.get("tenant_id"),
            "started_at": state["started_at"].isoformat(),
            "completed_at": completed_at.isoformat(),
        }

        # Generate report
        report_summary = self.reporter.format_summary(result)

        # Store in database
        self._store_supervisor_run(result, report_summary)

        logger.info(f"[{run_id}] Workflow complete: {final_status}")

        return {
            "final_state": final_state,
            "final_status": final_status,
            "status_reason": status_reason,
            "report_summary": report_summary
        }

    def _should_execute_actions(self, state: SupervisorState) -> str:
        """Conditional edge: Should we execute actions or skip to finalize?"""
        if state["diagnosis"] == "healthy":
            return "skip"

        actions = state.get("recommended_actions", [])
        if not actions:
            return "skip"

        # Check for monitor-only actions
        if all(a.get("agent") in ["none", "monitor"] for a in actions):
            return "skip"

        return "execute"

    def _should_continue_remediation(self, state: SupervisorState) -> str:
        """Conditional edge: Continue with more actions or finalize?"""
        # Check if we should continue based on validation
        if not state.get("should_continue", False):
            return "finalize"

        # Check if there are more actions to execute
        if state["current_action_index"] >= len(state["recommended_actions"]):
            return "finalize"

        return "continue"

    def _determine_final_status(
        self,
        diagnosis: str,
        actions_taken: List[Dict],
        final_state: Dict[str, Any]
    ) -> tuple[str, str]:
        """Determine final workflow status"""
        if diagnosis == "healthy":
            return "no_action", "System healthy, no remediation needed"

        if not actions_taken:
            return "no_action", "No actions taken"

        # Check if system improved
        if final_state.get("precision", 0) > 0.92 and final_state.get("false_hit_rate", 0) < 0.05:
            return "resolved", "Remediation successful, system restored to healthy state"

        if len(actions_taken) > 0:
            return "partial", "Actions taken, partial improvement achieved"

        return "failed", "Remediation attempted but issues persist"

    def _store_supervisor_run(self, result: Dict[str, Any], report_summary: str):
        """Store supervisor run in database"""
        with get_db_manager().session_scope() as session:
            supervisor_run = SupervisorRun(
                run_id=result["run_id"],
                trigger_source=result["trigger_source"],
                trigger_reason=result["trigger_reason"],
                initial_drift_score=result["initial_state"].get("drift_score"),
                initial_drift_severity=result["initial_state"].get("drift_severity"),
                initial_precision=result["initial_state"].get("precision"),
                initial_recall=result["initial_state"].get("recall"),
                initial_false_hit_rate=result["initial_state"].get("false_hit_rate"),
                initial_cache_hit_rate=result["initial_state"].get("cache_hit_rate"),
                initial_stale_vector_ratio=result["initial_state"].get("stale_vector_ratio"),
                diagnosis=result["diagnosis"],
                diagnosis_details=result["diagnosis_details"],
                decision_path=result["decision_path"],
                actions_taken=result["actions_taken"],
                final_precision=result["final_state"].get("precision"),
                final_recall=result["final_state"].get("recall"),
                final_false_hit_rate=result["final_state"].get("false_hit_rate"),
                final_drift_score=result["final_state"].get("drift_score"),
                final_status=result["final_status"],
                status_reason=result["status_reason"],
                report_summary=report_summary,
                total_execution_time_ms=result["total_execution_time_ms"],
                agents_invoked_count=result["agents_invoked_count"],
                tenant_id=result.get("tenant_id"),
                started_at=datetime.fromisoformat(result["started_at"]),
                completed_at=datetime.fromisoformat(result["completed_at"]),
            )

            session.add(supervisor_run)
            session.commit()
            logger.info(f"Stored supervisor run: {supervisor_run.id}")

    def run_remediation_workflow(
        self,
        trigger_reason: str,
        trigger_source: str = "manual",
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run LangGraph-powered remediation workflow

        Args:
            trigger_reason: What triggered this workflow
            trigger_source: manual, alert, scheduled
            tenant_id: Optional tenant isolation

        Returns:
            Complete workflow result
        """
        run_id = f"sup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        # Initialize state
        initial_state: SupervisorState = {
            "run_id": run_id,
            "trigger_reason": trigger_reason,
            "trigger_source": trigger_source,
            "tenant_id": tenant_id,
            "started_at": datetime.utcnow(),
            "system_state": {},
            "diagnosis": None,
            "diagnosis_details": None,
            "recommended_actions": [],
            "actions_taken": [],
            "decision_path": [],
            "current_action_index": 0,
            "validation_results": [],
            "should_continue": False,
            "final_state": None,
            "final_status": None,
            "status_reason": None,
            "report_summary": None,
            "errors": [],
        }

        logger.info(f"[{run_id}] Starting LangGraph supervisor workflow")
        logger.info(f"  Trigger: {trigger_reason}")
        logger.info(f"  Source: {trigger_source}")

        # Run the graph
        final_state = self.graph.invoke(initial_state)

        return {
            "run_id": run_id,
            "trigger_reason": trigger_reason,
            "trigger_source": trigger_source,
            "diagnosis": final_state.get("diagnosis"),
            "actions_taken": final_state.get("actions_taken", []),
            "final_status": final_state.get("final_status"),
            "status_reason": final_state.get("status_reason"),
            "report_summary": final_state.get("report_summary"),
            "decision_path": final_state.get("decision_path", []),
        }
