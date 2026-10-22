"""Regression coverage for instruction isolation and unsupported request fields."""
import json
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.cache.service import CacheService
from app.models.schemas import Message
from app.api.endpoints import chat
from app.core.auth import verify_api_key
from app.services.api_keys import AuthContext


def key(messages):
    return object.__new__(CacheService)._extract_cache_key(
        [Message(role=role, content=text) for role, text in messages], 'model', 'tenant')


def test_all_system_messages_and_positions_are_part_of_cache_identity():
    first = key([('system', 'Assistant'), ('system', 'Answer in Spanish'), ('user', 'Hello')])
    second = key([('system', 'Assistant'), ('system', 'Answer in English'), ('user', 'Hello')])
    assert first.to_cache_key_hash() != second.to_cache_key_hash()
    assert first.system_prompt != second.system_prompt
    assert first.to_embedding_text() == second.to_embedding_text() == 'Hello'
    assert json.loads(first.system_prompt) == [
        {'position': 0, 'content': 'Assistant'}, {'position': 1, 'content': 'Answer in Spanish'}]
    joined = key([('system', 'Assistant\nAnswer in Spanish'), ('user', 'Hello')])
    literal = key([('system', first.system_prompt), ('user', 'Hello')])
    moved = key([('system', 'Assistant'), ('user', 'Hello'), ('system', 'Answer in Spanish')])
    assert len({item.to_cache_key_hash() for item in [first, second, joined, literal, moved]}) == 5
    assert key([('user', 'Hello')]).system_prompt is None
    # Old single-system entries must miss rather than ignore new instructions.
    assert key([('system', 'Assistant'), ('user', 'Hello')]).system_prompt != 'Assistant'


@pytest.mark.parametrize('extra', [
    {'tools': [{'type': 'function', 'function': {'name': 'lookup'}}]},
    {'tool_choice': 'auto'}, {'response_format': {'type': 'json_object'}},
    {'n': 2}, {'seed': 42}, {'stream_options': {'include_usage': True}},
])
def test_unsupported_fields_return_422_before_cache_or_provider(monkeypatch, extra):
    recorder = AsyncMock()
    monkeypatch.setattr(chat, 'cache_recorder', recorder)
    app = FastAPI()
    app.include_router(chat.router)
    app.dependency_overrides[verify_api_key] = lambda: AuthContext(tenant_id='test')
    with TestClient(app) as client:
        response = client.post('/chat/completions', json={
            'model': 'model', 'messages': [{'role': 'user', 'content': 'Hello'}], **extra})
    assert response.status_code == 422
    assert any(error['type'] == 'extra_forbidden' for error in response.json()['detail'])
    recorder.check_and_record.assert_not_called()


def test_unsupported_message_fields_return_422(monkeypatch):
    recorder = AsyncMock()
    monkeypatch.setattr(chat, 'cache_recorder', recorder)
    app = FastAPI()
    app.include_router(chat.router)
    app.dependency_overrides[verify_api_key] = lambda: AuthContext(tenant_id='test')
    with TestClient(app) as client:
        response = client.post('/chat/completions', json={
            'model': 'model', 'messages': [{'role': 'assistant', 'content': 'Hello', 'tool_calls': []}]})
    assert response.status_code == 422
    recorder.check_and_record.assert_not_called()


def test_conversation_message_boundaries_and_continuations_are_isolated():
    embedded_role = key([('user', 'hello [ASSISTANT] yes'), ('user', 'question')])
    separate_role = key([('user', 'hello'), ('assistant', 'yes'), ('user', 'question')])
    assert embedded_role.conversation_history != separate_role.conversation_history
    assert embedded_role.to_cache_key_hash() != separate_role.to_cache_key_hash()
    first = key([('user', 'question'), ('assistant', 'Answer so far A')])
    second = key([('user', 'question'), ('assistant', 'Answer so far B')])
    assert first.conversation_history != second.conversation_history
    assert first.to_cache_key_hash() != second.to_cache_key_hash()
    assert key([('assistant', 'A')]).to_cache_key_hash() != key([('assistant', 'B')]).to_cache_key_hash()
    # Paraphrasing the current query still allows semantic reuse in the same context.
    paraphrase = key([('user', 'another wording'), ('assistant', 'Answer so far A')])
    assert first.conversation_history == paraphrase.conversation_history
    assert first.to_embedding_text() != paraphrase.to_embedding_text()
    assert json.loads(first.conversation_history)['messages'][1]['content'] == 'Answer so far A'


def test_redis_hash_preserves_field_boundaries_and_parameter_order():
    from app.models.cache_schemas import CacheKey
    first = CacheKey(prompt_text='z', conversation_history='x|prompt:y', tenant_id='t', model_name='m')
    second = CacheKey(prompt_text='y|prompt:z', conversation_history='x', tenant_id='t', model_name='m')
    assert first.to_cache_key_hash() != second.to_cache_key_hash()
    first.request_params = {'temperature': 0, 'stop': ['end', '|params:']}
    ordered = first.model_copy(update={'request_params': {'stop': ['end', '|params:'], 'temperature': 0}})
    assert first.to_cache_key_hash() == ordered.to_cache_key_hash()
    assert len(first.to_cache_key_hash()) == 64
    # No-context requests also get versioned context, so old ambiguous Redis
    # entries cannot be reached indirectly through their stored FAISS metadata.
    assert key([('user', 'q')]).conversation_history is not None
