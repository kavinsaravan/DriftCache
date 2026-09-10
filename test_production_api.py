#!/usr/bin/env python3
"""
Test Production API - Populate Dashboard with Sample Data
"""
import requests
import time
import json
from datetime import datetime

API_URL = "https://driftcache-api.onrender.com/api/v1/chat/completions"

# Test prompts - exact repeats and semantic variations
TEST_SCENARIOS = [
    {
        "name": "Exact Repeats - Python Question",
        "prompts": ["What is Python?"] * 5,  # Ask 5 times
    },
    {
        "name": "Exact Repeats - Docker Question", 
        "prompts": ["Explain Docker in simple terms."] * 5,
    },
    {
        "name": "Semantic Variations - Machine Learning",
        "prompts": [
            "What is machine learning?",
            "Explain machine learning to me.",
            "Can you tell me about machine learning?",
            "Define machine learning.",
        ],
    },
    {
        "name": "Semantic Variations - REST API",
        "prompts": [
            "What is a REST API?",
            "Explain REST APIs.",
            "Tell me about RESTful APIs.",
        ],
    },
    {
        "name": "Different Topics - No Cache Hits",
        "prompts": [
            "What is Kubernetes?",
            "How does GraphQL work?",
            "Explain microservices architecture.",
        ],
    },
]

def make_request(prompt: str, request_num: int, total: int):
    """Make a single API request"""
    print(f"[{request_num}/{total}] Sending: '{prompt[:50]}...'")
    
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 100,
        "temperature": 0.7
    }
    
    try:
        start = time.time()
        response = requests.post(API_URL, json=payload, timeout=30)
        latency = (time.time() - start) * 1000
        
        if response.status_code == 200:
            data = response.json()
            cache_hit = data.get("cache_hit", False)
            similarity = data.get("similarity_score")
            
            status = "HIT" if cache_hit else "MISS"
            similarity_str = f"(similarity: {similarity:.3f})" if similarity else ""
            
            print(f"  ✓ {status} - {latency:.0f}ms {similarity_str}")
            return {
                "success": True,
                "cache_hit": cache_hit,
                "latency_ms": latency,
                "similarity": similarity
            }
        else:
            print(f"  ✗ Error: {response.status_code} - {response.text[:100]}")
            return {"success": False, "error": response.status_code}
            
    except Exception as e:
        print(f"  ✗ Exception: {str(e)}")
        return {"success": False, "error": str(e)}

def run_test():
    """Run all test scenarios"""
    print("=" * 80)
    print("TESTING PRODUCTION API - POPULATING DASHBOARD")
    print("=" * 80)
    print(f"\nAPI URL: {API_URL}")
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    all_results = []
    total_requests = sum(len(scenario["prompts"]) for scenario in TEST_SCENARIOS)
    request_num = 0
    
    for scenario in TEST_SCENARIOS:
        print(f"\n{'=' * 80}")
        print(f"Scenario: {scenario['name']}")
        print(f"{'=' * 80}\n")
        
        for prompt in scenario["prompts"]:
            request_num += 1
            result = make_request(prompt, request_num, total_requests)
            all_results.append(result)
            time.sleep(0.5)  # Small delay between requests
    
    # Calculate summary statistics
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}\n")
    
    successful = [r for r in all_results if r.get("success")]
    total = len(successful)
    cache_hits = sum(1 for r in successful if r.get("cache_hit"))
    cache_misses = total - cache_hits
    hit_rate = (cache_hits / total * 100) if total > 0 else 0
    
    avg_latency = sum(r.get("latency_ms", 0) for r in successful) / total if total > 0 else 0
    
    print(f"Total Requests:  {total}")
    print(f"Cache Hits:      {cache_hits}")
    print(f"Cache Misses:    {cache_misses}")
    print(f"Hit Rate:        {hit_rate:.1f}%")
    print(f"Avg Latency:     {avg_latency:.0f}ms")
    
    print(f"\n{'=' * 80}")
    print("✓ Test Complete!")
    print(f"\nCheck your dashboard at: https://drift-cache-jfin.vercel.app")
    print(f"{'=' * 80}\n")

if __name__ == "__main__":
    run_test()
