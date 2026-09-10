#!/usr/bin/env python3
"""
Test Redis connection to Railway
"""
import asyncio
import redis.asyncio as redis
from redis.exceptions import RedisError

# Railway Redis URL (get from environment or hardcode for testing)
REDIS_URL = "redis://default:PASSWORD@redis.railway.internal:6379"  # Replace with actual URL

async def test_redis():
    """Test Redis connection"""
    print("Testing Redis connection...")
    print(f"URL: {REDIS_URL[:30]}...")  # Print first 30 chars

    try:
        # Create Redis client
        client = redis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )

        print("✓ Client created")

        # Test ping
        response = await client.ping()
        print(f"✓ Ping successful: {response}")

        # Test set/get
        await client.set("test_key", "test_value")
        value = await client.get("test_key")
        print(f"✓ Set/Get successful: {value}")

        # Clean up
        await client.delete("test_key")
        await client.aclose()

        print("\n✓ All tests passed!")

    except RedisError as e:
        print(f"\n✗ Redis error: {e}")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(test_redis())
