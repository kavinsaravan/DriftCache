"""
Base Provider Interface

All LLM providers must implement this interface to ensure consistent behavior
across different backends (OpenAI, Anthropic, Ollama, etc.)
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Optional

from app.models.schemas import (
    Message,
    ChatCompletionResponse,
)


class BaseProvider(ABC):
    """
    Abstract base class for LLM providers

    This interface ensures all providers follow the same contract,
    making it easy to swap providers or add new ones.
    """

    @abstractmethod
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
        """
        Generate a chat completion (non-streaming)

        Args:
            model: Model identifier
            messages: List of chat messages
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            stream: Whether to stream the response
            **kwargs: Additional provider-specific parameters

        Returns:
            ChatCompletionResponse in OpenAI format

        Raises:
            NotImplementedError: If provider doesn't implement this method
        """
        raise NotImplementedError("Provider must implement chat_completion")

    @abstractmethod
    async def chat_completion_stream(
        self,
        model: str,
        messages: List[Message],
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        top_p: float = 1.0,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Generate a streaming chat completion

        Args:
            model: Model identifier
            messages: List of chat messages
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            **kwargs: Additional provider-specific parameters

        Yields:
            SSE-formatted chunks containing ChatCompletionStreamResponse

        Raises:
            NotImplementedError: If provider doesn't implement streaming
        """
        raise NotImplementedError("Provider must implement chat_completion_stream")

    @abstractmethod
    def get_available_models(self) -> List[str]:
        """
        Get list of models supported by this provider

        Returns:
            List of model identifiers
        """
        raise NotImplementedError("Provider must implement get_available_models")

    @abstractmethod
    def supports_model(self, model: str) -> bool:
        """
        Check if this provider supports a given model

        Args:
            model: Model identifier to check

        Returns:
            True if provider supports this model, False otherwise
        """
        raise NotImplementedError("Provider must implement supports_model")

    def get_provider_name(self) -> str:
        """
        Get the name of this provider

        Returns:
            Provider name (e.g., "openai", "anthropic", "ollama")
        """
        return self.__class__.__name__.replace("Provider", "").lower()
