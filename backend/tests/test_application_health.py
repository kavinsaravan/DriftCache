"""Tests for health metadata and scheduled vector cleanup helpers."""

import pytest

from app import main


def test_llm_health_requires_default_provider_credentials(monkeypatch):
    monkeypatch.setattr(main.settings, "DEFAULT_MODEL", "claude-3-5-sonnet-20241022")
    monkeypatch.setattr(main.settings, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(main.settings, "OPENAI_API_KEY", "openai-key")

    status = main.get_llm_configuration_status()

    assert status["status"] == "not_configured"
    assert status["default_provider"] == "anthropic"
    assert "openai" in status["configured_providers"]


def test_llm_health_reports_configured_default_provider(monkeypatch):
    monkeypatch.setattr(main.settings, "DEFAULT_MODEL", "gpt-4")
    monkeypatch.setattr(main.settings, "OPENAI_API_KEY", "openai-key")

    status = main.get_llm_configuration_status()

    assert status["status"] == "configured"
    assert status["default_provider"] == "openai"


def test_cleanup_persists_only_when_vectors_are_removed(monkeypatch):
    class SearchService:
        def __init__(self):
            self.save_calls = 0

        def remove_expired_vectors(self):
            return 3

        def save_index(self):
            self.save_calls += 1

    service = SearchService()
    monkeypatch.setattr("app.vectorstore.search.get_search_service", lambda: service)

    assert main.cleanup_expired_vectors() == 3
    assert service.save_calls == 1


@pytest.mark.asyncio
async def test_health_degrades_when_default_provider_is_not_configured(monkeypatch):
    class DatabaseManager:
        def health_check(self):
            return True

    class RedisManager:
        async def health_check(self):
            return True

    async def get_redis_manager():
        return RedisManager()

    monkeypatch.setattr(main, "get_db_manager", lambda: DatabaseManager())
    monkeypatch.setattr(main, "get_redis_manager", get_redis_manager)
    monkeypatch.setattr(main.settings, "DEFAULT_MODEL", "claude-3-5-sonnet-20241022")
    monkeypatch.setattr(main.settings, "ANTHROPIC_API_KEY", "")

    response = await main.health_check()

    assert response["database"] == "connected"
    assert response["redis"] == "connected"
    assert response["llm"]["status"] == "not_configured"
    assert response["status"] == "degraded"
