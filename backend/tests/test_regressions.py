"""Focused regression tests for previously identified runtime bugs."""

from contextlib import contextmanager
from unittest.mock import AsyncMock

import pytest

from app.metrics.calculator import MetricsCalculator
from app.models.cache_schemas import CacheStoreResult
from app.models.schemas import Message
from app.models.training_pair import PairType, TrainingPair
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
