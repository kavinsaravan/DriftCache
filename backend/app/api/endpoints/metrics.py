"""
Metrics API Endpoints

Provides dashboard metrics and analytics
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.metrics.service import get_metrics_service
from app.core.auth import verify_metrics_key
from app.services.api_keys import AuthContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _tenant_scope(auth: AuthContext, requested_tenant: Optional[str]) -> Optional[str]:
    """Admins may select a tenant; every other credential is fixed to its tenant."""
    if auth.is_admin:
        return requested_tenant
    return auth.tenant_id


@router.get("/summary")
async def get_metrics_summary(
    period: str = Query("24h", description="Time period: 1h, 24h, 7d, 30d"),
    tenant_id: Optional[str] = Query(None, description="Optional tenant filter"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(verify_metrics_key),
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
        "calls_avoided": 720
    }
    ```

    This endpoint supplies the dashboard's cache activity cards.
    """
    with get_metrics_service(session=db) as service:
        return service.get_summary(period=period, tenant_id=_tenant_scope(auth, tenant_id))


@router.get("/similarity-distribution")
async def get_similarity_distribution(
    period: str = Query("24h", description="Time period"),
    bins: int = Query(10, ge=5, le=20, description="Number of histogram bins"),
    tenant_id: Optional[str] = Query(None, description="Optional tenant filter"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(verify_metrics_key),
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
            tenant_id=_tenant_scope(auth, tenant_id)
        )


@router.get("/top-cached-prompts")
async def get_top_cached_prompts(
    limit: int = Query(10, ge=1, le=100, description="Maximum results"),
    period: str = Query("24h", description="Time period"),
    tenant_id: Optional[str] = Query(None, description="Optional tenant filter"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(verify_metrics_key),
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
            tenant_id=_tenant_scope(auth, tenant_id)
        )


@router.get("/time-series/{metric}")
async def get_time_series(
    metric: str,
    period: str = Query("24h", description="Time period"),
    interval: str = Query("1h", description="Bucket size: 5m, 1h, 1d"),
    tenant_id: Optional[str] = Query(None, description="Optional tenant filter"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(verify_metrics_key),
):
    """
    Get time series data for a metric

    Metrics:
    - hit_rate: Cache hit rate over time
    - requests: Request count over time

    Used for dashboard charts
    """
    valid_metrics = ["hit_rate", "requests"]
    if metric not in valid_metrics:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid metric. Must be one of: {', '.join(valid_metrics)}",
        )

    with get_metrics_service(session=db) as service:
        return service.get_time_series(
            metric=metric,
            period=period,
            interval=interval,
            tenant_id=_tenant_scope(auth, tenant_id)
        )


@router.get("/dashboard")
async def get_dashboard_data(
    period: str = Query("24h", description="Time period"),
    tenant_id: Optional[str] = Query(None, description="Optional tenant filter"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(verify_metrics_key),
):
    """
    Get complete dashboard data in one call

    Returns everything the dashboard needs:
    - Summary metrics
    - Cache/provider speedup
    - Similarity distribution

    This reduces API calls for the frontend
    """
    with get_metrics_service(session=db) as service:
        return service.get_dashboard_data(
            period=period,
            tenant_id=_tenant_scope(auth, tenant_id),
        )


@router.get("/health")
async def metrics_health(_auth: AuthContext = Depends(verify_metrics_key)):
    """Metrics service health check"""
    return {
        "status": "healthy",
        "service": "metrics",
        "features": [
            "summary_metrics",
            "dashboard_impact",
            "similarity_distribution",
            "time_series"
        ]
    }
