"""
Test semantic caching end-to-end

Tests the critical path: store a response, then look it up with variations.
These tests catch the majority of caching bugs.
"""
import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from app.cache.service import CacheService
from app.models.schemas import Message


@pytest.fixture
async def isolated_cache_service(tmp_path):
    """
    Create a fresh CacheService with isolated storage

    This prevents tests from polluting each other and the real cache.
    """
    # Create isolated directories
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    # TODO: In a full implementation, override FAISS/metadata paths
    # For now, tests will use shared state (acceptable for initial testing)

    # Flush Redis test database
    cache_service = CacheService()
    if cache_service.redis_store:
        # Use a dedicated test database (e.g., DB 15)
        # await cache_service.redis_store.client.flushdb()
        pass

    yield cache_service

    # Cleanup after test
    # In a full implementation, restore original paths


@pytest.mark.asyncio
async def test_exact_repeat_should_hit():
    """Test 1: Exact repeat should always hit"""
    cache_service = CacheService()

    messages = [{"role": "user", "content": "What is Python?"}]
    messages_typed = [Message(**msg) for msg in messages]

    # Store a response
    await cache_service.store_response(
        messages=messages_typed,
        response_text="Python is a programming language.",
        model_name="gpt-4",
        tenant_id="test-exact"
    )

    # Look up the exact same question
    result = await cache_service.check_cache(
        messages=messages_typed,
        model_name="gpt-4",
        tenant_id="test-exact"
    )

    assert result.is_hit(), f"Expected cache hit for exact repeat, got {result.decision.value}"
    assert result.cached_response is not None
    assert result.cached_response.response_text == "Python is a programming language."
    assert result.similarity is not None
    print(f"✓ Exact match: similarity={result.similarity:.3f}")


@pytest.mark.asyncio
async def test_paraphrase_should_hit():
    """Test 2: Paraphrase should hit (semantic matching)"""
    cache_service = CacheService()

    # Store with one phrasing
    messages_original = [{"role": "user", "content": "What is Python?"}]
    messages_original_typed = [Message(**msg) for msg in messages_original]

    await cache_service.store_response(
        messages=messages_original_typed,
        response_text="Python is a programming language.",
        model_name="gpt-4",
        tenant_id="test-paraphrase"
    )

    # Test cases: (query, should_hit, description)
    test_cases = [
        ("what is python", True, "lowercase"),
        ("What is Python?", True, "same with punctuation"),
        ("Tell me about Python", True, "paraphrase"),
    ]

    for query, should_hit, description in test_cases:
        messages_paraphrase = [{"role": "user", "content": query}]
        messages_paraphrase_typed = [Message(**msg) for msg in messages_paraphrase]

        result = await cache_service.check_cache(
            messages=messages_paraphrase_typed,
            model_name="gpt-4",
            tenant_id="test-paraphrase"
        )

        if should_hit:
            assert result.is_hit(), (
                f"Expected cache hit for {description}: '{query}' "
                f"(similarity={result.similarity if result.similarity else 0:.3f})"
            )
            assert result.cached_response.response_text == "Python is a programming language."
            print(f"✓ {description}: '{query}' → HIT (similarity={result.similarity:.3f})")
        else:
            # For cases we're not confident about, just log
            if result.is_hit():
                print(f"✓ {description}: '{query}' → HIT (similarity={result.similarity:.3f})")
            else:
                sim = result.similarity if result.similarity else 0.0
                print(f"✗ {description}: '{query}' → MISS (similarity={sim:.3f})")


@pytest.mark.asyncio
async def test_same_history_should_hit():
    """Test 3a: Same conversation history should hit"""
    cache_service = CacheService()

    messages = [
        {"role": "user", "content": "What is Redis?"},
        {"role": "assistant", "content": "Redis is an in-memory data store."},
        {"role": "user", "content": "Can you elaborate?"}
    ]
    messages_typed = [Message(**msg) for msg in messages]

    # Store
    await cache_service.store_response(
        messages=messages_typed,
        response_text="Redis stores data in RAM for fast access.",
        model_name="gpt-4",
        tenant_id="test-history-hit"
    )

    # Look up with the exact same history
    result = await cache_service.check_cache(
        messages=messages_typed,
        model_name="gpt-4",
        tenant_id="test-history-hit"
    )

    assert result.is_hit(), f"Expected cache hit for same history, got {result.decision.value}"
    assert result.cached_response.response_text == "Redis stores data in RAM for fast access."
    print(f"✓ Same history: HIT (similarity={result.similarity:.3f})")


