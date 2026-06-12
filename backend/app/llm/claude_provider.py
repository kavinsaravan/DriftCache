"""
Claude LLM Provider
Handles communication with Anthropic's Claude API
"""
import time
from typing import AsyncIterator, List, Dict, Any
from anthropic import AsyncAnthropic
from anthropic.types import Message as ClaudeMessage, MessageStreamEvent

from app.core.config import settings
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


class ClaudeProvider:
    """Claude API provider with OpenAI-compatible interface"""

    def __init__(self):
        self.client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model_mapping = {
            "gpt-4": "claude-3-5-sonnet-20241022",
            "gpt-4-turbo": "claude-3-5-sonnet-20241022",
            "gpt-3.5-turbo": "claude-3-haiku-20240307",
            "claude-3-5-sonnet": "claude-3-5-sonnet-20241022",
            "claude-3-opus": "claude-3-opus-20240229",
            "claude-3-sonnet": "claude-3-sonnet-20240229",
            "claude-3-haiku": "claude-3-haiku-20240307",
        }

    def _map_model(self, model: str) -> str:
        """Map OpenAI model names to Claude model names"""
        return self.model_mapping.get(model, settings.DEFAULT_MODEL)

    def _convert_messages(self, messages: List[Message]) -> tuple[str, List[Dict[str, str]]]:
        """
        Convert OpenAI-style messages to Claude format
        Returns: (system_prompt, messages_list)
        """
        system_prompt = ""
        claude_messages = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
            else:
                claude_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

        return system_prompt, claude_messages

    async def create_completion(
        self,
        model: str,
        messages: List[Message],
        temperature: float = 1.0,
        max_tokens: int = 1024,
        top_p: float = 1.0,
        **kwargs
    ) -> ChatCompletionResponse:
        """Create a non-streaming chat completion"""

        claude_model = self._map_model(model)
        system_prompt, claude_messages = self._convert_messages(messages)

        # Call Claude API
        response: ClaudeMessage = await self.client.messages.create(
            model=claude_model,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            system=system_prompt if system_prompt else None,
            messages=claude_messages,
        )

        # Convert to OpenAI format
        completion_id = f"chatcmpl-{int(time.time())}"
        created_time = int(time.time())

        # Extract text content from Claude response
        content = ""
        if response.content:
            for block in response.content:
                if hasattr(block, 'text'):
                    content += block.text

        return ChatCompletionResponse(
            id=completion_id,
            object="chat.completion",
            created=created_time,
            model=claude_model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=content
                    ),
                    finish_reason=response.stop_reason or "stop"
                )
            ],
            usage=UsageInfo(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens
            )
        )

    async def create_streaming_completion(
        self,
        model: str,
        messages: List[Message],
        temperature: float = 1.0,
        max_tokens: int = 1024,
        top_p: float = 1.0,
        **kwargs
    ) -> AsyncIterator[str]:
        """Create a streaming chat completion"""

        claude_model = self._map_model(model)
        system_prompt, claude_messages = self._convert_messages(messages)

        completion_id = f"chatcmpl-{int(time.time())}"
        created_time = int(time.time())

        # Stream from Claude API
        async with self.client.messages.stream(
            model=claude_model,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            system=system_prompt if system_prompt else None,
            messages=claude_messages,
        ) as stream:

            # Send initial chunk with role
            initial_chunk = ChatCompletionStreamResponse(
                id=completion_id,
                object="chat.completion.chunk",
                created=created_time,
                model=claude_model,
                choices=[
                    ChatCompletionStreamChoice(
                        index=0,
                        delta=DeltaMessage(role="assistant"),
                        finish_reason=None
                    )
                ]
            )
            yield f"data: {initial_chunk.model_dump_json()}\n\n"

            # Stream content chunks
            async for event in stream:
                if event.type == "content_block_delta":
                    if hasattr(event.delta, 'text'):
                        chunk = ChatCompletionStreamResponse(
                            id=completion_id,
                            object="chat.completion.chunk",
                            created=created_time,
                            model=claude_model,
                            choices=[
                                ChatCompletionStreamChoice(
                                    index=0,
                                    delta=DeltaMessage(content=event.delta.text),
                                    finish_reason=None
                                )
                            ]
                        )
                        yield f"data: {chunk.model_dump_json()}\n\n"

            # Send final chunk
            final_chunk = ChatCompletionStreamResponse(
                id=completion_id,
                object="chat.completion.chunk",
                created=created_time,
                model=claude_model,
                choices=[
                    ChatCompletionStreamChoice(
                        index=0,
                        delta=DeltaMessage(),
                        finish_reason="stop"
                    )
                ]
            )
            yield f"data: {final_chunk.model_dump_json()}\n\n"
            yield "data: [DONE]\n\n"


# Singleton instance
claude_provider = ClaudeProvider()
