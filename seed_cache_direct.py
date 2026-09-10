#!/usr/bin/env python3
"""
Directly seed the cache with sample data for demo purposes
"""
import requests
import json

API_URL = "https://driftcache-api-production.up.railway.app/api/v1"

# Sample cache entries with pre-generated responses
CACHE_ENTRIES = [
    {
        "messages": [{"role": "user", "content": "What is Python?"}],
        "response": "Python is a high-level, interpreted programming language known for its simplicity and readability. Created by Guido van Rossum in 1991, it emphasizes code readability with significant whitespace.",
        "model": "claude-3-5-sonnet-20241022"
    },
    {
        "messages": [{"role": "user", "content": "Explain machine learning"}],
        "response": "Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed. It uses algorithms to identify patterns in data and make predictions or decisions.",
        "model": "claude-3-5-sonnet-20241022"
    },
    {
        "messages": [{"role": "user", "content": "What is FastAPI?"}],
        "response": "FastAPI is a modern, fast web framework for building APIs with Python. It's designed for high performance and includes automatic API documentation, type checking, and async support out of the box.",
        "model": "claude-3-5-sonnet-20241022"
    },
]

def seed_cache_entry(entry):
    """Seed a cache entry by making a request with a mocked response"""
    print(f"Seeding: {entry['messages'][0]['content'][:50]}...")

    # Since we can't actually call the LLM, we'll use the internal cache storage API
    # This would normally be done through the chat completions endpoint
    payload = {
        "messages": entry["messages"],
        "response_text": entry["response"],
        "model_name": entry["model"],
        "tenant_id": "default"
    }

    try:
        # Try to store directly in cache
        response = requests.post(
            f"{API_URL}/cache/store",  # Internal endpoint
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code in [200, 201]:
            print(f"✓ Seeded successfully")
            return True
        else:
            print(f"✗ Failed: {response.status_code}")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    print("=" * 60)
    print("DriftCache Direct Seeding Script")
    print("=" * 60)

    print(f"\nNote: Since OpenAI credits are depleted, this script")
    print(f"would normally seed via direct cache storage.")
    print(f"\nFor a live demo, you need to either:")
    print(f"  1. Add ANTHROPIC_API_KEY to Railway environment variables")
    print(f"  2. Or add OpenAI credits")

    print(f"\nCurrent workaround: Use the demo/seed_cache.py script")
    print(f"which is designed for local database seeding.\n")

    print("=" * 60)

if __name__ == "__main__":
    main()
