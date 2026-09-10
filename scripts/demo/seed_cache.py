#!/usr/bin/env python3
"""
Seed Cache Script

Populates DriftCache with initial data to set up demo scenarios.
"""

import json
import time
import requests
from pathlib import Path
from typing import List, Dict, Any


class CacheSeeder:
    """Seeds the cache with initial data"""
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.prompts_dir = Path(__file__).parent / "prompts"
    
    def send_request(self, prompt: str, model: str = "gpt-4") -> Dict[str, Any]:
        """Send request to DriftCache"""
        url = f"{self.api_base_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 150
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json(),
                    "cache_hit": response.json().get("cache_hit", False)
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def seed_baseline_software_prompts(self):
        """Seed cache with baseline software engineering prompts"""
        print("\n" + "=" * 70)
        print("SEEDING BASELINE CACHE - Software Engineering Domain")
        print("=" * 70)
        
        with open(self.prompts_dir / "drift_prompts.json") as f:
            data = json.load(f)
        
        baseline_prompts = data["baseline_prompts"]["prompts"]
        
        print(f"\nSending {len(baseline_prompts)} baseline prompts...")
        for i, prompt in enumerate(baseline_prompts, 1):
            print(f"  [{i}/{len(baseline_prompts)}] {prompt[:50]}...")
            result = self.send_request(prompt)
            
            if result["success"]:
                cache_hit = result["data"].get("cache_hit", False)
                status = "HIT" if cache_hit else "MISS"
                print(f"      ✓ {status}")
            else:
                print(f"      ✗ Error: {result['error']}")
            
            time.sleep(0.5)  # Be nice to the API
        
        print("\n✓ Baseline cache seeded successfully")
    
    def seed_semantic_duplicates(self):
        """Seed cache with semantic duplicate examples"""
        print("\n" + "=" * 70)
        print("SEEDING SEMANTIC DUPLICATES")
        print("=" * 70)
        
        with open(self.prompts_dir / "semantic_duplicates.json") as f:
            data = json.load(f)
        
        for pair in data["prompt_pairs"]:
            topic = pair["topic"]
            original = pair["original"]
            
            print(f"\nTopic: {topic}")
            print(f"  Original: {original}")
            
            # Send original
            result = self.send_request(original)
            if result["success"]:
                print(f"    ✓ Cached")
            else:
                print(f"    ✗ Error: {result['error']}")
            
            time.sleep(0.5)
        
        print("\n✓ Semantic duplicates seeded")
    
    def verify_cache_status(self):
        """Verify cache has been populated"""
        print("\n" + "=" * 70)
        print("VERIFYING CACHE STATUS")
        print("=" * 70)
        
        try:
            # Get cache metrics
            response = requests.get(f"{self.api_base_url}/metrics/cache-performance")
            if response.status_code == 200:
                metrics = response.json()
                print(f"\nCache Metrics:")
                print(f"  Total Requests: {metrics.get('total_requests', 'N/A')}")
                print(f"  Cache Hits: {metrics.get('cache_hits', 'N/A')}")
                print(f"  Cache Misses: {metrics.get('cache_misses', 'N/A')}")
                print(f"  Hit Rate: {metrics.get('cache_hit_rate', 'N/A')}")
            
            # Get drift status
            response = requests.get(f"{self.api_base_url}/drift/status")
            if response.status_code == 200:
                drift_data = response.json()
                print(f"\nDrift Status:")
                print(f"  Drift Score: {drift_data.get('drift_score', 'N/A')}")
                print(f"  Status: {drift_data.get('status', 'N/A')}")
            
            print("\n✓ Cache verification complete")
            
        except Exception as e:
            print(f"\n✗ Verification failed: {e}")
    
    def run_full_seed(self):
        """Run complete seeding workflow"""
        print("\n" + "=" * 70)
        print("DRIFTCACHE DEMO - CACHE SEEDING")
        print("=" * 70)
        print("\nThis will populate the cache with baseline data for demo scenarios.")
        
        # Seed baseline
        self.seed_baseline_software_prompts()
        
        # Seed semantic duplicates
        self.seed_semantic_duplicates()
        
        # Verify
        self.verify_cache_status()
        
        print("\n" + "=" * 70)
        print("SEEDING COMPLETE")
        print("=" * 70)
        print("\nThe cache is now ready for demo scenarios.")
        print("\nNext steps:")
        print("  1. Run semantic cache demo: python demo/run_demo.py --scenario semantic")
        print("  2. Run drift detection demo: python demo/generate_drift.py")
        print("  3. Run full demo: python demo/run_demo.py --all")


if __name__ == "__main__":
    seeder = CacheSeeder()
    seeder.run_full_seed()
