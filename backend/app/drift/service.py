"""
Drift Service Module

Coordinates drift detection workflow and database persistence
"""
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
import logging

from app.drift.windows import WindowSelector
from app.drift.detector import DriftDetector, DriftResult
from app.models.drift_alert import DriftAlert

logger = logging.getLogger(__name__)


class DriftService:
    """Orchestrates drift detection and alert management"""

    def __init__(self, session: Session):
        self.session = session
        self.window_selector = WindowSelector(session)
        self.detector = DriftDetector()

    def run_drift_check(
        self,
        tenant_id: Optional[str] = None
    ) -> Optional[DriftResult]:
        """
        Run complete drift detection workflow

        Args:
            tenant_id: Optional tenant isolation

        Returns:
            DriftResult if successful, None otherwise
        """
        logger.info(f"Starting drift check for tenant_id={tenant_id}")

        # Get reference and recent windows
        try:
            reference_window, recent_window = self.window_selector.get_windows_for_drift_check(
                tenant_id=tenant_id
            )
        except Exception as e:
            logger.error(f"Failed to get embedding windows: {e}")
            return None

        # Run drift detection
        result = self.detector.detect_drift(reference_window, recent_window)

        if not result:
            logger.warning("Drift detection returned no result")
            return None

        # Save alert to database
        try:
            self._save_drift_alert(result, tenant_id)
        except Exception as e:
            logger.error(f"Failed to save drift alert: {e}")
            # Continue anyway - we have the result

        return result

    def get_latest_drift_alert(
        self,
        tenant_id: Optional[str] = None
    ) -> Optional[DriftAlert]:
        """
        Get most recent drift alert

        Args:
            tenant_id: Optional tenant isolation

        Returns:
            Latest DriftAlert or None
        """
        query = self.session.query(DriftAlert)

        if tenant_id:
            query = query.filter(DriftAlert.tenant_id == tenant_id)

        alert = query.order_by(DriftAlert.created_at.desc()).first()

        return alert

    def get_drift_history(
        self,
        tenant_id: Optional[str] = None,
        limit: int = 50
    ) -> List[DriftAlert]:
        """
        Get drift alert history

        Args:
            tenant_id: Optional tenant isolation
            limit: Maximum alerts to return

        Returns:
            List of DriftAlert objects
        """
        query = self.session.query(DriftAlert)

        if tenant_id:
            query = query.filter(DriftAlert.tenant_id == tenant_id)

        alerts = query.order_by(DriftAlert.created_at.desc()).limit(limit).all()

        return alerts

    def get_unresolved_alerts(
        self,
        tenant_id: Optional[str] = None
    ) -> List[DriftAlert]:
        """
        Get unresolved drift alerts

        Args:
            tenant_id: Optional tenant isolation

        Returns:
            List of unresolved DriftAlert objects
        """
        query = self.session.query(DriftAlert).filter(
            DriftAlert.is_resolved == False  # noqa: E712
        )

        if tenant_id:
            query = query.filter(DriftAlert.tenant_id == tenant_id)

        alerts = query.order_by(DriftAlert.created_at.desc()).all()

        return alerts

    def resolve_alert(
        self,
        alert_id: int,
        resolution_notes: str
    ) -> bool:
        """
        Mark drift alert as resolved

        Args:
            alert_id: Alert to resolve
            resolution_notes: Notes about resolution

        Returns:
            True if successful
        """
        alert = self.session.query(DriftAlert).filter(
            DriftAlert.id == alert_id
        ).first()

        if not alert:
            logger.warning(f"Alert {alert_id} not found")
            return False

        alert.is_resolved = True
        alert.resolved_at = datetime.utcnow()
        alert.resolution_notes = resolution_notes

        try:
            self.session.commit()
            logger.info(f"Resolved alert {alert_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to resolve alert {alert_id}: {e}")
            self.session.rollback()
            return False

    def _save_drift_alert(
        self,
        result: DriftResult,
        tenant_id: Optional[str]
    ) -> DriftAlert:
        """
        Save drift result as alert in database

        Args:
            result: DriftResult to save
            tenant_id: Optional tenant ID

        Returns:
            Created DriftAlert
        """
        alert = DriftAlert(
            drift_score=result.drift_score,
            severity=result.severity,
            centroid_shift=result.centroid_shift,
            variance_shift=result.variance_shift,
            ks_p_value=result.ks_p_value,
            avg_similarity_recent=result.avg_similarity_recent,
            avg_similarity_reference=result.avg_similarity_reference,
            similarity_drop=result.similarity_drop,
            cache_hit_rate_recent=result.cache_hit_rate_recent,
            cache_hit_rate_reference=result.cache_hit_rate_reference,
            hit_rate_drop=result.hit_rate_drop,
            reference_window_start=result.reference_window_start,
            reference_window_end=result.reference_window_end,
            reference_sample_size=result.reference_sample_size,
            recent_window_start=result.recent_window_start,
            recent_window_end=result.recent_window_end,
            recent_sample_size=result.recent_sample_size,
            recommended_action=result.recommended_action,
            action_details=result.action_details,
            tenant_id=tenant_id
        )

        self.session.add(alert)
        self.session.commit()
        self.session.refresh(alert)

        logger.info(f"Saved drift alert: {alert}")

        return alert


# Context manager for service
from contextlib import contextmanager


@contextmanager
def get_drift_service(session: Session):
    """
    Context manager for DriftService

    Usage:
        with get_drift_service(session) as service:
            result = service.run_drift_check()
    """
    service = DriftService(session)
    try:
        yield service
    finally:
        pass
