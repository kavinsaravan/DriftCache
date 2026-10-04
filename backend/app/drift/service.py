"""Load score windows, run drift detection, and persist reports."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.drift.detector import SimilarityDriftDetector
from app.drift.schemas import DriftConfig, DriftReport, SimilaritySamples
from app.models.cache_event import CacheEvent
from app.models.drift_alert import DriftAlert


class DriftService:
    """Application service for read-only similarity drift monitoring."""

    def __init__(self, session: Session, config: DriftConfig | None = None):
        self.session = session
        self.config = config or DriftConfig()
        self.detector = SimilarityDriftDetector(self.config)

    def run_drift_check(self, tenant_id: str | None = None) -> DriftReport:
        now = datetime.now(timezone.utc)
        recent_start = now - timedelta(hours=self.config.recent_hours)
        reference_end = recent_start
        reference_start = reference_end - timedelta(days=self.config.reference_days)

        reference = SimilaritySamples(
            scores=self._load_scores(
                reference_start,
                reference_end,
                self.config.max_reference_samples,
                tenant_id,
            ),
            start=reference_start,
            end=reference_end,
        )
        recent = SimilaritySamples(
            scores=self._load_scores(
                recent_start,
                now,
                self.config.max_recent_samples,
                tenant_id,
            ),
            start=recent_start,
            end=now,
        )

        report = self.detector.detect(reference, recent)
        self._save_report(report, tenant_id)
        return report

    def _load_scores(
        self,
        start: datetime,
        end: datetime,
        limit: int,
        tenant_id: str | None,
    ) -> list[float]:
        query = self.session.query(CacheEvent.similarity_score).filter(
            and_(
                CacheEvent.created_at >= start,
                CacheEvent.created_at < end,
                CacheEvent.similarity_score.isnot(None),
            )
        )
        if tenant_id is not None:
            query = query.filter(CacheEvent.tenant_id == tenant_id)

        rows = query.order_by(desc(CacheEvent.created_at)).limit(limit).all()
        return [float(score) for (score,) in rows if score is not None]

    def _save_report(self, report: DriftReport, tenant_id: str | None) -> DriftAlert:
        alert = DriftAlert(
            drift_score=report.drift_score,
            severity=report.severity,
            centroid_shift=abs(report.mean_shift),
            variance_shift=report.variance_ratio - 1.0,
            ks_p_value=report.ks_p_value,
            wasserstein_distance=report.wasserstein_distance,
            drift_detected=report.drift_detected,
            reasons=report.reasons,
            avg_similarity_recent=report.recent_mean,
            avg_similarity_reference=report.reference_mean,
            similarity_drop=report.reference_mean - report.recent_mean,
            reference_window_start=report.reference_window_start,
            reference_window_end=report.reference_window_end,
            reference_sample_size=report.reference_sample_size,
            recent_window_start=report.recent_window_start,
            recent_window_end=report.recent_window_end,
            recent_sample_size=report.recent_sample_size,
            recommended_action="review_cache_quality" if report.drift_detected else None,
            action_details=" | ".join(report.reasons),
            tenant_id=tenant_id,
        )
        self.session.add(alert)
        self.session.commit()
        self.session.refresh(alert)
        return alert

    def get_latest_drift_alert(self, tenant_id: str | None = None) -> DriftAlert | None:
        query = self.session.query(DriftAlert)
        if tenant_id is not None:
            query = query.filter(DriftAlert.tenant_id == tenant_id)
        return query.order_by(DriftAlert.created_at.desc()).first()

    def get_drift_history(self, tenant_id: str | None = None, limit: int = 50) -> list[DriftAlert]:
        query = self.session.query(DriftAlert)
        if tenant_id is not None:
            query = query.filter(DriftAlert.tenant_id == tenant_id)
        return query.order_by(DriftAlert.created_at.desc()).limit(limit).all()

    def get_unresolved_alerts(self, tenant_id: str | None = None) -> list[DriftAlert]:
        query = self.session.query(DriftAlert).filter(
            DriftAlert.is_resolved.is_(False),
            DriftAlert.drift_detected.is_(True),
        )
        if tenant_id is not None:
            query = query.filter(DriftAlert.tenant_id == tenant_id)
        return query.order_by(DriftAlert.created_at.desc()).all()

    def resolve_alert(self, alert_id: int, resolution_notes: str) -> bool:
        alert = self.session.query(DriftAlert).filter(DriftAlert.id == alert_id).first()
        if alert is None:
            return False
        alert.is_resolved = True
        alert.resolved_at = datetime.now(timezone.utc)
        alert.resolution_notes = resolution_notes
        self.session.commit()
        return True


@contextmanager
def get_drift_service(session: Session) -> Iterator[DriftService]:
    yield DriftService(session)
