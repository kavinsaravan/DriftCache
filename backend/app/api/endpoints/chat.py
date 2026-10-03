"""
OpenAI-compatible chat completion endpoints

Supports both streaming and non-streaming modes with full caching:
- Cache check before streaming/non-streaming responses
- Server-Sent Events (SSE) for streaming with cache hits
- Response collection and caching for streaming misses
- Database recording of all requests
- API key authentication
- Error handling
"""
import time
import logging
from typing import Union
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse

from app.models.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    Message,
    ChatMessage,
    UsageInfo,
    ErrorResponse,
    ErrorDetail,
)
from app.providers.router import provider_router
from app.services.streaming import StreamCollector, create_cached_stream
from app.services.cache_recorder import get_cache_recorder

logger = logging.getLogger(__name__)
router = APIRouter()
cache_recorder = get_cache_recorder()


@router.post("/chat/completions", response_model=None)
async def create_chat_completion(
    request: ChatCompletionRequest
) -> Union[ChatCompletionResponse, StreamingResponse]:
    """
    OpenAI-compatible chat completion endpoint

    Supports:
    - API key authentication via Authorization: Bearer or X-API-Key header
    - Non-streaming responses with cache check/store
    - Streaming responses (SSE) with cache check/store
    - Cache hits return cached content (streamed or non-streamed)
    - Cache misses call provider and store response
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
            # Check cache first (similar to non-streaming)
            request_id, cache_result = await cache_recorder.check_and_record(
                messages=request.messages,
                model_name=request.model,
                stream=True
            )

            if cache_result.is_hit():
                # Cache hit - stream the cached response
                logger.info(f"✓ STREAMING CACHE HIT: similarity={cache_result.similarity:.3f}")
                cached = cache_result.cached_response

                # Create stream from cached content
                cached_stream = create_cached_stream(
                    content=cached.response_text,
                    model=cached.model_name,
                    completion_id=f"cached-{cached.cache_id[:8]}"
                )

                return StreamingResponse(
                    cached_stream,
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "X-Accel-Buffering": "no",
                        "X-Cache-Hit": "true",
                        "X-Similarity-Score": str(cache_result.similarity)
                    }
                )

            # Cache miss - stream from provider and collect for caching
            logger.info(f"✗ STREAMING CACHE MISS: {cache_result.reason}")

            completion_id = f"chatcmpl-{int(time.time())}"
            collector = StreamCollector(
                completion_id=completion_id,
                model=request.model
            )

            # Define callback for when stream completes
            async def on_stream_complete(response):
                """Store the collected response in cache"""
                try:
                    logger.info(
                        f"Stream completed: {response.chunks_received} chunks, "
                        f"{len(response.content)} characters, "
                        f"finish_reason={response.finish_reason}"
                    )

                    # Only cache if response completed successfully
                    if response.finish_reason != "stop":
                        logger.warning(
                            f"Skipping cache storage: finish_reason={response.finish_reason} "
                            f"(truncated or filtered response)"
                        )
                        return

                    # Store in cache + database
                    await cache_recorder.store_and_record(
                        request_id=request_id,
                        messages=request.messages,
                        response_text=response.content,
                        model_name=request.model,
                        provider="openai",
                        input_tokens=None,  # Not available in streaming mode
                        output_tokens=None,
                        estimated_cost=None
                    )
                    logger.info(f"Cached streaming response: {len(response.content)} chars")

                except Exception as e:
                    logger.error(f"Failed to cache streaming response: {e}")

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
                    "X-Accel-Buffering": "no",
                    "X-Cache-Hit": "false"
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
                            message=ChatMessage(
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

            # Only cache if response completed successfully
            finish_reason = response.choices[0].finish_reason if response.choices else None
            if finish_reason != "stop":
                logger.warning(
                    f"Skipping cache storage: finish_reason={finish_reason} "
                    f"(truncated or filtered response)"
                )
            else:
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
                    estimated_cost=None  # Cost calculation based on token usage
                )
                logger.info(f"Stored in cache+DB: {response.usage.total_tokens if response.usage else 0} tokens")

            # Add cache metadata to response
            response_dict = response.model_dump()
            response_dict["cache_hit"] = False

            return response_dict

    except HTTPException:
        raise
    except Exception as e:
        # Handle unexpected errors - don't expose internal details
        logger.error(f"Internal error in chat completion: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(
                    message="An internal error occurred. Please try again later.",
                    type="api_error",
                    code="internal_error"
                )
            ).model_dump()
        )
