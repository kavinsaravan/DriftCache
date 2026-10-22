"""Expiration survives all cache layers; Claude receives every instruction."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import threading

import numpy as np
import pytest

from app.cache.service import CacheService
from app.core.config import settings
from app.models.schemas import Message
from app.models.embedding_schemas import Embedding, EmbeddingMetadata
from app.models.search_schemas import VectorMetadata
from app.models.cache_schemas import CachedResponse
from app.providers.anthropic_provider import AnthropicProvider
from app.services.index_maintenance import IndexMaintenanceService
from app.vectorstore.search import SemanticSearchService
from app.vectorstore.storage import MetadataStore
from app.vectorstore.faiss_index import FAISSIndex


@pytest.fixture
def isolated_clock(monkeypatch):
    current = [datetime.utcnow()]
    class Clock(datetime):
        @classmethod
        def utcnow(cls):
            return current[0]
        @classmethod
        def now(cls, tz=None):
            return current[0].replace(tzinfo=timezone.utc).astimezone(tz) if tz else current[0]
    import app.cache.service as cache_module
    import app.models.search_schemas as metadata_module
    import app.models.cache_schemas as response_module
    import app.vectorstore.search as search_module
    import app.vectorstore.storage as storage_module
    import app.services.index_maintenance as maintenance_module
    for module in [cache_module, metadata_module, response_module, search_module, storage_module, maintenance_module]:
        monkeypatch.setattr(module, 'datetime', Clock)
    return current


def services(tmp_path, monkeypatch, clock):
    from app.training import deployment
    monkeypatch.setattr(deployment, 'refresh_deployed_model', lambda: False)
    monkeypatch.setattr(settings, 'CACHE_TTL_SECONDS', 3600)
    monkeypatch.setattr(type(settings), 'get_index_path', lambda self: str(tmp_path / 'faiss.index'))
    monkeypatch.setattr(type(settings), 'get_metadata_path', lambda self: str(tmp_path / 'metadata.json'))
    embeddings = SimpleNamespace(
        model=SimpleNamespace(model_name='embedding'),
        embed_text=lambda text, *args: Embedding(vector=[1., 0.], dimension=2, text=text,
            metadata=EmbeddingMetadata(prompt_hash='p', model_name='m', timestamp=clock[0])),
        embed_batch=lambda texts: SimpleNamespace(embeddings=[SimpleNamespace(vector=[1., 0.]) for _ in texts]),
    )
    search = object.__new__(SemanticSearchService)
    search.faiss_index = FAISSIndex(dimension=2, index_type='Flat')
    search.faiss_index.create_index()
    search.metadata_store = MetadataStore(str(tmp_path / 'metadata.json'))
    search.embedding_service = embeddings
    search._lock = threading.RLock()
    search._dirty = False
    redis = AsyncMock()
    redis.get_cached_response.return_value = None  # Simulate Redis eviction/expiry.
    return CacheService(redis_store=redis, search_service=search, embedding_service=embeddings), search


@pytest.mark.asyncio
@pytest.mark.parametrize('ttl,elapsed', [(60, 120), (7200, 4000)])
@pytest.mark.parametrize('operation', ['cleanup', 'rebuild'])
async def test_per_entry_deadline_survives_reload_and_maintenance(tmp_path, monkeypatch, isolated_clock, ttl, elapsed, operation):
    cache, search = services(tmp_path, monkeypatch, isolated_clock)
    messages = [Message(role='user', content='question')]
    result = await cache.store_response(messages, 'answer', 'm', ttl_seconds=ttl)
    deadline = isolated_clock[0] + timedelta(seconds=ttl)
    assert result.expires_at == deadline
    assert search.metadata_store.get(result.vector_id).expires_at == deadline
    assert cache.redis_store.set_cached_response.call_args.kwargs['response'].expires_at == deadline
    search.save_index()
    search.load_index()
    assert search.metadata_store.get(result.vector_id).expires_at == deadline
    isolated_clock[0] += timedelta(seconds=elapsed)
    should_hit = elapsed < ttl
    decision = await cache.check_cache(messages, 'm')
    assert decision.is_hit() == should_hit
    if should_hit:
        assert decision.cached_response.expires_at == deadline
    maintenance = IndexMaintenanceService(search)
    assert maintenance.get_stats()['stale_vector_count'] == int(not should_hit)
    assert search.metadata_store.get_stale_vector_ratio() == float(not should_hit)
    if operation == 'cleanup':
        assert search.remove_expired_vectors() == int(not should_hit)
    else:
        rebuilt = maintenance.rebuild(dry_run=False)
        assert rebuilt['vectors_removed'] == int(not should_hit)
    assert len(search.faiss_index) == int(should_hit)
    if should_hit:
        assert search.metadata_store.get(result.vector_id).expires_at == deadline


@pytest.mark.asyncio
async def test_nonpositive_ttl_is_rejected_without_writing(tmp_path, monkeypatch, isolated_clock):
    cache, _ = services(tmp_path, monkeypatch, isolated_clock)
    for ttl in [0, -1]:
        with pytest.raises(ValueError, match='positive'):
            await cache.store_response([Message(role='user', content='q')], 'a', 'm', ttl_seconds=ttl)
    cache.redis_store.set_cached_response.assert_not_called()


def test_legacy_unknown_deadline_is_not_extended_and_aware_deadlines_work():
    now = datetime.now(timezone.utc)
    data = dict(vector_id=1, prompt_id='p', prompt_text='q', model_name='m', embedding_model='e', timestamp=(now-timedelta(minutes=2)).isoformat())
    legacy = VectorMetadata.from_dict(data)
    assert legacy.is_expired(now)
    explicit = VectorMetadata(**data, expires_at=now+timedelta(minutes=2))
    assert not explicit.is_expired(now)
    assert VectorMetadata.from_dict(explicit.to_dict()).expires_at == explicit.expires_at
    cached = CachedResponse(cache_id='c', prompt_text='q', response_text='a', model_name='m', embedding_vector=[], expires_at=now-timedelta(seconds=1))
    assert cached.is_expired()


@pytest.mark.asyncio
async def test_model_rebuild_preserves_deadlines(tmp_path, monkeypatch, isolated_clock):
    cache, search = services(tmp_path, monkeypatch, isolated_clock)
    result = await cache.store_response([Message(role='user', content='q')], 'a', 'm', ttl_seconds=7200)
    import app.vectorstore.search as search_module
    monkeypatch.setattr(search_module, 'set_embedding_model', lambda model: None)
    monkeypatch.setattr(settings, 'EMBEDDING_MODEL', settings.EMBEDDING_MODEL)
    monkeypatch.setattr(settings, 'EMBEDDING_DIMENSION', settings.EMBEDDING_DIMENSION)
    candidate = SimpleNamespace(model_name='candidate', dimension=3, encode=lambda texts, **kwargs: np.asarray([[1., 0., 0.] for _ in texts], dtype=np.float32))
    search.rebuild_with_embedding_model(candidate)
    assert search.metadata_store.get(result.vector_id).expires_at == result.expires_at
    persisted = MetadataStore(str(tmp_path / 'metadata.json'))
    persisted.load()
    assert persisted.get(result.vector_id).expires_at == result.expires_at


@pytest.mark.asyncio
async def test_anthropic_preserves_all_system_blocks_in_both_modes():
    provider = object.__new__(AnthropicProvider)
    provider.model_mapping = {}
    response = SimpleNamespace(content=[SimpleNamespace(text='Hello')], stop_reason='end_turn', usage=SimpleNamespace(input_tokens=1, output_tokens=1))
    class Stream:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        def __aiter__(self):
            async def events():
                yield SimpleNamespace(type='message_delta', delta=SimpleNamespace(stop_reason='end_turn'))
                yield SimpleNamespace(type='message_stop')
            return events()
    client = SimpleNamespace(create=AsyncMock(return_value=response), stream=Mock(return_value=Stream()))
    provider.client = SimpleNamespace(messages=client)
    messages = [Message(role='system', content='First instruction'), Message(role='system', content='Second instruction'), Message(role='user', content='Hello')]
    await provider.chat_completion('claude-3-haiku-20240307', messages)
    chunks = [chunk async for chunk in provider.chat_completion_stream('claude-3-haiku-20240307', messages)]
    expected = [{'type': 'text', 'text': 'First instruction'}, {'type': 'text', 'text': 'Second instruction'}]
    assert client.create.call_args.kwargs['system'] == expected
    assert client.stream.call_args.kwargs['system'] == expected
    assert client.create.call_args.kwargs['messages'] == [{'role': 'user', 'content': 'Hello'}]
    assert chunks[-1] == 'data: [DONE]\n\n'
    await provider.chat_completion('claude-3-haiku-20240307', [Message(role='user', content='Hello')])
    assert 'system' not in client.create.call_args.kwargs


@pytest.mark.asyncio
async def test_database_history_uses_original_deadline_not_recording_time(tmp_path, monkeypatch, isolated_clock):
    from contextlib import contextmanager
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database.base import Base, import_models
    from app.models.cache_entry import CacheEntry
    from app.services import cache_recorder
    cache, _ = services(tmp_path, monkeypatch, isolated_clock)
    initial_time = isolated_clock[0]
    async def delayed_store(**kwargs):
        result = await cache.store_response(**kwargs)
        isolated_clock[0] += timedelta(seconds=5)
        return result
    import_models()
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    @contextmanager
    def scope():
        yield db
        db.commit()
    monkeypatch.setattr(cache_recorder, 'get_db_manager', lambda: SimpleNamespace(session_scope=scope))
    recorder = cache_recorder.CacheRecorder(SimpleNamespace(store_response=delayed_store))
    await recorder.store_and_record(request_id='r', messages=[Message(role='user',content='q')], response_text='a', model_name='m', ttl_seconds=60)
    assert db.query(CacheEntry).one().expires_at == initial_time + timedelta(seconds=60)
    db.close()
