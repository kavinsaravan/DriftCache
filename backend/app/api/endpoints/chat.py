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
from app.llm.claude_provider import claude_provider

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
            # Return streaming response
            return StreamingResponse(
                claude_provider.create_streaming_completion(
                    model=request.model,
                    messages=request.messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens or 1024,
                    top_p=request.top_p,
                ),
                media_type="text/event-stream",
            )
        else:
            # Return non-streaming response
            response = await claude_provider.create_completion(
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
