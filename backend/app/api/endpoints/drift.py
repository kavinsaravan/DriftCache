"""API endpoints for similarity-score drift reports."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.drift.schemas import DriftReport
from app.drift.service import get_drift_service
from app.models.drift_alert import DriftAlert

router = APIRouter()


class DriftAlertResponse(BaseModel):
    id: int
    drift_score: float
    drift_detected: bool
    severity: str
    ks_p_value: Optional[float]
    wasserstein_distance: Optional[float]
    reference_mean: Optional[float]
    recent_mean: Optional[float]
    mean_shift: Optional[float]
    variance_ratio: Optional[float]
    reference_sample_size: int
    recent_sample_size: int
    reasons: list[str]
    is_resolved: bool
    resolved_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResolveAlertRequest(BaseModel):
    resolution_notes: str


@router.post("/run-check", response_model=DriftReport)
def run_drift_check(
    tenant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Compare recent and historical cache-similarity distributions."""
    with get_drift_service(session=db) as service:
        return service.run_drift_check(tenant_id=tenant_id)


@router.get("/latest", response_model=DriftAlertResponse)
def get_latest_drift_alert(
    tenant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    with get_drift_service(session=db) as service:
        alert = service.get_latest_drift_alert(tenant_id=tenant_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="No drift reports found")
    return _format_alert_response(alert)


@router.get("/history", response_model=list[DriftAlertResponse])
def get_drift_history(
    tenant_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    with get_drift_service(session=db) as service:
        alerts = service.get_drift_history(tenant_id=tenant_id, limit=limit)
    return [_format_alert_response(alert) for alert in alerts]


@router.get("/unresolved", response_model=list[DriftAlertResponse])
def get_unresolved_alerts(
    tenant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    with get_drift_service(session=db) as service:
        alerts = service.get_unresolved_alerts(tenant_id=tenant_id)
    return [_format_alert_response(alert) for alert in alerts]


@router.post("/alerts/{alert_id}/resolve")
def resolve_drift_alert(
    alert_id: int,
    request: ResolveAlertRequest,
    db: Session = Depends(get_db),
):
    with get_drift_service(session=db) as service:
        resolved = service.resolve_alert(alert_id, request.resolution_notes)
    if not resolved:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return {"message": "Alert resolved successfully", "alert_id": alert_id}


@router.get("/status")
def get_drift_status(
    tenant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    with get_drift_service(session=db) as service:
        latest = service.get_latest_drift_alert(tenant_id=tenant_id)
        unresolved = service.get_unresolved_alerts(tenant_id=tenant_id)
    if latest is None:
        return {"status": "unknown", "message": "No drift checks have been run", "unresolved_count": 0}
    return {
        "status": "drift_detected" if latest.drift_detected else "stable",
        "severity": latest.severity,
        "drift_score": latest.drift_score,
        "last_check": latest.created_at.isoformat(),
        "unresolved_count": len(unresolved),
    }


def _format_alert_response(alert: DriftAlert) -> DriftAlertResponse:
    reference_mean = alert.avg_similarity_reference
    recent_mean = alert.avg_similarity_recent
    return DriftAlertResponse(
        id=alert.id,
        drift_score=alert.drift_score,
        drift_detected=alert.drift_detected,
        severity=alert.severity,
        ks_p_value=alert.ks_p_value,
        wasserstein_distance=alert.wasserstein_distance,
        reference_mean=reference_mean,
        recent_mean=recent_mean,
        mean_shift=(recent_mean - reference_mean) if recent_mean is not None and reference_mean is not None else None,
        variance_ratio=(alert.variance_shift + 1.0) if alert.variance_shift is not None else None,
        reference_sample_size=alert.reference_sample_size,
        recent_sample_size=alert.recent_sample_size,
        reasons=alert.reasons or ([alert.action_details] if alert.action_details else []),
        is_resolved=alert.is_resolved,
        resolved_at=alert.resolved_at,
        created_at=alert.created_at,
    )
