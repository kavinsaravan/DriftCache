#!/usr/bin/env python3
"""
Populate DriftCache with sample requests to generate metrics
"""
import requests
import time
import json

API_URL = "https://driftcache-api-production.up.railway.app/api/v1"

# Sample prompts - some similar to create cache hits
PROMPTS = [
    # Group 1: Similar questions about Python (should cache)
    "What is Python?",
    "Can you explain what Python is?",
    "Tell me about the Python programming language",

    # Group 2: Similar questions about machine learning (should cache)
    "What is machine learning?",
    "Explain machine learning to me",
    "Can you describe what machine learning is?",

    # Group 3: Similar questions about FastAPI (should cache)
    "How does FastAPI work?",
    "Explain FastAPI",
    "What is FastAPI used for?",

    # Group 4: Different questions (cache misses)
    "What is the capital of France?",
    "How do you make coffee?",
    "What is the meaning of life?",
    "Explain quantum computing",
    "What is the best programming language?",

    # Repeat some to generate cache hits
    "What is Python?",  # Should hit
    "Explain machine learning to me",  # Should hit
    "How does FastAPI work?",  # Should hit
    "What is Python?",  # Should hit again
    "Can you explain what Python is?",  # Should hit (similar)
]

def send_request(prompt, request_num):
    """Send a chat completion request through DriftCache"""
    print(f"\n[{request_num}/{len(PROMPTS)}] Sending: {prompt[:50]}...")

    payload = {
        "model": "claude-sonnet-5",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.7,
        "max_tokens": 150
    }

    try:
        start = time.time()
        response = requests.post(
            f"{API_URL}/chat/completions",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        elapsed = (time.time() - start) * 1000

        if response.status_code == 200:
            data = response.json()
            content = data['choices'][0]['message']['content'][:100]
            print(f"✓ Success ({elapsed:.0f}ms): {content}...")
            return True
        else:
            print(f"✗ Error {response.status_code}: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"✗ Exception: {e}")
        return False

def get_stats():
    """Get current cache statistics"""
    try:
        response = requests.get(f"{API_URL}/metrics/summary?period=24h")
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Failed to get stats: {e}")
        return None

def main():
    print("=" * 60)
    print("DriftCache Metrics Population Script")
    print("=" * 60)
    print(f"\nAPI URL: {API_URL}")
    print(f"Total requests to send: {len(PROMPTS)}")

    # Check initial stats
    print("\n--- Initial Stats ---")
    initial_stats = get_stats()
    if initial_stats:
        print(json.dumps(initial_stats, indent=2))

    print("\n--- Sending Requests ---")
    successful = 0
    failed = 0

    for i, prompt in enumerate(PROMPTS, 1):
        if send_request(prompt, i):
            successful += 1
        else:
            failed += 1

        # Small delay between requests
        time.sleep(1)

    print("\n" + "=" * 60)
    print(f"Completed! Successful: {successful}, Failed: {failed}")
    print("=" * 60)

    # Get final stats
    print("\n--- Final Stats ---")
    time.sleep(2)  # Wait for metrics to update
    final_stats = get_stats()
    if final_stats:
        print(json.dumps(final_stats, indent=2))

        if initial_stats:
            print("\n--- Changes ---")
            print(f"Total Requests: {initial_stats['total_requests']} → {final_stats['total_requests']}")
            print(f"Cache Hits: {initial_stats['cache_hits']} → {final_stats['cache_hits']}")
            print(f"Cache Hit Rate: {initial_stats['cache_hit_rate']:.1%} → {final_stats['cache_hit_rate']:.1%}")
            print(f"Cost Saved: ${initial_stats['estimated_cost_saved_usd']:.2f} → ${final_stats['estimated_cost_saved_usd']:.2f}")

    print("\n✓ Dashboard should now show metrics!")
    print(f"Visit: https://frontend-kavinsaravan-1858s-projects.vercel.app")

if __name__ == "__main__":
    main()
