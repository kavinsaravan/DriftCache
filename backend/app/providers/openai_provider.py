"""
OpenAI Provider Implementation
Handles requests to OpenAI's API (GPT models)
"""
import time
from typing import AsyncIterator, List, Optional
from openai import AsyncOpenAI

from app.core.config import settings
from app.providers.base import BaseProvider
from app.models.schemas import (
    Message,
    ChatCompletionResponse,
    ChatCompletionStreamResponse,
    ChatCompletionChoice,
    ChatCompletionStreamChoice,
    ChatMessage,
    DeltaMessage,
    UsageInfo,
)


class OpenAIProvider(BaseProvider):
    """OpenAI API provider implementation"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenAI provider

        Args:
            api_key: OpenAI API key (defaults to settings)
        """
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None

        # Models this provider supports
        self.supported_models = [
            "gpt-4",
            "gpt-4-turbo",
            "gpt-4-turbo-preview",
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k",
            "gpt-4-0125-preview",
            "gpt-4-1106-preview",
        ]

    def get_available_models(self) -> List[str]:
        """Get list of OpenAI models supported"""
        return self.supported_models

    def supports_model(self, model: str) -> bool:
        """Check if this provider supports the given model"""
        # Check exact match or prefix match (e.g., "gpt-4-custom")
        return model in self.supported_models or model.startswith("gpt-")

    async def chat_completion(
        self,
        model: str,
        messages: List[Message],
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        top_p: float = 1.0,
        stream: bool = False,
        **kwargs
    ) -> ChatCompletionResponse:
        """Generate a non-streaming chat completion using OpenAI"""

        if not self.client:
            raise ValueError("OpenAI API key not configured")

        # Convert messages to OpenAI format
        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        # Call OpenAI API
        response = await self.client.chat.completions.create(
            model=model,
            messages=openai_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            **kwargs
        )

        # OpenAI response is already in the correct format
        # Just need to convert to our Pydantic models
        return ChatCompletionResponse(
            id=response.id,
            object=response.object,
            created=response.created,
            model=response.model,
            choices=[
                ChatCompletionChoice(
                    index=choice.index,
                    message=ChatMessage(
                        role=choice.message.role,
                        content=choice.message.content or ""
                    ),
                    finish_reason=choice.finish_reason
                )
                for choice in response.choices
            ],
            usage=UsageInfo(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens
            )
        )

    async def chat_completion_stream(
        self,
        model: str,
        messages: List[Message],
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        top_p: float = 1.0,
        **kwargs
    ) -> AsyncIterator[str]:
        """Generate a streaming chat completion using OpenAI"""

        if not self.client:
            raise ValueError("OpenAI API key not configured")

        # Convert messages to OpenAI format
        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        # Stream from OpenAI API
        stream = await self.client.chat.completions.create(
            model=model,
            messages=openai_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            stream=True,
            **kwargs
        )

        # Convert OpenAI stream to our SSE format
        async for chunk in stream:
            if chunk.choices:
                choice = chunk.choices[0]

                # Build delta message
                delta = DeltaMessage()
                if choice.delta.role:
                    delta.role = choice.delta.role
                if choice.delta.content:
                    delta.content = choice.delta.content

                # Build response chunk
                response_chunk = ChatCompletionStreamResponse(
                    id=chunk.id,
                    object=chunk.object,
                    created=chunk.created,
                    model=chunk.model,
                    choices=[
                        ChatCompletionStreamChoice(
                            index=choice.index,
                            delta=delta,
                            finish_reason=choice.finish_reason
                        )
                    ]
                )

                yield f"data: {response_chunk.model_dump_json()}\n\n"

        # Send final [DONE] message
        yield "data: [DONE]\n\n"
