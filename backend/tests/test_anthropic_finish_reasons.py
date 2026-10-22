"""Exercise Claude stop reasons through the actual chat cache-store decision."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.api.endpoints import chat
from app.models.cache_schemas import CacheDecision, CacheDecisionResult
from app.models.schemas import ChatCompletionRequest
from app.providers.anthropic_provider import AnthropicProvider
from app.services.api_keys import AuthContext


class FakeStream:
    def __init__(self, reason, interrupted=None):
        self.reason = reason
        self.interrupted = interrupted

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def __aiter__(self):
        async def events():
            yield SimpleNamespace(type='content_block_delta', delta=SimpleNamespace(text='Answer content'))
            if self.interrupted == 'exception':
                raise RuntimeError('Connection interrupted')
            yield SimpleNamespace(type='message_delta', delta=SimpleNamespace(stop_reason=self.reason))
            if self.interrupted != 'eof':
                yield SimpleNamespace(type='message_stop')
        return events()


def configure(monkeypatch, reason, interrupted=None):
    provider = object.__new__(AnthropicProvider)
    provider.model_mapping = {}
    provider.client = SimpleNamespace(messages=SimpleNamespace(
        create=AsyncMock(return_value=SimpleNamespace(
            content=[SimpleNamespace(text='Answer content')], stop_reason=reason,
            usage=SimpleNamespace(input_tokens=2, output_tokens=3))),
        stream=Mock(return_value=FakeStream(reason, interrupted)),
    ))
    recorder = SimpleNamespace(
        check_and_record=AsyncMock(return_value=('request-id', CacheDecisionResult(decision=CacheDecision.MISS, reason='No match'))),
        store_and_record=AsyncMock(), record_provider_call=AsyncMock(),
    )
    monkeypatch.setattr(chat, 'cache_recorder', recorder)
    monkeypatch.setattr(chat, 'provider_router', SimpleNamespace(
        chat_completion=provider.chat_completion,
        chat_completion_stream=provider.chat_completion_stream,
        get_provider_for_model=lambda model: 'anthropic',
    ))
    return recorder


@pytest.mark.asyncio
@pytest.mark.parametrize('stream', [False, True])
@pytest.mark.parametrize('native,expected', [
    ('end_turn', 'stop'), ('stop_sequence', 'stop'),
    ('max_tokens', 'length'), ('model_context_window_exceeded', 'length'),
    ('tool_use', 'tool_calls'), ('refusal', 'content_filter'),
    ('pause_turn', None), ('unexpected_reason', None), (None, None),
])
async def test_normalization_and_cache_eligibility_in_both_modes(monkeypatch, stream, native, expected):
    recorder = configure(monkeypatch, native)
    request = ChatCompletionRequest(model='claude-test', messages=[{'role': 'user', 'content': 'question'}], stream=stream)
    response = await chat.create_chat_completion(request, auth=AuthContext(tenant_id='test'))
    if stream:
        chunks = [chunk async for chunk in response.body_iterator]
        assert chunks[-1] == 'data: [DONE]\n\n'
        final = json.loads(chunks[-2].removeprefix('data: ').strip())
        reason = final['choices'][0]['finish_reason']
    else:
        reason = response['choices'][0]['finish_reason']
    assert reason == expected
    if expected == 'stop':
        recorder.store_and_record.assert_awaited_once()
        recorder.record_provider_call.assert_not_awaited()
    else:
        recorder.store_and_record.assert_not_awaited()
        recorder.record_provider_call.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('interrupted', ['exception', 'eof'])
async def test_interrupted_stream_never_stores_partial_response(monkeypatch, interrupted):
    # Even an end_turn delta must not make an incomplete transport cacheable.
    recorder = configure(monkeypatch, 'end_turn', interrupted)
    response = await chat.create_chat_completion(
        ChatCompletionRequest(model='claude-test', messages=[{'role':'user','content':'q'}], stream=True),
        auth=AuthContext(tenant_id='test'),
    )
    chunks = []
    with pytest.raises(RuntimeError):
        async for chunk in response.body_iterator:
            chunks.append(chunk)
    recorder.store_and_record.assert_not_awaited()
    assert any('stream_error' in chunk for chunk in chunks)
    assert 'data: [DONE]\n\n' not in chunks
