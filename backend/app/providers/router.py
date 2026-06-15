"""
Provider Router

Intelligently routes requests to the appropriate LLM provider based on:
- Model name
- Provider availability
- Future: cost, latency, quality preferences

This is the entry point for all LLM requests in DriftCache.
"""
from typing import AsyncIterator, List, Optional
import logging

from app.providers.base import BaseProvider
from app.providers.openai_provider import OpenAIProvider
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.ollama_provider import OllamaProvider
from app.models.schemas import Message, ChatCompletionResponse

logger = logging.getLogger(__name__)


class ProviderRouter:
    """
    Routes requests to the appropriate LLM provider

    This class implements intelligent provider selection and
    can be extended for advanced routing strategies.
    """

    def __init__(self):
        """Initialize all available providers"""
        self.providers: List[BaseProvider] = []

        # Initialize providers
        try:
            self.openai_provider = OpenAIProvider()
            self.providers.append(self.openai_provider)
            logger.info("OpenAI provider initialized")
        except Exception as e:
            logger.warning(f"OpenAI provider not available: {e}")
            self.openai_provider = None

        try:
            self.anthropic_provider = AnthropicProvider()
            self.providers.append(self.anthropic_provider)
            logger.info("Anthropic provider initialized")
        except Exception as e:
            logger.warning(f"Anthropic provider not available: {e}")
            self.anthropic_provider = None

        try:
            self.ollama_provider = OllamaProvider()
            self.providers.append(self.ollama_provider)
            logger.info("Ollama provider initialized")
        except Exception as e:
            logger.warning(f"Ollama provider not available: {e}")
            self.ollama_provider = None

        if not self.providers:
            logger.error("No LLM providers available!")

    def route(self, model: str) -> Optional[BaseProvider]:
        """
        Select the appropriate provider for a given model

        Routing logic:
        1. Check model prefix (gpt- -> OpenAI, claude- -> Anthropic, etc.)
        2. Fall back to checking each provider's supports_model()
        3. Return None if no provider supports the model

        Args:
            model: Model identifier

        Returns:
            Provider instance or None
        """
        # Fast path: route by model prefix
        if model.startswith("gpt-"):
            if self.openai_provider:
                logger.info(f"Routing {model} to OpenAI")
                return self.openai_provider

        elif model.startswith("claude-"):
            if self.anthropic_provider:
                logger.info(f"Routing {model} to Anthropic")
                return self.anthropic_provider

        elif model.startswith(("llama", "mistral", "mixtral", "phi")):
            if self.ollama_provider:
                logger.info(f"Routing {model} to Ollama")
                return self.ollama_provider

        # Slow path: check each provider
        for provider in self.providers:
            if provider.supports_model(model):
                logger.info(f"Routing {model} to {provider.get_provider_name()}")
                return provider

        # No provider found
        logger.error(f"No provider supports model: {model}")
        return None

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
        Route and execute a chat completion request

        Args:
            model: Model identifier
            messages: Conversation messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            stream: Whether to stream (not used in this method)
            **kwargs: Additional provider-specific parameters

        Returns:
            ChatCompletionResponse

        Raises:
            ValueError: If no provider supports the model
        """
        provider = self.route(model)

        if not provider:
            available_models = []
            for p in self.providers:
                available_models.extend(p.get_available_models())

            raise ValueError(
                f"Model '{model}' not supported. "
                f"Available models: {', '.join(set(available_models[:10]))}"
            )

        return await provider.chat_completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            stream=stream,
            **kwargs
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
        """
        Route and execute a streaming chat completion request

        Args:
            model: Model identifier
            messages: Conversation messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            **kwargs: Additional provider-specific parameters

        Yields:
            SSE-formatted response chunks

        Raises:
            ValueError: If no provider supports the model
        """
        provider = self.route(model)

        if not provider:
            available_models = []
            for p in self.providers:
                available_models.extend(p.get_available_models())

            raise ValueError(
                f"Model '{model}' not supported. "
                f"Available models: {', '.join(set(available_models[:10]))}"
            )

        async for chunk in provider.chat_completion_stream(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            **kwargs
        ):
            yield chunk

    def get_available_models(self) -> List[str]:
        """
        Get all available models across all providers

        Returns:
            List of model identifiers
        """
        models = []
        for provider in self.providers:
            models.extend(provider.get_available_models())
        return list(set(models))  # Remove duplicates

    def get_provider_for_model(self, model: str) -> Optional[str]:
        """
        Get the provider name for a given model

        Args:
            model: Model identifier

        Returns:
            Provider name or None
        """
        provider = self.route(model)
        return provider.get_provider_name() if provider else None


# Singleton instance
provider_router = ProviderRouter()
