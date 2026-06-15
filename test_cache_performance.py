#!/usr/bin/env python3
"""
Simple cache performance test for DriftCache
Tests exact repeats and semantic similarity
"""
import requests
import time
import json

API_URL = "http://localhost:8000/api/v1/chat/completions"

# Test prompts
TEST_PROMPTS = [
    "What is Python?",
    "Explain Docker in simple terms",
    "What are the benefits of cloud computing?",
    "How does REST API work?",
    "Explain machine learning",
]

# Semantic variations (should cache hit with high similarity)
SEMANTIC_VARIATIONS = [
    ("What is Python?", "Can you tell me about Python?"),
    ("Explain Docker in simple terms", "What is Docker? Explain simply"),
    ("What are the benefits of cloud computing?", "Why should I use cloud computing?"),
]

def send_request(prompt):
    """Send request and measure latency"""
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "stream": False
    }

    start = time.time()
    response = requests.post(API_URL, json=payload)
    latency = (time.time() - start) * 1000  # ms

    if response.status_code == 200:
        data = response.json()
        tokens = data.get("usage", {}).get("completion_tokens", 0)
        return {
            "success": True,
            "latency_ms": latency,
            "tokens": tokens,
            "response_length": len(data["choices"][0]["message"]["content"])
        }
    else:
        return {
            "success": False,
            "latency_ms": latency,
            "error": response.text
        }

def main():
    print("=" * 80)
    print("DRIFTCACHE MANUAL PERFORMANCE TEST")
    print("=" * 80)
    print()

    # Clear Redis first
    print("Clearing Redis cache...")
    import subprocess
    subprocess.run(['redis-cli', 'FLUSHALL'], check=True, capture_output=True)
    print("✓ Cache cleared\\n")

    # Test 1: Exact Repeats (should cache hit on 2nd+ requests)
    print("=== Test 1: Exact Repeats (10 repeats each) ===")
    exact_results = {"first": [], "repeats": []}

    for prompt in TEST_PROMPTS:
        print(f"\\nTesting: '{prompt[:50]}...'")

        # First request (should be MISS)
        result = send_request(prompt)
        if result["success"]:
            exact_results["first"].append(result)
            print(f"  First request:  {result['latency_ms']:.0f}ms, {result['tokens']} tokens")

            # Repeat 10 times (should all be HITS)
            repeat_latencies = []
            for i in range(10):
                result = send_request(prompt)
                if result["success"]:
                    repeat_latencies.append(result['latency_ms'])
                    exact_results["repeats"].append(result)
                time.sleep(0.1)  # Small delay

            if repeat_latencies:
                avg_repeat = sum(repeat_latencies) / len(repeat_latencies)
                print(f"  Repeat average: {avg_repeat:.0f}ms (10 requests)")
                print(f"  Speedup: {result['latency_ms'] / avg_repeat:.1f}x faster")

    # Test 2: Semantic Variations (should cache hit with high similarity)
    print("\\n=== Test 2: Semantic Variations ===")
    semantic_results = []

    for original, variation in SEMANTIC_VARIATIONS:
        print(f"\\nOriginal: '{original}'")
        result1 = send_request(original)
        if result1["success"]:
            print(f"  First:     {result1['latency_ms']:.0f}ms")

            time.sleep(0.5)

            print(f"Variation: '{variation}'")
            result2 = send_request(variation)
            if result2["success"]:
                print(f"  Variation: {result2['latency_ms']:.0f}ms")
                semantic_results.append((result1, result2))

                # Check if responses are similar (cache hit)
                if abs(result1["response_length"] - result2["response_length"]) < 50:
                    print(f"  ✓ Likely cache HIT (similar response length)")
                else:
                    print(f"  ✗ Different responses ({result1['response_length']} vs {result2['response_length']} chars)")

    # Calculate overall metrics
    print("\\n" + "=" * 80)
    print("SUMMARY METRICS")
    print("=" * 80)

    if exact_results["first"] and exact_results["repeats"]:
        avg_first = sum(r["latency_ms"] for r in exact_results["first"]) / len(exact_results["first"])
        avg_repeat = sum(r["latency_ms"] for r in exact_results["repeats"]) / len(exact_results["repeats"])

        print(f"\\nExact Repeats:")
        print(f"  First request latency:  {avg_first:.0f}ms")
        print(f"  Cached request latency: {avg_repeat:.0f}ms")
        print(f"  Speedup:                {avg_first / avg_repeat:.1f}x faster")
        print(f"  Total requests:         {len(exact_results['first']) + len(exact_results['repeats'])}")
        print(f"  Cache hits (expected):  {len(exact_results['repeats'])}")

        # Estimate cost savings (gpt-4o-mini pricing)
        input_price = 0.150 / 1_000_000  # per token
        output_price = 0.600 / 1_000_000  # per token
        avg_tokens = sum(r["tokens"] for r in exact_results["repeats"]) / len(exact_results["repeats"])

        tokens_saved = len(exact_results["repeats"]) * avg_tokens
        cost_saved = tokens_saved * output_price + tokens_saved * 0.5 * input_price  # Estimate input tokens

        print(f"\\nCost Savings (estimated):")
        print(f"  Tokens saved:           {tokens_saved:.0f}")
        print(f"  Cost saved:             ${cost_saved:.4f}")

    if semantic_results:
        print(f"\\nSemantic Matching:")
        print(f"  Test pairs:             {len(semantic_results)}")
        print(f"  (Check logs for cache hit/miss details)")

    print("\\n" + "=" * 80)

if __name__ == "__main__":
    main()
