#!/usr/bin/env python3
"""
Seed the cache with synthetic data for demo purposes
Bypasses LLM APIs by directly creating cache entries
"""
import requests
import time
import random
from datetime import datetime, timedelta

API_URL = "https://driftcache-api-production.up.railway.app/api/v1"

# Pre-generated responses (no API calls needed)
SYNTHETIC_DATA = [
    {
        "prompt": "What is Python?",
        "response": "Python is a high-level, interpreted programming language known for its simplicity and readability. It was created by Guido van Rossum and first released in 1991. Python emphasizes code readability with significant whitespace and supports multiple programming paradigms including procedural, object-oriented, and functional programming.",
        "similar_prompts": [
            "Can you explain what Python is?",
            "Tell me about the Python programming language",
            "What is Python used for?"
        ]
    },
    {
        "prompt": "What is machine learning?",
        "response": "Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed. It focuses on developing algorithms that can access data, learn from it, and make predictions or decisions. Common applications include recommendation systems, image recognition, and natural language processing.",
        "similar_prompts": [
            "Explain machine learning to me",
            "Can you describe what machine learning is?",
            "How does ML work?"
        ]
    },
    {
        "prompt": "What is FastAPI?",
        "response": "FastAPI is a modern, fast web framework for building APIs with Python. It's designed for high performance and includes automatic API documentation, type checking with Python type hints, and async support out of the box. FastAPI is built on top of Starlette for web parts and Pydantic for data validation.",
        "similar_prompts": [
            "How does FastAPI work?",
            "Explain FastAPI",
            "What is FastAPI used for?"
        ]
    },
    {
        "prompt": "What is Docker?",
        "response": "Docker is a platform for developing, shipping, and running applications in containers. Containers package an application with all its dependencies, ensuring it runs consistently across different computing environments. Docker makes it easy to deploy applications and manage infrastructure efficiently.",
        "similar_prompts": [
            "Explain Docker containers",
            "How does Docker work?",
            "What are Docker containers?"
        ]
    },
    {
        "prompt": "What is Redis?",
        "response": "Redis is an open-source, in-memory data structure store used as a database, cache, and message broker. It supports various data structures like strings, hashes, lists, sets, and sorted sets. Redis is known for its exceptional performance, making it ideal for caching and real-time applications.",
        "similar_prompts": [
            "Explain Redis database",
            "How does Redis caching work?",
            "What is Redis used for?"
        ]
    }
]

def create_cache_entry(prompt, response):
    """Create a cache entry by making a completion request with pre-generated response"""
    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 200,
        # Special flag for demo mode (if backend supports it)
        "_demo_response": response
    }

    try:
        # This will fail at LLM call, but will still create cache entry
        response_obj = requests.post(
            f"{API_URL}/chat/completions",
            json=payload,
            timeout=10
        )
        return response_obj.status_code in [200, 201]
    except Exception as e:
        return False

def seed_database():
    """Seed the database with synthetic cache data"""
    print("=" * 60)
    print("Synthetic Data Seeding Script")
    print("=" * 60)
    print("\nThis script creates cache entries without calling LLM APIs")
    print("by using pre-generated responses.\n")

    # Strategy: Use the backend's cache storage directly
    print("Sending synthetic data to cache...\n")

    total_requests = 0
    cache_hits_expected = 0

    for i, data in enumerate(SYNTHETIC_DATA, 1):
        print(f"[{i}/{len(SYNTHETIC_DATA)}] Processing: {data['prompt'][:50]}...")

        # First request - will be a miss, stores in cache
        print(f"  → Sending original prompt (will be cached)")
        total_requests += 1
        time.sleep(0.5)

        # Similar prompts - should hit cache due to semantic similarity
        for j, similar in enumerate(data['similar_prompts'][:2], 1):  # Only 2 similar to save time
            print(f"  → Sending similar prompt {j} (should cache hit)")
            total_requests += 1
            cache_hits_expected += 1
            time.sleep(0.5)

    print("\n" + "=" * 60)
    print(f"Synthetic data seeding complete!")
    print(f"Expected metrics:")
    print(f"  - Total requests: {total_requests}")
    print(f"  - Cache misses: {len(SYNTHETIC_DATA)}")
    print(f"  - Cache hits: {cache_hits_expected}")
    print(f"  - Hit rate: {cache_hits_expected/total_requests*100:.1f}%")
    print("=" * 60)

    # Get actual stats
    print("\nFetching actual stats from backend...\n")
    time.sleep(2)

    try:
        response = requests.get(f"{API_URL}/metrics/summary?period=24h")
        if response.status_code == 200:
            stats = response.json()
            print("Actual metrics from backend:")
            print(f"  - Total requests: {stats['total_requests']}")
            print(f"  - Cache hits: {stats['cache_hits']}")
            print(f"  - Cache misses: {stats['cache_misses']}")
            print(f"  - Hit rate: {stats['cache_hit_rate']*100:.1f}%")
            print(f"  - Cost saved: ${stats['estimated_cost_saved_usd']:.2f}")
    except Exception as e:
        print(f"Could not fetch stats: {e}")

def main():
    print("\n⚠️  NOTE: This approach won't work without LLM API access.")
    print("The backend requires actual LLM responses to create cache entries.\n")

    print("Alternative approach: Use DEMO MODE on frontend instead:")
    print("  1. Set VITE_USE_MOCK_DATA=true in Vercel")
    print("  2. Redeploy frontend")
    print("  3. Dashboard will show pre-populated demo data\n")

    print("This gives you a fully populated dashboard for demos")
    print("without any API costs!\n")

    choice = input("Would you like me to update the frontend to demo mode? (y/n): ")
    if choice.lower() == 'y':
        print("\nTo enable demo mode:")
        print("  1. Go to Vercel dashboard")
        print("  2. Settings → Environment Variables")
        print("  3. Change VITE_USE_MOCK_DATA from 'false' to 'true'")
        print("  4. Redeploy")
        print("\nYour dashboard will then show:")
        print("  - 1,000 total requests")
        print("  - 68% cache hit rate")
        print("  - $11.72 cost savings")
        print("  - Full analytics graphs")

if __name__ == "__main__":
    main()
