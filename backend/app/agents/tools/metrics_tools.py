"""
Metrics Retrieval Tools

LangChain tools for accessing system metrics and performance data
"""
from typing import Optional, Dict, Any
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import logging

from app.metrics.service import get_metrics_service
from app.database.session import get_db_manager

logger = logging.getLogger(__name__)


class MetricsSummaryInput(BaseModel):
    """Input schema for metrics summary tool"""
    period: str = Field("24h", description="Time period (1h, 24h, 7d, 30d)")
    tenant_id: Optional[str] = Field(None, description="Optional tenant ID")


class MetricsSummaryTool(BaseTool):
    """
    Tool for retrieving system metrics summary

    Provides key performance indicators for cache system
    """
    name: str = "get_metrics_summary"
    description: str = """
    Gets system metrics summary for a time period.

    Returns:
    - total_requests: Total cache requests
    - cache_hits: Number of successful cache hits
    - cache_hit_rate: Hit rate percentage (0-1)
    - estimated_cost_saved_usd: Money saved by caching
    - average_latency_ms: Average response time
    - calls_avoided: LLM API calls prevented

    Use this to understand overall system performance and
    connect ML metrics to business impact.

    Common period values: "1h", "24h", "7d", "30d"
    """
    args_schema: type[BaseModel] = MetricsSummaryInput

    def _run(
        self,
        period: str = "24h",
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get metrics summary"""
        try:
            logger.info(f"Getting metrics summary: period={period}, tenant_id={tenant_id}")

            with get_db_manager().session_scope() as session:
                with get_metrics_service(session=session) as service:
                    summary = service.get_summary(period=period, tenant_id=tenant_id)

                    return {
                        "total_requests": summary["total_requests"],
                        "cache_hits": summary["cache_hits"],
                        "cache_misses": summary["cache_misses"],
                        "cache_hit_rate": round(summary["cache_hit_rate"], 4),
                        "estimated_cost_saved_usd": round(summary["estimated_cost_saved_usd"], 2),
                        "average_latency_ms": round(summary["average_latency_ms"], 1),
                        "calls_avoided": summary["calls_avoided"],
                        "period": period,
                        "status": "success"
                    }

        except Exception as e:
            logger.error(f"Failed to get metrics summary: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }


class LatencyMetricsInput(BaseModel):
    """Input schema for latency metrics tool"""
    period: str = Field("24h", description="Time period")
    tenant_id: Optional[str] = Field(None, description="Optional tenant ID")


class LatencyMetricsTool(BaseTool):
    """
    Tool for retrieving latency performance metrics

    Compares cache hit latency vs provider call latency
    """
    name: str = "get_latency_metrics"
    description: str = """
    Gets latency performance breakdown.

    Returns:
    - cache_latency: Average cache hit response time
    - provider_latency: Average LLM provider response time
    - speedup_factor: How much faster cache is vs provider

    Use this to understand performance benefits of caching
    and detect if cache retrieval is getting slower.

    A decreasing speedup_factor may indicate FAISS index
    degradation requiring rebuild.
    """
    args_schema: type[BaseModel] = LatencyMetricsInput

    def _run(
        self,
        period: str = "24h",
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get latency metrics"""
        try:
            logger.info(f"Getting latency metrics: period={period}, tenant_id={tenant_id}")

            with get_db_manager().session_scope() as session:
                with get_metrics_service(session=session) as service:
                    latency = service.get_latency_breakdown(period=period, tenant_id=tenant_id)

                    return {
                        "cache_latency": {
                            "average_ms": round(latency["cache_latency"]["average_ms"], 2),
                            "min_ms": round(latency["cache_latency"]["min_ms"], 2),
                            "max_ms": round(latency["cache_latency"]["max_ms"], 2),
                        },
                        "provider_latency": {
                            "average_ms": round(latency["provider_latency"]["average_ms"], 2),
                            "min_ms": round(latency["provider_latency"]["min_ms"], 2),
                            "max_ms": round(latency["provider_latency"]["max_ms"], 2),
                        },
                        "speedup_factor": round(latency["speedup_factor"], 2),
                        "period": period,
                        "status": "success"
                    }

        except Exception as e:
            logger.error(f"Failed to get latency metrics: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }


def get_metrics_tools():
    """Get all metrics-related tools"""
    return [
        MetricsSummaryTool(),
        LatencyMetricsTool(),
    ]
