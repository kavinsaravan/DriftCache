"""
Ollama Provider Implementation
Handles requests to local Ollama models (no API costs!)
"""
import time
from typing import AsyncIterator, List, Optional
import httpx

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


class OllamaProvider(BaseProvider):
    """
    Ollama local model provider

    Ollama runs models locally, which is great for:
    - Testing without API costs
    - Privacy-sensitive applications
    - Offline deployments
    """

    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize Ollama provider

        Args:
            base_url: Ollama server URL (defaults to settings)
        """
        self.base_url = base_url or settings.OLLAMA_BASE_URL or "http://localhost:11434"

        # Common Ollama models
        self.supported_models = [
            "llama2",
            "llama2:13b",
            "llama2:70b",
            "mistral",
            "mixtral",
            "codellama",
            "phi",
            "neural-chat",
        ]

    def get_available_models(self) -> List[str]:
        """Get list of Ollama models"""
        return self.supported_models

    def supports_model(self, model: str) -> bool:
        """Check if this provider supports the given model"""
        # Ollama uses model:tag format, so check prefix
        return (
            model in self.supported_models or
            model.startswith("llama") or
            model.startswith("mistral") or
            model.startswith("mixtral") or
            model.startswith("phi")
        )

    def _convert_messages(self, messages: List[Message]) -> List[dict]:
        """Convert to Ollama message format (same as OpenAI)"""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

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
        """Generate a non-streaming chat completion using Ollama"""

        ollama_messages = self._convert_messages(messages)

        # Prepare request
        payload = {
            "model": model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
            }
        }

        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        # Call Ollama API
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload
                )
                response.raise_for_status()
                data = response.json()

            except httpx.ConnectError:
                raise ValueError(
                    f"Cannot connect to Ollama at {self.base_url}. "
                    "Make sure Ollama is running: 'ollama serve'"
                )
            except Exception as e:
                raise ValueError(f"Ollama request failed: {str(e)}")

        # Convert Ollama response to OpenAI format
        completion_id = f"chatcmpl-{int(time.time())}"
        created_time = int(time.time())

        # Extract content
        content = data.get("message", {}).get("content", "")

        # Estimate token usage (Ollama doesn't always provide this)
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)

        return ChatCompletionResponse(
            id=completion_id,
            object="chat.completion",
            created=created_time,
            model=model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=content
                    ),
                    finish_reason="stop"
                )
            ],
            usage=UsageInfo(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens
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
        """Generate a streaming chat completion using Ollama"""

        ollama_messages = self._convert_messages(messages)

        # Prepare request
        payload = {
            "model": model,
            "messages": ollama_messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
            }
        }

        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        completion_id = f"chatcmpl-{int(time.time())}"
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
        yield f"data: {initial_chunk.model_dump_json()}\n\n"

        # Stream from Ollama
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json=payload
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if line.strip():
                            import json
                            data = json.loads(line)

                            # Extract content delta
                            content = data.get("message", {}).get("content", "")
                            done = data.get("done", False)

                            if content:
                                chunk = ChatCompletionStreamResponse(
                                    id=completion_id,
                                    object="chat.completion.chunk",
                                    created=created_time,
                                    model=model,
                                    choices=[
                                        ChatCompletionStreamChoice(
                                            index=0,
                                            delta=DeltaMessage(content=content),
                                            finish_reason=None
                                        )
                                    ]
                                )
                                yield f"data: {chunk.model_dump_json()}\n\n"

                            if done:
                                break

            except httpx.ConnectError:
                raise ValueError(
                    f"Cannot connect to Ollama at {self.base_url}. "
                    "Make sure Ollama is running: 'ollama serve'"
                )

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
        yield f"data: {final_chunk.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"
