"""Focused regression tests for previously identified runtime bugs."""

from contextlib import contextmanager
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.metrics.calculator import MetricsCalculator
from app.models.cache_entry import CacheEntry
from app.models.cache_schemas import (
    CacheDecision,
    CacheDecisionResult,
    CachedResponse,
    CacheStoreResult,
)
from app.models.schemas import Message
from app.models.training_pair import PairType, TrainingPair
from app.repositories.cache_repo import CacheRepository
from app.services import cache_recorder as cache_recorder_module
from app.services.cache_recorder import CacheRecorder


@pytest.mark.asyncio
async def test_cache_recorder_uses_assigned_vector_id(monkeypatch):
    cache_service = AsyncMock()
    cache_service.store_response.return_value = CacheStoreResult(
        cache_id="cache-123",
        vector_id=42,
    )

    embedding_records = []

    class FakeCacheRepository:
        def __init__(self, session):
            pass

        def create_entry(self, **kwargs):
            return kwargs

        def create_embedding_record(self, **kwargs):
            embedding_records.append(kwargs)
            return kwargs

    class FakeDatabaseManager:
        @contextmanager
        def session_scope(self):
            yield object()

    monkeypatch.setattr(cache_recorder_module, "get_db_manager", FakeDatabaseManager)
    monkeypatch.setattr(cache_recorder_module, "CacheRepository", FakeCacheRepository)

    recorder = CacheRecorder(cache_service=cache_service)
    result = await recorder.store_and_record(
        request_id="request-123",
        messages=[Message(role="user", content="What is caching?")],
        response_text="Caching stores reusable results.",
        model_name="test-model",
    )

    assert result == "cache-123"
    assert embedding_records[0]["faiss_vector_id"] == 42


@pytest.mark.asyncio
async def test_cache_hit_increments_persistent_entry_counter(monkeypatch):
    cached_response = CachedResponse(
        cache_id="cache-hit-123",
        prompt_text="What is caching?",
        response_text="Caching stores reusable results.",
        model_name="test-model",
        embedding_vector=[],
    )
    cache_service = AsyncMock()
    cache_service.check_cache.return_value = CacheDecisionResult(
        decision=CacheDecision.HIT,
        cached_response=cached_response,
        similarity=0.98,
        reason="Semantic match",
    )
    incremented_cache_ids = []

    class NullQuery:
        def filter(self, *args):
            return self

        def order_by(self, *args):
            return self

        def first(self):
            return None

    class FakeSession:
        def query(self, *args):
            return NullQuery()

        def add(self, value):
            pass

        def commit(self):
            pass

    class FakeDatabaseManager:
        @contextmanager
        def session_scope(self):
            yield FakeSession()

    class FakeRequestRepository:
        def __init__(self, session):
            pass

        def create(self, **kwargs):
            return kwargs

    class FakeIndexRepository:
        def __init__(self, session):
            pass

        def get_current(self):
            return None

    class FakeCacheRepository:
        def __init__(self, session):
            pass

        def increment_entry_hits(self, cache_id):
            incremented_cache_ids.append(cache_id)
            return True

    monkeypatch.setattr(cache_recorder_module, "get_db_manager", FakeDatabaseManager)
    monkeypatch.setattr(cache_recorder_module, "RequestRepository", FakeRequestRepository)
    monkeypatch.setattr(cache_recorder_module, "CacheRepository", FakeCacheRepository)
    monkeypatch.setattr(cache_recorder_module, "get_active_threshold", lambda *args, **kwargs: 0.9)
    monkeypatch.setattr("app.repositories.index_repo.IndexRepository", FakeIndexRepository)

    recorder = CacheRecorder(cache_service=cache_service)
    await recorder.check_and_record(
        messages=[Message(role="user", content="What is caching?")],
        model_name="test-model",
        tenant_id="project:test",
    )

    assert incremented_cache_ids == ["cache-hit-123"]


def test_cache_hit_increment_is_persisted():
    engine = create_engine("sqlite:///:memory:")
    CacheEntry.__table__.create(engine)
    session = sessionmaker(bind=engine)()
    try:
        entry = CacheEntry(
            cache_id="cache-123",
            prompt_text="What is caching?",
            prompt_hash="hash",
            response_text="Caching stores reusable results.",
            model="test-model",
            tenant_id="project:test",
        )
        session.add(entry)
        session.commit()

        assert CacheRepository(session).increment_entry_hits("cache-123") is True
        assert CacheRepository(session).increment_entry_hits("cache-123") is True
        assert CacheRepository(session).increment_entry_hits("missing") is False
        session.refresh(entry)
        assert entry.cache_hits == 2
        assert entry.last_accessed is not None
    finally:
        session.close()
        engine.dispose()


class _SimilarityQuery:
    def __init__(self, scores):
        self.scores = scores

    def filter(self, *args):
        return self

    def all(self):
        return [(score,) for score in self.scores]


class _SimilaritySession:
    def __init__(self, scores):
        self.scores = scores

    def query(self, *args):
        return _SimilarityQuery(self.scores)


def test_similarity_distribution_counts_identical_and_boundary_scores():
    calculator = MetricsCalculator(_SimilaritySession([0.5, 0.5, 1.0]))

    distribution = calculator.calculate_similarity_distribution(bins=10)

    assert sum(distribution.values()) == 3
    assert distribution["0.50-0.60"] == 2
    assert distribution["0.90-1.00"] == 1


def test_similarity_distribution_rejects_nonpositive_bin_count():
    calculator = MetricsCalculator(_SimilaritySession([0.5]))

    with pytest.raises(ValueError, match="greater than zero"):
        calculator.calculate_similarity_distribution(bins=0)


@pytest.mark.parametrize(
    ("score", "expected"),
    [(0.0, "similarity=0.000"), (0.81234, "similarity=0.812"), (None, "similarity=N/A")],
)
def test_training_pair_repr_handles_all_similarity_values(score, expected):
    pair = TrainingPair(id=1, pair_type=PairType.POSITIVE, similarity_score=score)

    assert expected in repr(pair)
