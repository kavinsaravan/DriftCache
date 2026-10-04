"""Tests for deterministic cache-similarity drift detection."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.drift.detector import SimilarityDriftDetector
from app.drift.schemas import DriftConfig, SimilaritySamples


def samples(scores):
    end = datetime.now(timezone.utc)
    return SimilaritySamples(scores=scores, start=end - timedelta(hours=1), end=end)


def test_identical_distributions_do_not_trigger_drift():
    scores = [0.70 + index * 0.001 for index in range(60)]
    report = SimilarityDriftDetector().detect(samples(scores), samples(scores.copy()))

    assert report.status == "stable"
    assert report.drift_detected is False
    assert report.ks_p_value == pytest.approx(1.0)
    assert report.wasserstein_distance == pytest.approx(0.0)


def test_shifted_distribution_triggers_drift():
    reference = [0.80 + index * 0.001 for index in range(60)]
    recent = [0.55 + index * 0.001 for index in range(60)]
    report = SimilarityDriftDetector().detect(samples(reference), samples(recent))

    assert report.status == "drift_detected"
    assert report.drift_detected is True
    assert report.ks_p_value < 0.05
    assert report.wasserstein_distance == pytest.approx(0.25)
    assert report.mean_shift == pytest.approx(-0.25)


def test_insufficient_samples_return_inconclusive_report():
    detector = SimilarityDriftDetector(DriftConfig(minimum_samples=10))
    report = detector.detect(samples([0.8] * 9), samples([0.7] * 10))

    assert report.status == "insufficient_data"
    assert report.drift_detected is False
    assert report.reference_sample_size == 9


def test_constant_distributions_are_handled_safely():
    detector = SimilarityDriftDetector()
    report = detector.detect(samples([0.8] * 40), samples([0.8] * 40))

    assert report.status == "stable"
    assert report.variance_ratio == pytest.approx(1.0)


def test_malformed_similarity_scores_are_rejected():
    with pytest.raises(ValidationError):
        samples([float("nan")])

    with pytest.raises(ValidationError):
        samples([1.1])


def test_service_loads_tenant_windows_and_persists_report():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.database.base import Base
    from app.drift.service import DriftService
    from app.models.cache_event import CacheEvent, CacheStatus
    from app.models.drift_alert import DriftAlert

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    now = datetime.now(timezone.utc)

    for index in range(35):
        session.add(
            CacheEvent(
                request_id=f"reference-{index}",
                cache_status=CacheStatus.HIT,
                similarity_score=0.80 + index * 0.001,
                threshold_used=0.75,
                tenant_id="tenant-a",
                model="test-model",
                created_at=now - timedelta(days=2),
            )
        )
        session.add(
            CacheEvent(
                request_id=f"recent-{index}",
                cache_status=CacheStatus.HIT,
                similarity_score=0.55 + index * 0.001,
                threshold_used=0.75,
                tenant_id="tenant-a",
                model="test-model",
                created_at=now - timedelta(hours=1),
            )
        )
    session.commit()

    report = DriftService(session).run_drift_check(tenant_id="tenant-a")

    assert report.drift_detected is True
    saved = session.query(DriftAlert).one()
    assert saved.tenant_id == "tenant-a"
    assert saved.wasserstein_distance == pytest.approx(0.25)
    assert saved.reasons
