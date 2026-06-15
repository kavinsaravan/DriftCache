"""
Supervisor Agent

Orchestrates all infrastructure agents for coordinated remediation
"""
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
import uuid

from app.agents.policies.remediation_policy import RemediationPolicy
from app.agents.reports.agent_report import AgentReportFormatter
from app.agents.threshold_optimizer import ThresholdOptimizerAgent
from app.agents.index_rebuild_agent import IndexRebuildAgent
from app.agents.tools.drift_tools import DriftAnalysisTool
from app.agents.tools.cache_tools import CacheQualityTool
from app.agents.tools.metrics_tools import MetricsSummaryTool
from app.models.supervisor_run import SupervisorRun
from app.database.session import get_db_session

logger = logging.getLogger(__name__)


class SupervisorAgent:
    """
    Supervisor orchestrates all autonomous infrastructure agents

    Workflow:
    1. Load system state
    2. Diagnose problem
    3. Recommend actions
    4. Execute actions in sequence
    5. Validate each action
    6. Decide if more actions needed
    7. Write final report

    This is the highest-level autonomous component
    """

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.policy = RemediationPolicy()
        self.reporter = AgentReportFormatter()

        # Initialize agent dependencies
        self.threshold_optimizer = ThresholdOptimizerAgent()
        self.index_rebuilder = IndexRebuildAgent(dry_run=dry_run)

        # Initialize tools
        self.drift_tool = DriftAnalysisTool()
        self.quality_tool = CacheQualityTool()
        self.metrics_tool = MetricsSummaryTool()

    def run_remediation_workflow(
        self,
        trigger_reason: str,
        trigger_source: str = "manual",
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run complete supervisory remediation workflow

        Args:
            trigger_reason: What triggered this workflow
            trigger_source: manual, alert, scheduled
            tenant_id: Optional tenant isolation

        Returns:
            Complete workflow result
        """
        run_id = f"sup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        started_at = datetime.utcnow()

        logger.info(f"[{run_id}] Starting supervisor workflow")
        logger.info(f"  Trigger: {trigger_reason}")
        logger.info(f"  Source: {trigger_source}")

        # Step 1: Load system state
        logger.info(f"[{run_id}] Loading system state...")
        system_state = self._load_system_state(tenant_id=tenant_id)

        # Step 2: Diagnose problem
        logger.info(f"[{run_id}] Diagnosing problem...")
        diagnosis, diagnosis_details = self.policy.diagnose_problem(system_state)
        logger.info(f"[{run_id}] Diagnosis: {diagnosis}")

        # Step 3: Recommend actions
        logger.info(f"[{run_id}] Recommending actions...")
        recommended_actions = self.policy.recommend_action(diagnosis, system_state)
        logger.info(f"[{run_id}] {len(recommended_actions)} action(s) recommended")

        # Step 4: Execute actions
        actions_taken = []
        decision_path = [{"step": "diagnosis", "result": diagnosis}]

        for action in recommended_actions:
            # Check if action has conditions
            if action.get("condition"):
                if not self._check_condition(action["condition"], actions_taken):
                    logger.info(f"[{run_id}] Skipping {action['agent']}: condition not met")
                    continue

            # Skip monitor-only actions
            if action["agent"] in ["none", "monitor"]:
                logger.info(f"[{run_id}] {action['action']}: {action['reason']}")
                break

            # Execute action
            logger.info(f"[{run_id}] Executing {action['agent']}: {action['action']}")
            action_result = self._execute_action(action, system_state, tenant_id)

            actions_taken.append(action_result)
            decision_path.append({
                "step": f"execute_{action['agent']}",
                "action": action["action"],
                "result": action_result.get("result_summary", "completed")
            })

            # Step 5: Validate action
            validation = self._validate_action(system_state, action_result)
            decision_path.append({
                "step": "validate",
                "passed": validation.get("passed"),
                "improvements": validation.get("improvements", [])
            })

            # Step 6: Decide if more actions needed
            should_continue, continue_reason = self.policy.should_continue_remediation(
                actions_taken,
                validation
            )

            if not should_continue:
                logger.info(f"[{run_id}] Stopping remediation: {continue_reason}")
                break

        # Step 7: Final state and status
        final_state = self._load_system_state(tenant_id=tenant_id)
        final_status, status_reason = self._determine_final_status(
            diagnosis,
            actions_taken,
            final_state
        )

        completed_at = datetime.utcnow()
        execution_time_ms = (completed_at - started_at).total_seconds() * 1000

        # Build result
        result = {
            "run_id": run_id,
            "trigger_reason": trigger_reason,
            "trigger_source": trigger_source,
            "initial_state": system_state,
            "diagnosis": diagnosis,
            "diagnosis_details": diagnosis_details,
            "decision_path": decision_path,
            "actions_taken": actions_taken,
            "final_state": final_state,
            "validation": self._final_validation(system_state, final_state),
            "final_status": final_status,
            "status_reason": status_reason,
            "recommendations": self._generate_recommendations(final_state),
            "total_execution_time_ms": execution_time_ms,
            "agents_invoked_count": len(actions_taken),
            "tenant_id": tenant_id,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
        }

        # Generate report
        result["report_summary"] = self.reporter.format_summary(result)

        # Store in database
        self._store_supervisor_run(result)

        logger.info(f"[{run_id}] Supervisor workflow complete: {final_status}")
        return result

    def _load_system_state(self, tenant_id: Optional[str]) -> Dict[str, Any]:
        """Load current system metrics"""
        # Get drift status
        drift_result = self.drift_tool._run(tenant_id=tenant_id)

        # Get cache quality
        quality_result = self.quality_tool._run(
            dataset_name="default",
            threshold=0.90,
            tenant_id=tenant_id
        )

        # Get metrics
        metrics_result = self.metrics_tool._run(period="24h", tenant_id=tenant_id)

        return {
            "drift_severity": drift_result.get("severity", "no_drift"),
            "drift_score": drift_result.get("drift_score", 0),
            "precision": quality_result.get("precision", 0),
            "recall": quality_result.get("recall", 0),
            "false_hit_rate": quality_result.get("false_hit_rate", 0),
            "false_miss_rate": quality_result.get("false_miss_rate", 0),
            "cache_hit_rate": metrics_result.get("cache_hit_rate", 0),
            "stale_vector_ratio": 0.15,  # Mock for now
        }

    def _execute_action(
        self,
        action: Dict[str, Any],
        system_state: Dict[str, Any],
        tenant_id: Optional[str]
    ) -> Dict[str, Any]:
        """Execute a specific agent action"""
        agent = action["agent"]

        if agent == "threshold_optimizer":
            # Mock evaluation dataset
            eval_dataset = [
                {"similarity": 0.92, "should_cache": True},
                {"similarity": 0.88, "should_cache": False},
                # Add more mock data...
            ]

            result = self.threshold_optimizer.optimize_threshold(
                current_threshold=0.90,
                current_metrics=system_state,
                evaluation_dataset=eval_dataset,
                drift_severity=system_state.get("drift_severity"),
                trigger_source="supervisor",
                tenant_id=tenant_id
            )

            return {
                "agent": "threshold_optimizer",
                "action": "optimize_threshold",
                "reason": action["reason"],
                "result": result,
            }
