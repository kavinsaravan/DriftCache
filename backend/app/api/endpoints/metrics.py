"""
Metrics API Endpoints

Provides dashboard metrics and analytics
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.metrics.service import get_metrics_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/summary")
async def get_metrics_summary(
    period: str = Query("24h", description="Time period: 1h, 24h, 7d, 30d"),
    tenant_id: Optional[str] = Query(None, description="Optional tenant filter"),
    db: Session = Depends(get_db)
):
    """
    Get summary metrics for dashboard

    Returns:
    ```json
    {
        "total_requests": 1200,
        "cache_hits": 720,
        "cache_misses": 480,
        "cache_hit_rate": 0.60,
        "estimated_cost_saved_usd": 42.73,
        "average_latency_ms": 310,
        "total_provider_calls": 480,
        "calls_avoided": 720
    }
    ```

    This is the key endpoint that proves DriftCache's value!
    """
    with get_metrics_service(session=db) as service:
        return service.get_summary(period=period, tenant_id=tenant_id)


@router.get("/latency")
async def get_latency_stats(
    period: str = Query("24h", description="Time period"),
    tenant_id: Optional[str] = Query(None, description="Optional tenant filter"),
    db: Session = Depends(get_db)
):
    """
    Get latency statistics

    Returns cache vs provider latency comparison

    Shows how much faster cache is than LLM calls
    """
    with get_metrics_service(session=db) as service:
        return service.get_latency_stats(period=period, tenant_id=tenant_id)


@router.get("/similarity-distribution")
async def get_similarity_distribution(
    period: str = Query("24h", description="Time period"),
    bins: int = Query(10, ge=5, le=20, description="Number of histogram bins"),
    tenant_id: Optional[str] = Query(None, description="Optional tenant filter"),
    db: Session = Depends(get_db)
):
    """
    Get similarity score distribution

    Returns histogram of similarity scores

    Helps understand if threshold is too strict or too loose

    Example:
    ```json
    {
        "0.70-0.80": 42,
        "0.80-0.90": 108,
        "0.90-1.00": 350
    }
    ```
    """
    with get_metrics_service(session=db) as service:
        return service.get_similarity_distribution(
            period=period,
            bins=bins,
            tenant_id=tenant_id
        )


@router.get("/top-cached-prompts")
async def get_top_cached_prompts(
    limit: int = Query(10, ge=1, le=100, description="Maximum results"),
    period: str = Query("24h", description="Time period"),
    tenant_id: Optional[str] = Query(None, description="Optional tenant filter"),
    db: Session = Depends(get_db)
):
    """
    Get top cached prompts by hit count

    Shows which prompts are being cached most frequently

    Great for understanding usage patterns
    """
    with get_metrics_service(session=db) as service:
        return service.get_top_cached_prompts(
            limit=limit,
            period=period,
            tenant_id=tenant_id
        )


@router.get("/provider-usage")
async def get_provider_usage(
    period: str = Query("24h", description="Time period"),
    tenant_id: Optional[str] = Query(None, description="Optional tenant filter"),
    db: Session = Depends(get_db)
):
    """
    Get provider usage statistics

    Returns breakdown by provider and model

    Shows:
    - Total calls per provider
    - Total tokens used
    - Total cost per provider
    - Model-level breakdown
    """
    with get_metrics_service(session=db) as service:
        return service.get_provider_usage(period=period, tenant_id=tenant_id)


@router.get("/time-series/{metric}")
async def get_time_series(
    metric: str,
    period: str = Query("24h", description="Time period"),
    interval: str = Query("1h", description="Bucket size: 5m, 1h, 1d"),
    tenant_id: Optional[str] = Query(None, description="Optional tenant filter"),
    db: Session = Depends(get_db)
):
    """
    Get time series data for a metric

    Metrics:
    - hit_rate: Cache hit rate over time
    - latency: Average latency over time
    - requests: Request count over time

    Used for dashboard charts
    """
    valid_metrics = ["hit_rate", "latency", "requests"]
    if metric not in valid_metrics:
        return {
            "error": f"Invalid metric. Must be one of: {', '.join(valid_metrics)}"
        }

    with get_metrics_service(session=db) as service:
        return service.get_time_series(
            metric=metric,
            period=period,
            interval=interval,
            tenant_id=tenant_id
        )


@router.get("/dashboard")
async def get_dashboard_data(
    period: str = Query("24h", description="Time period"),
    tenant_id: Optional[str] = Query(None, description="Optional tenant filter"),
    db: Session = Depends(get_db)
):
    """
    Get complete dashboard data in one call

    Returns everything the dashboard needs:
    - Summary metrics
    - Latency comparison
    - Similarity distribution
    - Top cached prompts
    - Provider usage

    This reduces API calls for the frontend
    """
    with get_metrics_service(session=db) as service:
        return service.get_dashboard_data(period=period, tenant_id=tenant_id)


@router.get("/health")
async def metrics_health():
    """Metrics service health check"""
    return {
        "status": "healthy",
        "service": "metrics",
        "features": [
            "summary_metrics",
            "latency_analysis",
            "similarity_distribution",
            "cost_tracking",
            "provider_usage",
            "time_series"
        ]
    }
