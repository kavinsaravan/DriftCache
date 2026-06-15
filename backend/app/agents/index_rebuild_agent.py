"""
Index Rebuild Agent

Autonomous agent that maintains FAISS vector index health
"""
from typing import Dict, Any, Optional
import logging
from datetime import datetime

from app.vectorstore.index_health import IndexHealthMonitor
from app.vectorstore.index_manager import IndexManager
from app.vectorstore.rebuild import IndexRebuilder
from app.models.index_rebuild_job import IndexRebuildJob
from app.database.session import get_db_manager

logger = logging.getLogger(__name__)


class IndexRebuildAgent:
    """
    Autonomous index maintenance agent

    Responsibilities:
    1. Monitor index health
    2. Detect degradation conditions
    3. Trigger rebuilds when needed
    4. Validate rebuild results
    5. Record maintenance history

    Decision priorities:
    - High stale ratio (>25%) -> Rebuild urgently
    - High latency (>40ms) -> Rebuild for performance
    - Old index + moderate staleness -> Rebuild proactively
    - Threshold optimization failed -> Rebuild for quality
    """

    def __init__(
        self,
        dry_run: bool = True,
        stale_ratio_threshold: float = 0.25,
        latency_threshold_ms: float = 40.0
    ):
        self.dry_run = dry_run
        self.stale_ratio_threshold = stale_ratio_threshold
        self.latency_threshold_ms = latency_threshold_ms

        self.health_monitor = IndexHealthMonitor()
        self.index_manager = IndexManager()
        self.rebuilder = IndexRebuilder(index_manager=self.index_manager)

    def evaluate_and_rebuild(
        self,
        drift_severity: Optional[str] = None,
        threshold_optimization_failed: bool = False,
        trigger_source: str = "agent",
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluate index health and rebuild if needed

        Args:
            drift_severity: Current drift level
            threshold_optimization_failed: Whether threshold tuning didn't help
            trigger_source: What triggered evaluation (agent, manual, scheduled)
            tenant_id: Optional tenant isolation

        Returns:
            Evaluation result with decision and action taken
        """
        logger.info("Evaluating index health for potential rebuild")
        logger.info(f"  Drift severity: {drift_severity}")
        logger.info(f"  Threshold opt failed: {threshold_optimization_failed}")
        logger.info(f"  Trigger source: {trigger_source}")

        # Get index health metrics
        health_report = self.health_monitor.generate_health_report(tenant_id=tenant_id)
        health_metrics = health_report["health_metrics"]

        # Decide whether to rebuild
        decision, decision_reason = self._decide_rebuild_action(
            health_metrics=health_metrics,
            drift_severity=drift_severity,
            threshold_optimization_failed=threshold_optimization_failed
        )

        result = {
            "agent": "index_rebuilder",
            "decision": decision,
            "decision_reason": decision_reason,
            "health_metrics": health_metrics,
            "health_status": health_metrics["health_status"],
            "recommendations": health_report["recommendations"],
        }

        # Execute rebuild if decided
        if decision in ["REBUILD_NOW", "SCHEDULE_REBUILD"]:
            rebuild_result = self._execute_rebuild(
                reason=decision_reason,
                trigger_source=trigger_source,
                health_metrics=health_metrics,
                tenant_id=tenant_id
            )
            result["rebuild_result"] = rebuild_result
            result["rebuild_job_id"] = rebuild_result.get("rebuild_job_id")

        logger.info(f"Index rebuild evaluation complete: {decision}")
        return result

    def _decide_rebuild_action(
        self,
        health_metrics: Dict[str, Any],
        drift_severity: Optional[str] = None,
        threshold_optimization_failed: bool = False
    ) -> tuple[str, str]:
        """
        Decide what action to take

        Args:
            health_metrics: Index health metrics
            drift_severity: Current drift level
            threshold_optimization_failed: Whether threshold tuning didn't help

        Returns:
            (decision, reason) tuple
        """
        stale_ratio = health_metrics.get("stale_vector_ratio", 0)
        avg_latency = health_metrics.get("avg_search_latency_ms", 0)
        index_age = health_metrics.get("index_age_hours", 0)
        health_status = health_metrics.get("health_status", "unknown")

        # Priority 1: Critical stale ratio
        if stale_ratio > 0.30:
            return "REBUILD_NOW", f"Critical stale vector ratio ({stale_ratio:.1%}) requires immediate rebuild"

        # Priority 2: Critical latency
        if avg_latency > 50:
            return "REBUILD_NOW", f"Critical search latency ({avg_latency:.1f}ms) requires immediate rebuild"

        # Priority 3: High stale ratio
        if stale_ratio > self.stale_ratio_threshold:
            return "REBUILD_NOW", f"High stale vector ratio ({stale_ratio:.1%}) exceeds threshold"

        # Priority 4: High latency
        if avg_latency > self.latency_threshold_ms:
            return "SCHEDULE_REBUILD", f"Elevated search latency ({avg_latency:.1f}ms) suggests rebuild needed"

        # Priority 5: Threshold optimization failed + quality issues
        if threshold_optimization_failed and health_status in ["degraded", "critical"]:
            return "REBUILD_NOW", "Threshold optimization failed to improve quality, index rebuild needed"

        # Priority 6: High drift + moderate staleness
        if drift_severity == "high_drift" and stale_ratio > 0.15:
            return "SCHEDULE_REBUILD", f"High drift with moderate staleness ({stale_ratio:.1%})"

        # Priority 7: Old index with issues
        if index_age > 168 and stale_ratio > 0.15:  # 7 days
            return "SCHEDULE_REBUILD", f"Old index ({index_age:.0f}h) with moderate staleness ({stale_ratio:.1%})"

        # No rebuild needed
        return "NO_REBUILD", f"Index healthy: stale={stale_ratio:.1%}, latency={avg_latency:.1f}ms, age={index_age:.0f}h"

    def _execute_rebuild(
        self,
        reason: str,
        trigger_source: str,
        health_metrics: Dict[str, Any],
        tenant_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        Execute index rebuild

        Args:
            reason: Rebuild reason
            trigger_source: What triggered rebuild
            health_metrics: Current health metrics
            tenant_id: Optional tenant ID

        Returns:
            Rebuild result
        """
        logger.info(f"Executing index rebuild: {reason}")

        # Execute rebuild
        rebuild_result = self.rebuilder.rebuild_index(
            reason=reason,
            dry_run=self.dry_run,
            tenant_id=tenant_id
        )

        # Store rebuild job in database
        with get_db_manager().session_scope() as session:
            rebuild_job = IndexRebuildJob(
                job_id=rebuild_result.get("rebuild_id"),
                status="simulated" if self.dry_run else rebuild_result.get("status", "completed"),
                trigger_reason=reason,
                trigger_source=trigger_source,
                old_vector_count=health_metrics.get("vector_count"),
                active_cache_count=rebuild_result.get("active_cache_count"),
                stale_vector_ratio=health_metrics.get("stale_vector_ratio"),
                avg_search_latency_ms=health_metrics.get("avg_search_latency_ms"),
                index_age_hours=health_metrics.get("index_age_hours"),
                new_vector_count=rebuild_result.get("new_vector_count"),
                vectors_added=rebuild_result.get("vectors_added"),
                vectors_removed=rebuild_result.get("vectors_removed"),
                rebuild_duration_ms=rebuild_result.get("rebuild_duration_ms"),
                validation_passed=rebuild_result.get("validation", {}).get("passed"),
                validation_details=rebuild_result.get("validation"),
                tenant_id=tenant_id,
                started_at=datetime.fromisoformat(rebuild_result["started_at"]),
                completed_at=datetime.fromisoformat(rebuild_result["completed_at"]) if rebuild_result.get("completed_at") else None,
            )

            session.add(rebuild_job)
            session.commit()
            session.refresh(rebuild_job)

            rebuild_result["rebuild_job_id"] = rebuild_job.id

        logger.info(f"Rebuild job recorded: {rebuild_job.id}")
        return rebuild_result

    def get_rebuild_history(
        self,
        limit: int = 10,
        tenant_id: Optional[str] = None
    ) -> list[Dict[str, Any]]:
        """
        Get recent rebuild jobs

        Args:
            limit: Number of jobs to return
            tenant_id: Optional tenant filter

        Returns:
            List of rebuild job summaries
        """
        with get_db_manager().session_scope() as session:
            query = session.query(IndexRebuildJob)

            if tenant_id:
                query = query.filter(IndexRebuildJob.tenant_id == tenant_id)

            jobs = query.order_by(IndexRebuildJob.created_at.desc()).limit(limit).all()

            return [job.to_dict() for job in jobs]
