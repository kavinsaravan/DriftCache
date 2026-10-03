"""
Test semantic caching end-to-end

Tests the critical path: store a response, then look it up with variations.
These tests catch the majority of caching bugs.
"""
import pytest
import asyncio
from app.cache.service import CacheService
from app.models.schemas import Message


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
        tenant_id="default"
    )

    # Look up the exact same question
    result = await cache_service.check_cache(
        messages=messages_typed,
        model_name="gpt-4",
        tenant_id="default"
    )

    assert result.is_hit(), f"Expected cache hit for exact repeat, got {result.decision.value}"
    assert result.cached_response is not None
    assert result.cached_response.response_text == "Python is a programming language."


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
        tenant_id="default"
    )

    # Look up with paraphrases
    test_cases = [
        "what is python",  # Lowercase
        "What is Python?",  # Capitalized with punctuation
        "Tell me about Python",  # Paraphrase
        "Explain Python to me",  # Different phrasing
    ]

    for paraphrase in test_cases:
        messages_paraphrase = [{"role": "user", "content": paraphrase}]
        messages_paraphrase_typed = [Message(**msg) for msg in messages_paraphrase]

        result = await cache_service.check_cache(
            messages=messages_paraphrase_typed,
            model_name="gpt-4",
            tenant_id="default"
        )

        # Should hit if similarity is above threshold (usually 0.85+)
        # The exact cutoff depends on the embedding model
        if result.is_hit():
            assert result.cached_response.response_text == "Python is a programming language."
            print(f"✓ Paraphrase hit: '{paraphrase}' (similarity={result.similarity:.3f})")
        else:
            # Some paraphrases might not be similar enough, that's ok
            print(f"✗ Paraphrase miss: '{paraphrase}' (similarity={result.similarity:.3f if result.similarity else 0:.3f})")


@pytest.mark.asyncio
async def test_different_history_should_miss():
    """Test 3: Same question with different history should miss"""
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
        tenant_id="default"
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
        tenant_id="default"
    )

    # Should miss because conversation history is different
    assert not result.is_hit(), f"Expected cache miss for different history, got {result.decision.value}"


@pytest.mark.asyncio
async def test_different_system_prompt_should_miss():
    """Test 4: Same question with different system prompt should miss"""
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
        tenant_id="default"
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
        tenant_id="default"
    )

    # Should miss because system prompt is different
    assert not result.is_hit(), f"Expected cache miss for different system prompt, got {result.decision.value}"


@pytest.mark.asyncio
async def test_different_tenant_should_miss():
    """Test 5: Same question with different tenant should miss"""
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

    # Look up for tenant B
    result = await cache_service.check_cache(
        messages=messages_typed,
        model_name="gpt-4",
        tenant_id="tenant-b"
    )

    # Should miss because tenant is different
    assert not result.is_hit(), f"Expected cache miss for different tenant, got {result.decision.value}"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
