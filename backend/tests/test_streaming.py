"""
Test Streaming Response System

Tests for:
- SSE formatting
- Stream collection
- Cached stream generation
- Error handling
"""
import asyncio
import pytest
from app.services.streaming import (
    SSEFormatter,
    StreamCollector,
    StreamedResponse,
    create_cached_stream,
    parse_sse_chunk,
    estimate_tokens,
)
from app.models.schemas import (
    ChatCompletionStreamResponse,
    ChatCompletionStreamChoice,
    DeltaMessage,
)


def test_sse_formatter_chunk():
    """Test SSE chunk formatting"""
    chunk = ChatCompletionStreamResponse(
        id="test-123",
        object="chat.completion.chunk",
        created=1234567890,
        model="gpt-4",
        choices=[
            ChatCompletionStreamChoice(
                index=0,
                delta=DeltaMessage(content="Hello"),
                finish_reason=None
            )
        ]
    )

    formatted = SSEFormatter.format_chunk(chunk)

    assert formatted.startswith("data: ")
    assert "Hello" in formatted
    assert formatted.endswith("\n\n")


def test_sse_formatter_done():
    """Test [DONE] message formatting"""
    done = SSEFormatter.format_done()

    assert done == "data: [DONE]\n\n"


def test_sse_formatter_error():
    """Test error message formatting"""
    error = SSEFormatter.format_error("Something went wrong")

    assert "error" in error
    assert "Something went wrong" in error
    assert error.startswith("data: ")


def test_streamed_response_collection():
    """Test collecting chunks into a response"""
    response = StreamedResponse(
        id="test-123",
        model="gpt-4"
    )

    # Add chunks
    response.add_chunk(DeltaMessage(role="assistant"))
    response.add_chunk(DeltaMessage(content="Hello"))
    response.add_chunk(DeltaMessage(content=" world"))

    assert response.role == "assistant"
    assert response.content == "Hello world"
    assert response.chunks_received == 2  # Role doesn't count


@pytest.mark.asyncio
async def test_stream_collector():
    """Test stream collection"""
    # Create a fake stream
    async def fake_stream():
        chunks = [
            ChatCompletionStreamResponse(
                id="test-123",
                object="chat.completion.chunk",
                created=1234567890,
                model="gpt-4",
                choices=[
                    ChatCompletionStreamChoice(
                        index=0,
                        delta=DeltaMessage(role="assistant"),
                        finish_reason=None
                    )
                ]
            ),
            ChatCompletionStreamResponse(
                id="test-123",
                object="chat.completion.chunk",
                created=1234567890,
                model="gpt-4",
                choices=[
                    ChatCompletionStreamChoice(
                        index=0,
                        delta=DeltaMessage(content="Hello"),
                        finish_reason=None
                    )
                ]
            ),
            ChatCompletionStreamResponse(
                id="test-123",
                object="chat.completion.chunk",
                created=1234567890,
                model="gpt-4",
                choices=[
                    ChatCompletionStreamChoice(
                        index=0,
                        delta=DeltaMessage(content=" world"),
                        finish_reason="stop"
                    )
                ]
            ),
        ]

        for chunk in chunks:
            yield SSEFormatter.format_chunk(chunk)
        yield SSEFormatter.format_done()

    # Collect the stream
    collector = StreamCollector(completion_id="test-123", model="gpt-4")

    completion_called = False

    async def on_complete(response):
        nonlocal completion_called
        completion_called = True
        assert response.content == "Hello world"
        assert response.finish_reason == "stop"

    # Process stream
    chunks_received = 0
    async for chunk in collector.collect_and_forward(
        stream=fake_stream(),
        on_complete=on_complete
    ):
        chunks_received += 1

    assert chunks_received > 0
    assert completion_called
    assert collector.completed


@pytest.mark.asyncio
async def test_cached_stream_generation():
    """Test generating a stream from cached content"""
    cached_content = "This is a cached response from DriftCache"

    chunks = []
    async for chunk in create_cached_stream(
        content=cached_content,
        model="gpt-4",
        chunk_size=3
    ):
        chunks.append(chunk)

    # Should have multiple chunks
    assert len(chunks) > 3

    # First chunk should have role
    assert "assistant" in chunks[0]

    # Last chunk should be [DONE]
    assert chunks[-1] == "data: [DONE]\n\n"

    # Middle chunks should have content
    content_chunks = [c for c in chunks if "This" in c or "cached" in c or "response" in c]
    assert len(content_chunks) > 0


def test_parse_sse_chunk():
    """Test parsing SSE chunks"""
    # Valid chunk
    chunk1 = 'data: {"id": "test", "content": "hello"}\n\n'
    parsed1 = parse_sse_chunk(chunk1)
    assert parsed1 is not None
    assert parsed1["id"] == "test"
    assert parsed1["content"] == "hello"

    # [DONE] chunk
    chunk2 = "data: [DONE]\n\n"
    parsed2 = parse_sse_chunk(chunk2)
    assert parsed2 is not None
    assert parsed2.get("done") is True

    # Invalid chunk
    chunk3 = "invalid data"
    parsed3 = parse_sse_chunk(chunk3)
    assert parsed3 is None


def test_token_estimation():
    """Test token estimation"""
    text1 = "Hello world"
    tokens1 = estimate_tokens(text1)
    assert tokens1 > 0
    assert tokens1 < len(text1)  # Tokens should be less than characters

    text2 = "A" * 100
    tokens2 = estimate_tokens(text2)
    assert tokens2 == 25  # 100 chars / 4 = 25 tokens


if __name__ == "__main__":
    print("Running streaming tests...")
    pytest.main([__file__, "-v"])
