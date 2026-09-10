#!/usr/bin/env python3
"""
Populate production DriftCache with realistic demo data for dashboard demo.

This script creates:
- Cache entries in Redis
- Historical events in PostgreSQL
- Realistic latency, hit rates, and cost savings data
"""

import asyncio
import os
import random
from datetime import datetime, timedelta
from typing import List
import httpx

# Production API URL
API_BASE_URL = os.getenv("API_URL", "https://driftcache-api-production.up.railway.app")

# Sample prompts for realistic data
SAMPLE_PROMPTS = [
    ("What is Python?", "Python is a high-level, interpreted programming language known for its simplicity and readability. It supports multiple programming paradigms including procedural, object-oriented, and functional programming."),
    ("Explain machine learning", "Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed. It uses algorithms to analyze data, identify patterns, and make decisions."),
    ("How does HTTP work?", "HTTP (HyperText Transfer Protocol) is an application-layer protocol for transmitting hypermedia documents. It follows a client-server model where clients send requests and servers respond with the requested resources."),
    ("What is Docker?", "Docker is a platform for developing, shipping, and running applications in containers. Containers package software with all dependencies, ensuring consistency across different environments."),
    ("Explain REST API", "REST (Representational State Transfer) API is an architectural style for building web services. It uses HTTP methods (GET, POST, PUT, DELETE) to perform operations on resources identified by URLs."),
    ("What is TypeScript?", "TypeScript is a strongly-typed superset of JavaScript that compiles to plain JavaScript. It adds static typing, classes, and interfaces to help catch errors during development."),
    ("How does Redis work?", "Redis is an in-memory data structure store used as a database, cache, and message broker. It supports various data structures like strings, hashes, lists, and sets with sub-millisecond latency."),
    ("Explain PostgreSQL", "PostgreSQL is an advanced open-source relational database system. It's known for its reliability, feature robustness, and performance. It supports both SQL and JSON querying."),
    ("What is FastAPI?", "FastAPI is a modern, fast web framework for building APIs with Python based on standard Python type hints. It provides automatic API documentation, data validation, and high performance."),
    ("Describe semantic caching", "Semantic caching stores and retrieves data based on meaning rather than exact matches. It uses similarity measures to find cached responses that are semantically similar to new queries."),
    ("What is embeddings?", "Embeddings are vector representations of data that capture semantic meaning. They map high-dimensional data (like text) into lower-dimensional continuous vector spaces where similar items are close together."),
    ("How does LangChain work?", "LangChain is a framework for developing applications powered by language models. It provides tools for chaining LLM calls, managing prompts, and integrating external data sources."),
    ("Explain vector databases", "Vector databases are specialized databases optimized for storing and querying high-dimensional vectors. They enable fast similarity searches essential for AI applications like semantic search and recommendation systems."),
    ("What is prompt engineering?", "Prompt engineering is the practice of designing effective prompts for language models. It involves crafting instructions that guide the model to produce desired outputs with better accuracy and relevance."),
    ("Describe API caching strategies", "API caching strategies include CDN caching, reverse proxy caching, application-level caching, and database query caching. Each strategy optimizes different layers to reduce latency and costs."),
]

MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]


