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
from typing import AsyncIterator, Optional, List, Dict, Any
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

    def add_chunk(self, delta: DeltaMessage):
        """Add a chunk to the collected response"""
        if delta.role:
            self.role = delta.role
        if delta.content:
            self.content += delta.content
            self.chunks_received += 1


class SSEFormatter:
    """
    Server-Sent Events (SSE) formatter

    Converts data into SSE format for streaming responses
    """

    @staticmethod
    def format_event(data: str, event: Optional[str] = None) -> str:
        """
        Format data as an SSE event

        Args:
            data: The data payload
            event: Optional event name

        Returns:
            Formatted SSE string
        """
        lines = []
        if event:
            lines.append(f"event: {event}")
        lines.append(f"data: {data}")
        lines.append("")  # Empty line terminates the event
        return "\n".join(lines) + "\n"

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

    def get_collected_response(self) -> Optional[StreamedResponse]:
        """
        Get the collected response

        Returns:
            StreamedResponse if completed, None otherwise
        """
        if self.completed:
            return self.response
        return None


async def stream_with_heartbeat(
    stream: AsyncIterator[str],
    heartbeat_interval: int = 15
) -> AsyncIterator[str]:
    """
    Add heartbeat comments to keep connection alive

    Some proxies close connections if no data is sent for a while.
    SSE comments (lines starting with :) prevent this.

    Args:
        stream: Original stream
        heartbeat_interval: Seconds between heartbeats

    Yields:
        Stream chunks with periodic heartbeats
    """
    import asyncio

    last_heartbeat = time.time()

    async for chunk in stream:
        yield chunk

        # Send heartbeat if needed
        current_time = time.time()
        if current_time - last_heartbeat > heartbeat_interval:
            yield ": heartbeat\n\n"
            last_heartbeat = current_time


async def create_cached_stream(
    content: str,
    model: str,
    completion_id: Optional[str] = None,
    chunk_size: int = 5
) -> AsyncIterator[str]:
    """
    Create a stream from cached content

    When we have a cache hit, we simulate streaming by breaking
    the cached response into chunks.

    Args:
        content: The cached content to stream
        model: Model name
        completion_id: Optional completion ID
        chunk_size: Words per chunk

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

    # Split content into words
    words = content.split()

    # Stream in chunks
    for i in range(0, len(words), chunk_size):
        chunk_words = words[i:i + chunk_size]
        chunk_content = " ".join(chunk_words)

        # Add space before chunk if not first
        if i > 0:
            chunk_content = " " + chunk_content

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

        # Small delay to simulate streaming
        import asyncio
        await asyncio.sleep(0.05)

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


# Utility functions

def estimate_tokens(text: str) -> int:
    """
    Rough token estimation

    This is approximate. Real tokenization requires the specific model's tokenizer.

    Args:
        text: Text to estimate

    Returns:
        Estimated token count
    """
    # Rough estimate: ~4 characters per token
    return len(text) // 4


def parse_sse_chunk(chunk_str: str) -> Optional[Dict[str, Any]]:
    """
    Parse an SSE chunk into JSON

    Args:
        chunk_str: SSE-formatted chunk

    Returns:
        Parsed JSON dict or None
    """
    try:
        if chunk_str.startswith("data: "):
            json_str = chunk_str[6:].strip()
            if json_str == "[DONE]":
                return {"done": True}
            return json.loads(json_str)
    except Exception as e:
        logger.warning(f"Failed to parse SSE chunk: {e}")
    return None
