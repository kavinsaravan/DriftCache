"""
OpenAI-compatible chat completion endpoints
"""
import time
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
            # Return streaming response using provider router
            return StreamingResponse(
                provider_router.chat_completion_stream(
                    model=request.model,
                    messages=request.messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens or 1024,
                    top_p=request.top_p,
                ),
                media_type="text/event-stream",
            )
        else:
            # Return non-streaming response using provider router
            response = await provider_router.chat_completion(
                model=request.model,
                messages=request.messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens or 1024,
                top_p=request.top_p,
            )
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
