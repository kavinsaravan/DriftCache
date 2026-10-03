"""
Pytest tests for FastAPI Gateway endpoints

These are integration tests that require a running server.
Run with: pytest -m integration
"""
import pytest
import httpx
import json


BASE_URL = "http://localhost:8000/api/v1"

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_models_endpoint():
    """Test /v1/models endpoint returns valid model list"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/models")

        # Assert successful response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        # Parse and validate response structure
        data = response.json()
        assert "object" in data, "Response missing 'object' field"
        assert data["object"] == "list", f"Expected object='list', got {data.get('object')}"
        assert "data" in data, "Response missing 'data' field"
        assert isinstance(data["data"], list), "data field should be a list"
        assert len(data["data"]) > 0, "Model list should not be empty"


@pytest.mark.asyncio
async def test_chat_completion_non_streaming():
    """Test /v1/chat/completions returns valid non-streaming response"""
    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "Say 'Hello, DriftCache!' and nothing else."}
        ],
        "temperature": 0.7,
        "max_tokens": 50,
        "stream": False
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/chat/completions",
            json=payload
        )

        # Assert successful response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        # Validate response structure
        data = response.json()
        assert "id" in data, "Response missing 'id' field"
        assert "object" in data, "Response missing 'object' field"
        assert data["object"] == "chat.completion", f"Expected chat.completion, got {data.get('object')}"
        assert "choices" in data, "Response missing 'choices' field"
        assert len(data["choices"]) > 0, "Should have at least one choice"
        assert "message" in data["choices"][0], "Choice missing 'message' field"
        assert "content" in data["choices"][0]["message"], "Message missing 'content'"


@pytest.mark.asyncio
async def test_chat_completion_streaming():
    """Test /v1/chat/completions streaming returns SSE chunks"""
    payload = {
        "model": "claude-3-haiku",
        "messages": [
            {"role": "user", "content": "Count from 1 to 5."}
        ],
        "temperature": 0.7,
        "max_tokens": 100,
        "stream": True
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        async with client.stream(
            "POST",
            f"{BASE_URL}/chat/completions",
            json=payload
        ) as response:
            # Assert streaming started successfully
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"

            # Collect chunks
            chunks_received = 0
            async for chunk in response.aiter_text():
                if chunk.strip():
                    chunks_received += 1

            # Assert we received streaming data
            assert chunks_received > 0, "Should receive at least one streaming chunk"


# Run with: pytest backend/tests/test_gateway.py -v
