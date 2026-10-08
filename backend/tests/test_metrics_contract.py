"""Regression tests for the cache-focused metrics API contract."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.endpoints import metrics as metrics_endpoints
from app.metrics import service as metrics_service_module
from app.metrics.calculator import MetricsCalculator
from app.models.cache_event import CacheEvent, CacheStatus
from app.models.provider_call import ProviderCall


def test_summary_uses_recorded_provider_cost_for_cache_savings():
    engine = create_engine("sqlite:///:memory:")
    CacheEvent.__table__.create(engine)
    ProviderCall.__table__.create(engine)
    session = sessionmaker(bind=engine)()
    try:
        session.add_all(
            [
                CacheEvent(
                    request_id="request-hit",
                    cache_status=CacheStatus.HIT,
                    threshold_used=0.85,
                    tenant_id="project:test",
                    model="test-model",
                    latency_ms=4.2,
                ),
                CacheEvent(
                    request_id="request-miss",
                    cache_status=CacheStatus.MISS,
                    threshold_used=0.85,
                    tenant_id="project:test",
                    model="test-model",
                    latency_ms=8.4,
                ),
            ]
        )
        session.add(
            ProviderCall(
                request_id="request-miss",
                provider="openai",
                model="test-model",
                estimated_cost=0.01,
                latency_ms=100.0,
                tenant_id="project:test",
            )
        )
        session.commit()

        summary = MetricsCalculator(session).calculate_summary(
            tenant_id="project:test"
        )

        assert summary == {
            "total_requests": 2,
            "cache_hits": 1,
            "cache_misses": 1,
            "cache_hit_rate": 0.5,
            "estimated_cost_saved_usd": 0.01,
            "calls_avoided": 1,
        }

        latency = MetricsCalculator(session).calculate_dashboard_latency(
            tenant_id="project:test"
        )
        assert latency == {
            "cache_average_ms": 4.2,
            "provider_average_ms": 100.0,
            "speedup_factor": 23.81,
        }
    finally:
        session.close()
        engine.dispose()


def test_dashboard_payload_omits_removed_sections(monkeypatch):
    class FakeCalculator:
        def __init__(self, session):
            pass

        def calculate_summary(self, **kwargs):
            return {
                "total_requests": 0,
                "cache_hits": 0,
                "cache_misses": 0,
                "cache_hit_rate": 0.0,
                "estimated_cost_saved_usd": 0.0,
                "calls_avoided": 0,
            }

        def calculate_dashboard_latency(self, **kwargs):
            return {
                "cache_average_ms": 0.0,
                "provider_average_ms": 0.0,
                "speedup_factor": 0.0,
            }

        def calculate_similarity_distribution(self, **kwargs):
            return {}

    monkeypatch.setattr(metrics_service_module, "MetricsCalculator", FakeCalculator)

    dashboard = metrics_service_module.MetricsService(
        session=object()
    ).get_dashboard_data()

    assert set(dashboard) == {
        "period",
        "generated_at",
        "summary",
        "latency",
        "similarity_distribution",
    }


def test_removed_metrics_routes_are_not_registered():
    route_paths = {route.path for route in metrics_endpoints.router.routes}

    assert "/latency" not in route_paths
    assert "/provider-usage" not in route_paths


def test_latency_time_series_is_rejected():
    calculator = MetricsCalculator(session=object())
    now = datetime.now(timezone.utc)

    with pytest.raises(ValueError, match="metric must be"):
        calculator.calculate_time_series(
            metric="latency",
            since=now - timedelta(hours=1),
            until=now,
        )
