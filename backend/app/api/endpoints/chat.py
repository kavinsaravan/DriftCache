"""
OpenAI-compatible chat completion endpoints

Supports both streaming and non-streaming modes with:
- Server-Sent Events (SSE) for streaming
- Response collection for caching
- Error handling
"""
import time
import logging
from typing import Union
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ErrorResponse,
    ErrorDetail,
)
from app.providers.router import provider_router
from app.services.streaming import StreamCollector

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat/completions", response_model=Union[ChatCompletionResponse, StreamingResponse])
async def create_chat_completion(request: ChatCompletionRequest):
    """
    OpenAI-compatible chat completion endpoint

    Supports:
    - Non-streaming responses
    - Streaming responses (SSE)
    - Request validation
    - Error handling
    """
    try:
        # Validate that we have messages
        if not request.messages:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error=ErrorDetail(
                        message="messages cannot be empty",
                        type="invalid_request_error",
                        code="invalid_messages"
                    )
                ).model_dump()
            )

        # Handle streaming vs non-streaming
        if request.stream:
            # STREAMING MODE
            # We need to:
            # 1. Stream tokens to client immediately (good UX)
            # 2. Collect full response for caching (important for cache layer)

            # Create stream collector
            completion_id = f"chatcmpl-{int(time.time())}"
            collector = StreamCollector(
                completion_id=completion_id,
                model=request.model
            )

            # Define callback for when stream completes
            async def on_stream_complete(response):
                """
                Called when streaming finishes

                This is where we'll cache the response in future iterations
                """
                logger.info(
                    f"Stream completed: {response.chunks_received} chunks, "
                    f"{len(response.content)} characters"
                )
                # TODO: Cache the response here (Week 2)

            # Get provider stream
            provider_stream = provider_router.chat_completion_stream(
                model=request.model,
                messages=request.messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens or 1024,
                top_p=request.top_p,
            )

            # Wrap with collector
            collected_stream = collector.collect_and_forward(
                stream=provider_stream,
                on_complete=on_stream_complete
            )

            # Return streaming response
            return StreamingResponse(
                collected_stream,
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",  # Disable nginx buffering
                }
            )

        else:
            # NON-STREAMING MODE
            # Simple case: just return the full response
            response = await provider_router.chat_completion(
                model=request.model,
                messages=request.messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens or 1024,
                top_p=request.top_p,
            )

            # TODO: Cache the response here (Week 2)
            logger.info(f"Completion: {response.usage.total_tokens} tokens")

            return response

    except HTTPException:
        raise
    except Exception as e:
        # Handle unexpected errors
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(
                    message=str(e),
                    type="api_error",
                    code="internal_error"
                )
            ).model_dump()
        )
