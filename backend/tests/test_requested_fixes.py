"""Regression coverage for request history, model isolation and drift observations."""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.endpoints.metrics import router
from app.core.auth import verify_metrics_key
from app.database.session import get_db
from app.models.request import Request
from app.models.cache_event import CacheEvent, CacheStatus
from app.models.cache_schemas import CacheConfig, CachedResponse, CacheDecision
from app.models.search_schemas import VectorMetadata, SearchResult, SearchResults
from app.cache.service import CacheService
from app.cache.decision import CacheDecisionEngine
from app.services.cache_recorder import CacheRecorder
from app.services.api_keys import AuthContext
from app.vectorstore.search import SemanticSearchService
from app.vectorstore.storage import MetadataStore


def test_history_records_misses_and_scopes_pagination():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Request.__table__.create(engine)
    CacheEvent.__table__.create(engine)
    db = sessionmaker(bind=engine)()
    for i, (tenant, status) in enumerate([('a', CacheStatus.HIT), ('a', CacheStatus.THRESHOLD_NOT_MET), ('b', CacheStatus.MISS)]):
        db.add(Request(request_id=f'r{i}', tenant_id=tenant, model='m', messages_json=[], prompt_text=f'prompt-{i}', prompt_hash=str(i)))
        db.add(CacheEvent(request_id=f'r{i}', tenant_id=tenant, model='m', cache_status=status, threshold_used=.85, similarity_score=.95 if i == 0 else .4))
    db.commit()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[verify_metrics_key] = lambda: AuthContext(tenant_id='a')
    with TestClient(app) as client:
        result = client.get('/metrics/requests?tenant_id=b&limit=1').json()
        assert result['total'] == 2
        assert result['items'][0]['status'] == 'THRESHOLD_NOT_MET'
        assert result['items'][0]['prompt'] == 'prompt-1'
        assert client.get('/metrics/requests?offset=1&limit=1').json()['items'][0]['status'] == 'HIT'
        assert client.get('/metrics/requests?limit=0').status_code == 422
    app.dependency_overrides[verify_metrics_key] = lambda: AuthContext(tenant_id='a', is_admin=True)
    with TestClient(app) as client:
        assert client.get('/metrics/requests?tenant_id=b').json()['total'] == 1
    db.close()


def make_search(tmp_path):
    service = object.__new__(SemanticSearchService)
    service._lock = threading.RLock()
    service._dirty = False
    service.metadata_store = MetadataStore(str(tmp_path / 'metadata.json'))
    # The nearest result is another tenant, then another model, then expired,
    # then the compatible low-similarity result we must observe without serving.
    for i, (tenant, model, age) in enumerate([('other', 'm', 0), ('a', 'other-model', 0), ('a', 'm', 100000), ('a', 'm', 0)]):
        service.metadata_store.add(VectorMetadata(vector_id=i, cache_id=f'cache{i}', prompt_id=f'p{i}', prompt_text='question', response_text='answer', tenant_id=tenant, model_name=model, embedding_model='embed', timestamp=datetime.utcnow()-timedelta(seconds=age)))
    def search(query, top_k, threshold):
        results = [SearchResult(vector_id=i, prompt_id=f'p{i}', prompt_text='question', response_text='answer', similarity=score, distance=0) for i,score in enumerate([1., .99, .98, .4]) if threshold is None or score >= threshold]
        return SearchResults(query_vector=[1.], results=results, total_found=len(results), search_time_ms=0)
    service.search = search
    return service


def test_default_model_isolation_and_observation_filters(tmp_path):
    service = make_search(tmp_path)
    assert CacheConfig().require_same_model is True
    assert service.get_cache_entry(object(), model_name='m', tenant_id='a') is None
    candidate = service.get_cache_entry(object(), model_name='m', tenant_id='a', include_below_threshold=True)
    assert candidate.vector_id == 3
    assert candidate.similarity == .4
    assert not candidate.is_cache_hit
    assert service.metadata_store.get(3).cache_hits == 0
    assert service._dirty is False
    # An explicit zero threshold must not be replaced by the default.
    assert service.get_cache_entry(object(), threshold=0, model_name='m', tenant_id='a').is_cache_hit


