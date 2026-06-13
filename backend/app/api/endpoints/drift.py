"""
Drift Detection API Endpoints

Exposes drift detection and alert management
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database.session import get_db
from app.drift.service import get_drift_service
from app.models.drift_alert import DriftAlert

router = APIRouter()


# Response models
class DriftCheckResponse(BaseModel):
    """Response for drift check"""
    drift_score: float
    severity: str
    signals: dict
    similarity_metrics: dict
    cache_metrics: dict
    windows: dict
    recommendation: dict

    class Config:
        from_attributes = True


class DriftAlertResponse(BaseModel):
    """Response for drift alert"""
    id: int
    drift_score: float
    severity: str
    centroid_shift: float
    variance_shift: float
    ks_p_value: Optional[float]
    avg_similarity_recent: Optional[float]
    avg_similarity_reference: Optional[float]
    similarity_drop: Optional[float]
    cache_hit_rate_recent: Optional[float]
    cache_hit_rate_reference: Optional[float]
    hit_rate_drop: Optional[float]
    recommended_action: Optional[str]
    action_details: Optional[str]
    is_resolved: bool
    resolved_at: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class ResolveAlertRequest(BaseModel):
    """Request to resolve an alert"""
    resolution_notes: str


@router.post("/run-check", response_model=DriftCheckResponse)
async def run_drift_check(
    tenant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Run drift detection check

    Compares recent embeddings against reference baseline to detect semantic drift

    Args:
        tenant_id: Optional tenant isolation
        db: Database session

    Returns:
        Drift detection results with score, severity, and recommendations
    """
    with get_drift_service(session=db) as service:
        result = service.run_drift_check(tenant_id=tenant_id)

    if not result:
        raise HTTPException(
            status_code=400,
            detail="Insufficient data for drift detection. Need more historical embeddings."
        )

    return result.to_dict()


@router.get("/latest", response_model=DriftAlertResponse)
async def get_latest_drift_alert(
    tenant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get most recent drift alert

    Args:
        tenant_id: Optional tenant isolation
        db: Database session

    Returns:
        Latest drift alert
    """
    with get_drift_service(session=db) as service:
        alert = service.get_latest_drift_alert(tenant_id=tenant_id)

    if not alert:
        raise HTTPException(
            status_code=404,
            detail="No drift alerts found"
        )

    return _format_alert_response(alert)


@router.get("/history", response_model=List[DriftAlertResponse])
async def get_drift_history(
    tenant_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    Get drift alert history

    Args:
        tenant_id: Optional tenant isolation
        limit: Maximum alerts to return
        db: Database session

    Returns:
        List of drift alerts
    """
    with get_drift_service(session=db) as service:
        alerts = service.get_drift_history(tenant_id=tenant_id, limit=limit)

    return [_format_alert_response(alert) for alert in alerts]


@router.get("/unresolved", response_model=List[DriftAlertResponse])
async def get_unresolved_alerts(
    tenant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get unresolved drift alerts

    Args:
        tenant_id: Optional tenant isolation
        db: Database session

    Returns:
        List of unresolved drift alerts
    """
    with get_drift_service(session=db) as service:
        alerts = service.get_unresolved_alerts(tenant_id=tenant_id)

    return [_format_alert_response(alert) for alert in alerts]


@router.post("/alerts/{alert_id}/resolve")
async def resolve_drift_alert(
    alert_id: int,
    request: ResolveAlertRequest,
    db: Session = Depends(get_db)
):
    """
    Mark drift alert as resolved

    Args:
        alert_id: Alert ID to resolve
        request: Resolution notes
        db: Database session

    Returns:
        Success message
    """
    with get_drift_service(session=db) as service:
        success = service.resolve_alert(
            alert_id=alert_id,
            resolution_notes=request.resolution_notes
        )

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Alert {alert_id} not found"
        )

    return {
        "message": "Alert resolved successfully",
        "alert_id": alert_id
    }


@router.get("/status")
async def get_drift_status(
    tenant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get current drift status summary

    Args:
        tenant_id: Optional tenant isolation
        db: Database session

    Returns:
        Summary of drift status
    """
    with get_drift_service(session=db) as service:
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
        "recommended_action": latest_alert.recommended_action
    }


def _format_alert_response(alert: DriftAlert) -> DriftAlertResponse:
    """Format DriftAlert for API response"""
    return DriftAlertResponse(
        id=alert.id,
        drift_score=alert.drift_score,
        severity=alert.severity,
        centroid_shift=alert.centroid_shift,
        variance_shift=alert.variance_shift,
        ks_p_value=alert.ks_p_value,
        avg_similarity_recent=alert.avg_similarity_recent,
        avg_similarity_reference=alert.avg_similarity_reference,
        similarity_drop=alert.similarity_drop,
        cache_hit_rate_recent=alert.cache_hit_rate_recent,
        cache_hit_rate_reference=alert.cache_hit_rate_reference,
        hit_rate_drop=alert.hit_rate_drop,
        recommended_action=alert.recommended_action,
        action_details=alert.action_details,
        is_resolved=alert.is_resolved,
        resolved_at=alert.resolved_at.isoformat() if alert.resolved_at else None,
        created_at=alert.created_at.isoformat()
    )
