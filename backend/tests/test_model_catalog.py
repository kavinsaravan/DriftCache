"""Discovery and onboarding use the same deployment-selected model IDs."""
import asyncio
import pytest
from app.core.config import settings
from app.core.model_catalog import available_models, integration_configuration
from app.api.endpoints.models import list_models


@pytest.fixture(autouse=True)
def configuration(monkeypatch):
    monkeypatch.setattr(settings, 'DEFAULT_MODEL', 'claude-sonnet-5-5')
    monkeypatch.setattr(settings, 'ADDITIONAL_MODELS', [])
    monkeypatch.setattr(settings, 'ANTHROPIC_API_KEY', 'private-anthropic-key')
    monkeypatch.setattr(settings, 'OPENAI_API_KEY', '')
    monkeypatch.setattr(settings, 'OLLAMA_BASE_URL', '')


def test_claude_discovery_uses_default_without_legacy_aliases():
    response = asyncio.run(list_models())
    assert [model.id for model in response.data] == ['claude-sonnet-5-5']
    config = integration_configuration()
    assert config['default_model'] == response.data[0].id
    assert config['default_provider'] == 'anthropic'
    assert config['configured'] is True
    assert 'private-anthropic-key' not in str(config)


def test_unconfigured_provider_is_not_advertised(monkeypatch):
    monkeypatch.setattr(settings, 'ANTHROPIC_API_KEY', '')
    assert available_models() == []
    assert integration_configuration()['configured'] is False


def test_extra_models_are_deduplicated_and_filtered_by_provider(monkeypatch):
    monkeypatch.setattr(settings, 'ADDITIONAL_MODELS', ['gpt-custom', 'claude-extra', 'claude-extra', 'unsupported-model'])
    assert available_models() == ['claude-extra', 'claude-sonnet-5-5']
    monkeypatch.setattr(settings, 'OPENAI_API_KEY', 'private-openai-key')
    assert available_models() == ['claude-extra', 'claude-sonnet-5-5', 'gpt-custom']


@pytest.mark.parametrize('model,provider,credential', [
    ('gpt-custom', 'openai', 'OPENAI_API_KEY'),
    ('llama3:latest', 'ollama', 'OLLAMA_BASE_URL'),
])
def test_other_provider_defaults_are_used_without_claude_fallback(monkeypatch, model, provider, credential):
    monkeypatch.setattr(settings, 'DEFAULT_MODEL', model)
    monkeypatch.setattr(settings, credential, 'configured')
    config = integration_configuration()
    assert config['default_model'] == model
    assert config['default_provider'] == provider
    assert config['configured'] is True
    assert available_models() == [model]


def test_unknown_default_has_no_misleading_example(monkeypatch):
    monkeypatch.setattr(settings, 'DEFAULT_MODEL', 'unknown-model')
    config = integration_configuration()
    assert config['configured'] is False
    assert config['default_provider'] is None
    assert config['available_models'] == []