@pytest.mark.asyncio
async def test_different_history_should_miss():
    """Test 3b: Different conversation history should miss"""
    cache_service = CacheService()

    # Store a response in conversation A
    messages_a = [
        {"role": "user", "content": "What is Redis?"},
        {"role": "assistant", "content": "Redis is an in-memory data store."},
        {"role": "user", "content": "Can you elaborate?"}
    ]
    messages_a_typed = [Message(**msg) for msg in messages_a]

    await cache_service.store_response(
        messages=messages_a_typed,
        response_text="Redis stores data in RAM for fast access.",
        model_name="gpt-4",
        tenant_id="test-history-miss"
    )

    # Look up the same final question but in conversation B
    messages_b = [
        {"role": "user", "content": "What is Python?"},
        {"role": "assistant", "content": "Python is a programming language."},
        {"role": "user", "content": "Can you elaborate?"}
    ]
    messages_b_typed = [Message(**msg) for msg in messages_b]

    result = await cache_service.check_cache(
        messages=messages_b_typed,
        model_name="gpt-4",
        tenant_id="test-history-miss"
    )

    # Should miss because conversation history is different
    assert not result.is_hit(), (
        f"Expected cache miss for different history, got {result.decision.value}. "
        f"This would be a false hit returning the wrong conversation's answer!"
    )
    print("✓ Different history: MISS (correct)")


@pytest.mark.asyncio
async def test_same_system_prompt_should_hit():
    """Test 4a: Same system prompt should hit"""
    cache_service = CacheService()

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is Python?"}
    ]
    messages_typed = [Message(**msg) for msg in messages]

    # Store
    await cache_service.store_response(
        messages=messages_typed,
        response_text="Python is a programming language.",
        model_name="gpt-4",
        tenant_id="test-system-hit"
    )

    # Look up with the same system prompt
    result = await cache_service.check_cache(
        messages=messages_typed,
        model_name="gpt-4",
        tenant_id="test-system-hit"
    )

    assert result.is_hit(), f"Expected cache hit for same system prompt, got {result.decision.value}"
    assert result.cached_response.response_text == "Python is a programming language."
    print(f"✓ Same system prompt: HIT (similarity={result.similarity:.3f})")


@pytest.mark.asyncio
async def test_different_system_prompt_should_miss():
    """Test 4b: Different system prompt should miss"""
    cache_service = CacheService()

    # Store with system prompt A
    messages_a = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is Python?"}
    ]
    messages_a_typed = [Message(**msg) for msg in messages_a]

    await cache_service.store_response(
        messages=messages_a_typed,
        response_text="Python is a programming language.",
        model_name="gpt-4",
        tenant_id="test-system-miss"
    )

    # Look up with system prompt B
    messages_b = [
        {"role": "system", "content": "You are a concise assistant."},
        {"role": "user", "content": "What is Python?"}
    ]
    messages_b_typed = [Message(**msg) for msg in messages_b]

    result = await cache_service.check_cache(
        messages=messages_b_typed,
        model_name="gpt-4",
        tenant_id="test-system-miss"
    )

    # Should miss because system prompt is different
    assert not result.is_hit(), (
        f"Expected cache miss for different system prompt, got {result.decision.value}. "
        f"Different system prompts should not match!"
    )
    print("✓ Different system prompt: MISS (correct)")


@pytest.mark.asyncio
async def test_same_tenant_should_hit():
    """Test 5a: Same tenant should hit"""
    cache_service = CacheService()

    messages = [{"role": "user", "content": "What is Python?"}]
    messages_typed = [Message(**msg) for msg in messages]

    # Store for tenant A
    await cache_service.store_response(
        messages=messages_typed,
        response_text="Python is a programming language.",
        model_name="gpt-4",
        tenant_id="tenant-a"
    )

    # Look up for the same tenant
    result = await cache_service.check_cache(
        messages=messages_typed,
        model_name="gpt-4",
        tenant_id="tenant-a"
    )

    assert result.is_hit(), f"Expected cache hit for same tenant, got {result.decision.value}"
    assert result.cached_response.response_text == "Python is a programming language."
    print(f"✓ Same tenant: HIT (similarity={result.similarity:.3f})")


@pytest.mark.asyncio
async def test_different_tenant_should_miss():
    """Test 5b: Different tenant should miss"""
    cache_service = CacheService()

    messages = [{"role": "user", "content": "What is Python?"}]
    messages_typed = [Message(**msg) for msg in messages]

    # Store for tenant A
    await cache_service.store_response(
        messages=messages_typed,
        response_text="Python is a programming language.",
        model_name="gpt-4",
        tenant_id="tenant-a-diff"
    )

    # Look up for tenant B
    result = await cache_service.check_cache(
        messages=messages_typed,
        model_name="gpt-4",
        tenant_id="tenant-b-diff"
    )

    # Should miss because tenant is different
    assert not result.is_hit(), (
        f"Expected cache miss for different tenant, got {result.decision.value}. "
        f"Tenant isolation is broken!"
    )
    print("✓ Different tenant: MISS (correct)")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