def test_decision_rejects_other_model_by_default():
    cached = CachedResponse(cache_id='id', prompt_text='q', response_text='a', model_name='other', embedding_vector=[], tenant_id='a')
    result = CacheDecisionEngine().evaluate(cached, .99, 'm', tenant_id='a')
    assert result.decision == CacheDecision.MODEL_MISMATCH
    assert not result.is_hit()


@pytest.mark.asyncio
async def test_low_similarity_survives_cache_decision_and_event_recording(tmp_path, monkeypatch):
    from app.training import deployment
    from app.services import cache_recorder
    monkeypatch.setattr(deployment, 'refresh_deployed_model', lambda: False)
    messages = [SimpleNamespace(role='user', content='q')]
    search = make_search(tmp_path)
    context = object.__new__(CacheService)._extract_cache_key(messages, 'm', 'a').conversation_history
    for metadata in search.metadata_store.get_all():
        metadata.conversation_history = context
    service = CacheService(
        redis_store=AsyncMock(), search_service=search,
        embedding_service=SimpleNamespace(embed_text=lambda *args: object()),
    )
    result = await service.check_cache(messages, 'm', tenant_id='a')
    assert result.decision == CacheDecision.THRESHOLD_NOT_MET
    assert result.similarity == .4
    assert result.cached_response is None
    service.redis_store.increment_cache_miss.assert_awaited_once()
    service.redis_store.increment_cache_hit.assert_not_called()
    service.redis_store.get_cached_response.assert_not_called()

    # Follow the observation into the real event recorder using an isolated DB.
    from app.database.base import Base, import_models
    import_models()
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    from contextlib import contextmanager
    session = sessionmaker(bind=engine)()
    @contextmanager
    def scope():
        yield session
        session.commit()
    monkeypatch.setattr(cache_recorder, 'get_db_manager', lambda: SimpleNamespace(session_scope=scope))
    recorder = CacheRecorder(SimpleNamespace(check_cache=AsyncMock(return_value=result)))
    from app.models.schemas import Message
    await recorder.check_and_record([Message(role='user', content='q')], 'm', tenant_id='a')
    event = session.query(CacheEvent).one()
    assert event.similarity_score == .4
    assert event.cache_status == CacheStatus.THRESHOLD_NOT_MET
    assert event.matched_cache_id is None
    session.close()


def test_container_build_packages_training_fixtures(tmp_path, monkeypatch):
    """Exercise the packaged data layout without requiring a Docker daemon."""
    import json
    import shutil
    from pathlib import Path, PurePosixPath
    from app.training import data_generator
    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / 'backend/Dockerfile').read_text()
    assert 'COPY backend/requirements.txt .' in dockerfile
    assert 'COPY backend/ .' in dockerfile
    assert 'COPY datasets/ /datasets/' in dockerfile
    assert 'context: .' in (root / 'docker-compose.yml').read_text()
    # This is the exact lookup used by a module installed at /app/app/training.
    assert PurePosixPath('/app/app/training/data_generator.py').parents[3] / 'datasets' == PurePosixPath('/datasets')
    destination = tmp_path / 'datasets'
    shutil.copytree(root / 'datasets', destination)
    monkeypatch.setattr(data_generator, 'DATASETS_DIR', destination)
    for name in ['semantic_duplicates.json', 'hard_negatives.json']:
        groups = data_generator.TrainingDataGenerator._load_groups(name)
        assert groups == json.loads((root / 'datasets' / name).read_text())['prompt_groups']
        assert groups


def test_legacy_context_cannot_reach_ambiguous_redis_entries(tmp_path):
    search = make_search(tmp_path)
    context = object.__new__(CacheService)._extract_cache_key(
        [SimpleNamespace(role='user', content='q')], 'm', 'a',
    ).conversation_history
    assert search.get_cache_entry(
        object(), model_name='m', tenant_id='a', conversation_history=context,
        include_below_threshold=True,
    ) is None
