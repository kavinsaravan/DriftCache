"""
Threshold Management Tools

LangChain tools for reading and updating similarity threshold configuration
"""
from typing import Optional, Dict, Any
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import logging
from datetime import datetime
from app.database.session import SessionLocal
from app.services.threshold_config import get_active_threshold, set_active_threshold

logger = logging.getLogger(__name__)


class GetThresholdInput(BaseModel):
    """Input schema for get threshold tool"""
    tenant_id: str = Field("default", description="Tenant ID")


class GetThresholdTool(BaseTool):
    """
    Tool for retrieving current similarity threshold

    Returns active threshold configuration
    """
    name: str = "get_current_threshold"
    description: str = """
    Gets the current active similarity threshold.

    Returns:
    - current_threshold: Active threshold value (0-1)
    - last_updated: When threshold was last changed
    - set_by: Who/what set the threshold (manual, agent, system)

    Use this before making threshold adjustment decisions
    to understand current configuration.
    """
    args_schema: type[BaseModel] = GetThresholdInput

    def _run(self, tenant_id: str = "default") -> Dict[str, Any]:
        """Get current threshold from database"""
        try:
            logger.info(f"Getting current threshold for tenant_id={tenant_id}")

            db = SessionLocal()
            try:
                current_threshold = get_active_threshold(db, tenant_id=tenant_id)

                return {
                    "current_threshold": current_threshold,
                    "last_updated": datetime.utcnow().isoformat(),
                    "set_by": "database",
                    "tenant_id": tenant_id,
                    "status": "success"
                }
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Failed to get threshold: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }


class UpdateThresholdInput(BaseModel):
    """Input schema for update threshold tool"""
    new_threshold: float = Field(..., ge=0.0, le=1.0, description="New threshold value (0-1)")
    reason: str = Field(..., description="Reason for threshold change")
    dry_run: bool = Field(True, description="If True, only simulate update")
    tenant_id: str = Field("default", description="Tenant ID")


class UpdateThresholdTool(BaseTool):
    """
    Tool for updating similarity threshold

    First autonomous optimization action
    """
    name: str = "update_similarity_threshold"
    description: str = """
    Updates the active similarity threshold.

    Use cases:
    - Increase threshold (e.g., 0.90 -> 0.92) when:
      * False hit rate is too high (>0.10)
      * Precision needs improvement
      * Cache serving wrong answers

    - Decrease threshold (e.g., 0.90 -> 0.88) when:
      * False miss rate is too high (>0.40)
      * Recall needs improvement
      * Missing cost savings with good precision

    By default runs in dry-run mode .
    Will enable actual threshold updates.

    Returns success status and impact simulation.
    """
    args_schema: type[BaseModel] = UpdateThresholdInput

    def _run(
        self,
        new_threshold: float,
        reason: str,
        dry_run: bool = True,
        tenant_id: str = "default"
    ) -> Dict[str, Any]:
        """Update threshold"""
        try:
            logger.info(
                f"Threshold update: new_threshold={new_threshold}, "
                f"reason={reason}, dry_run={dry_run}, tenant_id={tenant_id}"
            )

            # Validate threshold range
            if not 0.0 <= new_threshold <= 1.0:
                return {
                    "error": "Threshold must be between 0.0 and 1.0",
                    "status": "failed"
                }

            db = SessionLocal()
            try:
                # Get current threshold
                old_threshold = get_active_threshold(db, tenant_id=tenant_id)

                # Compute real impact using evaluation dataset
                direction = "increase" if new_threshold > old_threshold else "decrease"

                # Load evaluation dataset and compute metrics at both thresholds
                from app.evaluation.dataset_loader import get_cached_evaluation_dataset
                from app.optimization.threshold_search import ThresholdSearcher

                eval_dataset = get_cached_evaluation_dataset()
                searcher = ThresholdSearcher()

                # Evaluate at old threshold
                old_metrics = searcher._evaluate_threshold(old_threshold, eval_dataset)

                # Evaluate at new threshold
                new_metrics = searcher._evaluate_threshold(new_threshold, eval_dataset)

                # Calculate actual changes
                estimated_precision_change = new_metrics["precision"] - old_metrics["precision"]
                estimated_recall_change = new_metrics["recall"] - old_metrics["recall"]
                estimated_false_hit_change = new_metrics["false_hit_rate"] - old_metrics["false_hit_rate"]

                if dry_run:
                    # Simulation mode
                    return {
                        "status": "simulated",
                        "old_threshold": old_threshold,
                        "new_threshold": new_threshold,
                        "change": round(new_threshold - old_threshold, 4),
                        "direction": direction,
                        "reason": reason,
                        "action": "would_update",
                        "message": f"DRY RUN: Would update threshold from {old_threshold} to {new_threshold}",
                        "estimated_impact": {
                            "precision_change": f"{estimated_precision_change:+.2%}",
                            "recall_change": f"{estimated_recall_change:+.2%}",
                            "false_hit_change": f"{estimated_false_hit_change:+.2%}",
                            "old_precision": round(old_metrics["precision"], 4),
                            "new_precision": round(new_metrics["precision"], 4),
                            "old_recall": round(old_metrics["recall"], 4),
                            "new_recall": round(new_metrics["recall"], 4),
                            "old_false_hit_rate": round(old_metrics["false_hit_rate"], 4),
                            "new_false_hit_rate": round(new_metrics["false_hit_rate"], 4),
                            "recommendation": (
                                "Increase precision, slight recall drop" if direction == "increase"
                                else "Increase recall, slight precision risk"
                            )
                        },
                        "details": {
                            "would_update_config": True,
                            "would_log_change": True,
                            "would_notify": True,
                            "requires_restart": False,
                            "reason": reason
                        }
                    }
                else:
                    # Actually update the threshold
                    new_record = set_active_threshold(
                        db=db,
                        new_threshold=new_threshold,
                        reason=reason,
                        created_by="agent:threshold_optimizer",
                        tenant_id=tenant_id
                    )

                    return {
                        "status": "applied",
                        "old_threshold": old_threshold,
                        "new_threshold": new_threshold,
                        "change": round(new_threshold - old_threshold, 4),
                        "direction": direction,
                        "reason": reason,
                        "action": "updated",
                        "message": f"Updated threshold from {old_threshold} to {new_threshold}",
                        "threshold_version_id": new_record.id,
                        "deployed_at": new_record.deployed_at.isoformat(),
                        "details": {
                            "updated_config": True,
                            "logged_change": True,
                            "requires_restart": False,
                            "reason": reason
                        }
                    }
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Threshold update failed: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }


def get_threshold_tools():
    """Get all threshold-related tools"""
    return [
        GetThresholdTool(),
        UpdateThresholdTool(),
    ]
