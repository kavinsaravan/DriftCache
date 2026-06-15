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
    ChatCompletionChoice,
    Message,
    UsageInfo,
    ErrorResponse,
    ErrorDetail,
)
from app.providers.router import provider_router
from app.services.streaming import StreamCollector
from app.services.cache_recorder import get_cache_recorder

logger = logging.getLogger(__name__)
router = APIRouter()
cache_recorder = get_cache_recorder()


@router.post("/chat/completions", response_model=None)
async def create_chat_completion(request: ChatCompletionRequest) -> Union[ChatCompletionResponse, StreamingResponse]:
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
            # Check cache first (with database recording)
            request_id, cache_result = await cache_recorder.check_and_record(
                messages=request.messages,
                model_name=request.model,
                stream=False
            )

            if cache_result.is_hit():
                # Cache hit - build response from cached data
                logger.info(f"✓ CACHE HIT: similarity={cache_result.similarity:.3f}")
                cached = cache_result.cached_response

                # Build OpenAI-compatible response from cached data
                response = ChatCompletionResponse(
                    id=f"cached-{cached.cache_id[:8]}",
                    object="chat.completion",
                    created=int(cached.created_at.timestamp()),
                    model=cached.model_name,
                    choices=[
                        ChatCompletionChoice(
                            index=0,
                            message=Message(
                                role="assistant",
                                content=cached.response_text
                            ),
                            finish_reason="stop"
                        )
                    ],
                    usage=UsageInfo(
                        prompt_tokens=0,
                        completion_tokens=0,
                        total_tokens=0
                    )
                )

                # Add cache metadata
                response_dict = response.model_dump()
                response_dict["cache_hit"] = True
                response_dict["similarity_score"] = cache_result.similarity

                return response_dict

            # Cache miss - call provider
            logger.info(f"✗ CACHE MISS: {cache_result.reason}")
            response = await provider_router.chat_completion(
                model=request.model,
                messages=request.messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens or 1024,
                top_p=request.top_p,
            )

            # Store response in cache + database for future requests
            response_text = response.choices[0].message.content
            await cache_recorder.store_and_record(
                request_id=request_id,
                messages=request.messages,
                response_text=response_text,
                model_name=request.model,
                provider="openai",
                input_tokens=response.usage.prompt_tokens if response.usage else None,
                output_tokens=response.usage.completion_tokens if response.usage else None,
                estimated_cost=None  # TODO: Calculate cost based on model pricing
            )
            logger.info(f"Stored in cache+DB: {response.usage.total_tokens if response.usage else 0} tokens")

            # Add cache metadata to response
            response_dict = response.model_dump()
            response_dict["cache_hit"] = False

            return response_dict

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
