"""
Test script for FastAPI Gateway endpoints
"""
import asyncio
import httpx
import json


BASE_URL = "http://localhost:8000/api/v1"


async def test_models_endpoint():
    """Test /v1/models endpoint"""
    print("\n=== Testing /v1/models ===")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/models")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")


async def test_chat_completion_non_streaming():
    """Test /v1/chat/completions (non-streaming)"""
    print("\n=== Testing /v1/chat/completions (non-streaming) ===")

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
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")


async def test_chat_completion_streaming():
    """Test /v1/chat/completions (streaming)"""
    print("\n=== Testing /v1/chat/completions (streaming) ===")

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
            print(f"Status Code: {response.status_code}")
            print("Streaming response:")
            async for chunk in response.aiter_text():
                if chunk.strip():
                    print(chunk, end='', flush=True)


async def main():
    """Run all tests"""
    print("DriftCache Gateway API Tests")
    print("=" * 50)

    try:
        # Test 1: Models endpoint
        await test_models_endpoint()

        # Test 2: Non-streaming completion
        await test_chat_completion_non_streaming()

        # Test 3: Streaming completion
        await test_chat_completion_streaming()

        print("\n\n" + "=" * 50)
        print("All tests completed!")

    except httpx.ConnectError:
        print("\nError: Could not connect to the server.")
        print("Make sure the FastAPI server is running on http://localhost:8000")
        print("\nTo start the server, run:")
        print("  cd backend && uvicorn app.main:app --reload")
    except Exception as e:
        print(f"\nError occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())
