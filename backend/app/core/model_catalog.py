"""Deployment-selected models shared by discovery and application onboarding.

This describes configuration, not a live check of provider credentials or access.
"""
from app.core.config import settings


def provider_for_model(model: str) -> str | None:
    if model.startswith("claude-"):
        return "anthropic"
    if model.startswith("gpt-"):
        return "openai"
    if model.startswith(("llama", "mistral", "mixtral", "phi", "codellama", "neural-chat")):
        return "ollama"
    return None


def configured_providers() -> set[str]:
    return {name for name, value in (
        ("anthropic", settings.ANTHROPIC_API_KEY),
        ("openai", settings.OPENAI_API_KEY),
        ("ollama", settings.OLLAMA_BASE_URL),
    ) if value}


def available_models() -> list[str]:
    providers = configured_providers()
    return sorted({model for model in [settings.DEFAULT_MODEL, *settings.ADDITIONAL_MODELS]
                   if provider_for_model(model) in providers})


def integration_configuration() -> dict:
    provider = provider_for_model(settings.DEFAULT_MODEL)
    return {
        "default_model": settings.DEFAULT_MODEL,
        "default_provider": provider,
        "configured": provider is not None and provider in configured_providers(),
        "available_models": available_models(),
    }