async def send_cache_request(prompt: str, expected_response: str = None, model: str = "gpt-4o-mini") -> dict:
    """Send a request to the DriftCache API to create a cache entry."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{API_BASE_URL}/api/v1/chat/completions",
                json={
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "model": model,
                    "max_tokens": 500,
                    "temperature": 0.7,
                    "stream": False
                },
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error sending request: {e}")
            return None


async def populate_cache_entries():
    """Populate cache with initial entries."""
    print("Populating cache entries...")

    for i, (prompt, expected_response) in enumerate(SAMPLE_PROMPTS):
        model = random.choice(MODELS)
        print(f"Creating cache entry {i+1}/{len(SAMPLE_PROMPTS)}: {prompt[:50]}...")

        result = await send_cache_request(prompt, model)
        if result:
            print(f"  ✓ Created cache entry (cache_id: {result.get('cache_id', 'N/A')})")

        # Small delay to avoid overwhelming the API
        await asyncio.sleep(0.5)

    print(f"\n✓ Created {len(SAMPLE_PROMPTS)} initial cache entries\n")


async def simulate_cache_hits():
    """Simulate cache hits by re-requesting cached prompts."""
    print("Simulating cache hits...")

    # Generate realistic hit patterns (some prompts get hit more than others)
    hit_counts = {
        0: 52,   # "What is Python?" - most popular
        1: 38,   # "Explain machine learning"
        2: 31,   # "How does HTTP work?"
        3: 28,   # "What is Docker?"
        4: 24,   # "Explain REST API"
        5: 19,   # Other prompts get fewer hits
        6: 15,
        7: 12,
        8: 10,
        9: 8,
        10: 6,
        11: 5,
        12: 4,
        13: 3,
        14: 2,
    }

    total_hits = sum(hit_counts.values())
    completed = 0

    for idx, count in hit_counts.items():
        if idx >= len(SAMPLE_PROMPTS):
            continue

        prompt, _ = SAMPLE_PROMPTS[idx]
        model = random.choice(MODELS)

        for hit_num in range(count):
            # Add slight variations to simulate real usage over time
            variation = random.choice(["", " ", "  "])  # Slight prompt variations
            varied_prompt = prompt + variation

            await send_cache_request(varied_prompt, model)
            completed += 1

            if completed % 20 == 0:
                print(f"  Progress: {completed}/{total_hits} cache hits simulated")

            # Faster iteration
            await asyncio.sleep(0.2)

    print(f"\n✓ Simulated {total_hits} cache hits\n")


async def simulate_cache_misses():
    """Simulate cache misses with unique prompts."""
    print("Simulating cache misses...")

    miss_prompts = [
        "What is the capital of France in 2026?",
        "How to train a neural network from scratch?",
        "Explain quantum computing basics",
        "What are the latest trends in AI?",
        "How to optimize database queries?",
        "What is Kubernetes orchestration?",
        "Explain microservices architecture",
        "How does blockchain technology work?",
        "What is edge computing?",
        "Describe serverless architecture",
        "How to implement OAuth2?",
        "What is GraphQL?",
        "Explain CI/CD pipelines",
        "How does DNS work?",
        "What is load balancing?",
    ]

    for i, prompt in enumerate(miss_prompts):
        model = random.choice(MODELS)
        await send_cache_request(prompt, model)

        if (i + 1) % 5 == 0:
            print(f"  Progress: {i+1}/{len(miss_prompts)} cache misses simulated")

        await asyncio.sleep(0.3)

    print(f"\n✓ Simulated {len(miss_prompts)} cache misses\n")


async def verify_data():
    """Verify that data was populated correctly."""
    print("\nVerifying populated data...")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Check dashboard metrics
            response = await client.get(f"{API_BASE_URL}/api/v1/metrics/dashboard?period=24h")
            response.raise_for_status()
            data = response.json()

            summary = data.get("summary", {})
            print(f"\n✓ Dashboard Data:")
            print(f"  Total Requests: {summary.get('total_requests', 0)}")
            print(f"  Cache Hits: {summary.get('cache_hits', 0)}")
            print(f"  Cache Misses: {summary.get('cache_misses', 0)}")
            print(f"  Hit Rate: {summary.get('cache_hit_rate', 0):.2%}")
            print(f"  Cost Saved: ${summary.get('estimated_cost_saved_usd', 0):.2f}")
            print(f"  Calls Avoided: {summary.get('calls_avoided', 0)}")

            # Check top cached prompts
            top_prompts = data.get("top_cached_prompts", [])
            print(f"\n✓ Top Cached Prompts: {len(top_prompts)}")
            for i, prompt_data in enumerate(top_prompts[:3], 1):
                print(f"  {i}. '{prompt_data.get('prompt', '')[:40]}...' - {prompt_data.get('hit_count', 0)} hits")

            print("\n✓ Data verification complete!")

        except Exception as e:
            print(f"Error verifying data: {e}")


async def main():
    """Main function to populate demo data."""
    print("=" * 60)
    print("DriftCache Demo Data Population Script")
    print("=" * 60)
    print(f"\nTarget API: {API_BASE_URL}\n")

    # Step 1: Create initial cache entries
    await populate_cache_entries()

    # Step 2: Simulate realistic cache hit patterns
    await simulate_cache_hits()

    # Step 3: Simulate some cache misses for realistic hit rate
    await simulate_cache_misses()

    # Step 4: Verify the data
    await verify_data()

    print("\n" + "=" * 60)
    print("Demo data population complete!")
    print("Your dashboard should now show realistic metrics.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
