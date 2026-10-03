"""
Threshold Configuration Service

Manages active similarity threshold from database
"""
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.threshold_version import ThresholdVersion
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


def get_active_threshold(db: Session, tenant_id: str = "default") -> float:
    """
    Get currently active similarity threshold

    Args:
        db: Database session
        tenant_id: Tenant ID (defaults to "default")

    Returns:
        Active threshold value (falls back to settings if no DB threshold)
    """
    try:
        # Query for active threshold
        active_threshold = db.query(ThresholdVersion).filter(
            ThresholdVersion.is_active == True,
            ThresholdVersion.tenant_id == tenant_id
        ).order_by(ThresholdVersion.active_from.desc()).first()

        if active_threshold:
            return active_threshold.threshold_value

    except Exception as e:
        logger.warning(f"Failed to get threshold from DB: {e}")

    # Fallback to settings
    return settings.SIMILARITY_THRESHOLD


def set_active_threshold(
    db: Session,
    new_threshold: float,
    reason: str,
    created_by: str = "manual",
    tenant_id: str = "default",
    metrics_before: Optional[dict] = None,
    metrics_after_estimate: Optional[dict] = None
) -> ThresholdVersion:
    """
    Set new active threshold

    Args:
        db: Database session
        new_threshold: New threshold value
        reason: Reason for change
        created_by: Who/what created this change
        tenant_id: Optional tenant ID
        metrics_before: Optional metrics before change
        metrics_after_estimate: Optional estimated metrics after change

    Returns:
        New ThresholdVersion record
    """
    # Get current active threshold
    old_threshold_record = db.query(ThresholdVersion).filter(
        ThresholdVersion.is_active == True,
        ThresholdVersion.tenant_id == tenant_id
    ).first()

    old_threshold_value = old_threshold_record.threshold_value if old_threshold_record else settings.SIMILARITY_THRESHOLD

    # Deactivate old threshold
    if old_threshold_record:
        old_threshold_record.is_active = False
        old_threshold_record.active_until = datetime.utcnow()

    # Create new threshold version
    new_threshold_record = ThresholdVersion(
        old_threshold=old_threshold_value,
        threshold_value=new_threshold,
        reason=reason,
        created_by=created_by,
        active_from=datetime.utcnow(),
        active_until=None,
        is_active=True,
        deployed_at=datetime.utcnow(),
        tenant_id=tenant_id,
        precision_before=metrics_before.get("precision") if metrics_before else None,
        recall_before=metrics_before.get("recall") if metrics_before else None,
        false_hit_rate_before=metrics_before.get("false_hit_rate") if metrics_before else None,
        false_miss_rate_before=metrics_before.get("false_miss_rate") if metrics_before else None,
        precision_after_estimate=metrics_after_estimate.get("precision") if metrics_after_estimate else None,
        recall_after_estimate=metrics_after_estimate.get("recall") if metrics_after_estimate else None,
        false_hit_rate_after_estimate=metrics_after_estimate.get("false_hit_rate") if metrics_after_estimate else None,
        false_miss_rate_after_estimate=metrics_after_estimate.get("false_miss_rate") if metrics_after_estimate else None,
    )

    db.add(new_threshold_record)
    db.commit()
    db.refresh(new_threshold_record)

    logger.info(
        f"Updated threshold: {old_threshold_value} -> {new_threshold} "
        f"(reason: {reason}, created_by: {created_by})"
    )

    return new_threshold_record
