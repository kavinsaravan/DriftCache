"""
Drift Analysis Tools

LangChain tools for semantic drift detection and analysis
"""
from typing import Optional, Dict, Any
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import logging

from app.drift.service import get_drift_service
from app.database.session import get_db_manager

logger = logging.getLogger(__name__)


class DriftAnalysisInput(BaseModel):
    """Input schema for drift analysis tool"""
    tenant_id: Optional[str] = Field(None, description="Optional tenant ID for isolation")


class DriftAnalysisTool(BaseTool):
    """
    Tool for running or retrieving drift analysis

    Analyzes semantic drift by comparing recent embeddings
    against reference baseline to detect distribution changes
    """
    name: str = "run_drift_analysis"
    description: str = """
    Runs drift detection analysis to detect semantic distribution changes.

    Returns drift score, severity, and statistical signals including:
    - centroid_shift: How much average query topic moved (0-1)
    - variance_shift: Change in query diversity
    - ks_p_value: Statistical significance of distribution change
    - similarity_drop: Decrease in average cache match quality
    - hit_rate_drop: Cache performance impact

    Use this tool to understand if user prompt patterns are changing
    over time, which may require cache optimization.
    """
    args_schema: type[BaseModel] = DriftAnalysisInput

    def _run(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Run drift analysis"""
        try:
            logger.info(f"Running drift analysis for tenant_id={tenant_id}")

            with get_db_manager().session_scope() as session:
                with get_drift_service(session=session) as service:
                    # Try to get latest drift alert first
                    latest_alert = service.get_latest_drift_alert(tenant_id=tenant_id)

                    # If no recent alert (< 1 hour old), run new check
                    if latest_alert is None:
                        result = service.run_drift_check(tenant_id=tenant_id)
                        if not result:
                            return {
                                "error": "Insufficient data for drift detection",
                                "status": "failed"
                            }

                        return result.to_dict()

                    # Return existing alert
                    return {
                        "drift_score": latest_alert.drift_score,
                        "severity": latest_alert.severity,
                        "signals": {
                            "centroid_shift": latest_alert.centroid_shift,
                            "variance_shift": latest_alert.variance_shift,
                            "ks_p_value": latest_alert.ks_p_value,
                        },
                        "similarity_metrics": {
                            "avg_similarity_recent": latest_alert.avg_similarity_recent,
                            "avg_similarity_reference": latest_alert.avg_similarity_reference,
                            "similarity_drop": latest_alert.similarity_drop,
                        },
                        "cache_metrics": {
                            "cache_hit_rate_recent": latest_alert.cache_hit_rate_recent,
                            "cache_hit_rate_reference": latest_alert.cache_hit_rate_reference,
                            "hit_rate_drop": latest_alert.hit_rate_drop,
                        },
                        "recommendation": {
                            "action": latest_alert.recommended_action,
                            "details": latest_alert.action_details,
                        },
                        "created_at": latest_alert.created_at.isoformat(),
                        "status": "success"
                    }

        except Exception as e:
            logger.error(f"Drift analysis failed: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }


class DriftStatusInput(BaseModel):
    """Input schema for drift status tool"""
    tenant_id: Optional[str] = Field(None, description="Optional tenant ID")


class DriftStatusTool(BaseTool):
    """
    Tool for getting current drift status summary

    Quick overview of drift state without running full analysis
    """
    name: str = "get_drift_status"
    description: str = """
    Gets current drift status summary.

    Returns:
    - Current drift severity (low/medium/high/critical)
    - Latest drift score
    - When last drift check was run
    - Number of unresolved drift alerts
    - Recommended action

    Use this for quick drift health check before deciding
    if full analysis is needed.
    """
    args_schema: type[BaseModel] = DriftStatusInput

    def _run(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get drift status"""
        try:
            with get_db_manager().session_scope() as session:
                with get_drift_service(session=session) as service:
                    latest_alert = service.get_latest_drift_alert(tenant_id=tenant_id)
                    unresolved_alerts = service.get_unresolved_alerts(tenant_id=tenant_id)

                    if not latest_alert:
                        return {
                            "status": "unknown",
                            "message": "No drift checks have been run yet",
                            "unresolved_count": 0
                        }

                    return {
                        "status": latest_alert.severity,
                        "drift_score": latest_alert.drift_score,
                        "last_check": latest_alert.created_at.isoformat(),
                        "unresolved_count": len(unresolved_alerts),
                        "recommended_action": latest_alert.recommended_action,
                        "needs_attention": latest_alert.severity in ["high", "critical"]
                    }

        except Exception as e:
            logger.error(f"Failed to get drift status: {e}")
            return {
                "error": str(e),
                "status": "error"
            }


def get_drift_tools():
    """Get all drift-related tools"""
    return [
        DriftAnalysisTool(),
        DriftStatusTool(),
    ]
