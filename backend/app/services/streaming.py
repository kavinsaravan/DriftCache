"""
Streaming Response System

Handles Server-Sent Events (SSE) streaming for LLM responses with:
- SSE formatting
- Response collection for caching
- Error handling
- Stream interception
"""
import json
import time
import logging
from typing import AsyncIterator, Optional
from dataclasses import dataclass, field

from app.models.schemas import (
    ChatCompletionStreamResponse,
    ChatCompletionStreamChoice,
    DeltaMessage,
)

logger = logging.getLogger(__name__)


@dataclass
class StreamedResponse:
    """
    Collected response from a stream

    This is used to cache the full response after streaming completes
    """
    id: str
    model: str
    content: str = ""
    role: str = "assistant"
    finish_reason: Optional[str] = None
    created: int = field(default_factory=lambda: int(time.time()))
    chunks_received: int = 0
    output_tokens: int = 0  # Estimated token count

    def add_chunk(self, delta: DeltaMessage):
        """Add a chunk to the collected response"""
        if delta.role:
            self.role = delta.role
        if delta.content:
            self.content += delta.content
            self.chunks_received += 1

    def estimate_tokens(self) -> int:
        """Estimate total tokens in the response (rough approximation)"""
        # Rough estimate: ~4 characters per token
        self.output_tokens = len(self.content) // 4
        return self.output_tokens


class SSEFormatter:
    """
    Server-Sent Events (SSE) formatter

    Converts data into SSE format for streaming responses
    """

    @staticmethod
    def format_chunk(chunk: ChatCompletionStreamResponse) -> str:
        """
        Format a completion chunk as SSE

        Args:
            chunk: The chunk to format

        Returns:
            SSE-formatted string
        """
        return f"data: {chunk.model_dump_json()}\n\n"

    @staticmethod
    def format_done() -> str:
        """Format the [DONE] message"""
        return "data: [DONE]\n\n"

    @staticmethod
    def format_error(error_message: str) -> str:
        """
        Format an error message as SSE

        Args:
            error_message: Error message to send

        Returns:
            SSE-formatted error
        """
        error_data = {
            "error": {
                "message": error_message,
                "type": "stream_error",
            }
        }
        return f"data: {json.dumps(error_data)}\n\n"


class StreamCollector:
    """
    Collects streaming chunks for later caching

    This allows us to:
    1. Stream responses to the client immediately
    2. Collect the full response in the background
    3. Cache the complete response after streaming finishes
    """

    def __init__(self, completion_id: str, model: str):
        """
        Initialize stream collector

        Args:
            completion_id: Unique ID for this completion
            model: Model being used
        """
        self.response = StreamedResponse(
            id=completion_id,
            model=model
        )
        self.started = False
        self.completed = False

    async def collect_and_forward(
        self,
        stream: AsyncIterator[str],
        on_complete: Optional[callable] = None
    ) -> AsyncIterator[str]:
        """
        Intercept stream, collect chunks, and forward to client

        This is the key method that enables simultaneous streaming
        and caching.

        Args:
            stream: The original stream from the provider
            on_complete: Optional callback when stream completes

        Yields:
            SSE-formatted chunks
        """
        try:
            self.started = True

            async for chunk_str in stream:
                # Forward to client immediately
                yield chunk_str

                # Parse and collect for caching
                if chunk_str.startswith("data: ") and chunk_str != "data: [DONE]\n\n":
                    try:
                        # Extract JSON from SSE format
                        json_str = chunk_str[6:].strip()  # Remove "data: " prefix
                        chunk_data = json.loads(json_str)

                        # Parse as ChatCompletionStreamResponse
                        chunk = ChatCompletionStreamResponse(**chunk_data)

                        # Collect the chunk
                        if chunk.choices and len(chunk.choices) > 0:
                            choice = chunk.choices[0]
                            self.response.add_chunk(choice.delta)

                            if choice.finish_reason:
                                self.response.finish_reason = choice.finish_reason

                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse chunk: {chunk_str}")
                    except Exception as e:
                        logger.warning(f"Error collecting chunk: {e}")

            # Mark as completed
            self.completed = True

            # Call completion callback
            if on_complete:
                try:
                    await on_complete(self.response)
                except Exception as e:
                    logger.error(f"Error in stream completion callback: {e}")

        except Exception as e:
            logger.error(f"Error in stream collection: {e}")
            # Send error to client
            yield SSEFormatter.format_error(str(e))
            raise

async def create_cached_stream(
    content: str,
    model: str,
    completion_id: Optional[str] = None,
    chunk_size: int = 20
) -> AsyncIterator[str]:
    """
    Create a stream from cached content

    When we have a cache hit, we simulate streaming by breaking
    the cached response into chunks.

    Args:
        content: The cached content to stream
        model: Model name
        completion_id: Optional completion ID
        chunk_size: Characters per chunk (preserves whitespace)

    Yields:
        SSE-formatted chunks simulating a real stream
    """
    completion_id = completion_id or f"chatcmpl-{int(time.time())}"
    created_time = int(time.time())

    # Send initial chunk with role
    initial_chunk = ChatCompletionStreamResponse(
        id=completion_id,
        object="chat.completion.chunk",
        created=created_time,
        model=model,
        choices=[
            ChatCompletionStreamChoice(
                index=0,
                delta=DeltaMessage(role="assistant"),
                finish_reason=None
            )
        ]
    )
    yield SSEFormatter.format_chunk(initial_chunk)

    # Stream in character chunks to preserve whitespace (newlines, tabs, etc.)
    for i in range(0, len(content), chunk_size):
        chunk_content = content[i:i + chunk_size]

        content_chunk = ChatCompletionStreamResponse(
            id=completion_id,
            object="chat.completion.chunk",
            created=created_time,
            model=model,
            choices=[
                ChatCompletionStreamChoice(
                    index=0,
                    delta=DeltaMessage(content=chunk_content),
                    finish_reason=None
                )
            ]
        )
        yield SSEFormatter.format_chunk(content_chunk)

        # Yield control without adding artificial latency to an already cached
        # response.
        import asyncio
        await asyncio.sleep(0)

    # Send final chunk
    final_chunk = ChatCompletionStreamResponse(
        id=completion_id,
        object="chat.completion.chunk",
        created=created_time,
        model=model,
        choices=[
            ChatCompletionStreamChoice(
                index=0,
                delta=DeltaMessage(),
                finish_reason="stop"
            )
        ]
    )
    yield SSEFormatter.format_chunk(final_chunk)
    yield SSEFormatter.format_done()
