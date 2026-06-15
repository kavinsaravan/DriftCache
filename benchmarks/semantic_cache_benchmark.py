#!/usr/bin/env python3
"""
Semantic Cache Benchmark Suite

Tests DriftCache performance across multiple dimensions:
- Cache hit rate
- Latency (cache vs provider)
- Cost savings
- Quality metrics (precision, recall, false hit rate)
- Semantic matching accuracy
"""

import json
import time
import statistics
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
import requests
from datetime import datetime


@dataclass
class BenchmarkResult:
    """Complete benchmark results"""
    # Test metadata
    timestamp: str
    total_requests: int
    test_duration_seconds: float
    
    # Cache performance
    cache_hits: int
    cache_misses: int
    cache_hit_rate: float
    
    # Latency metrics (milliseconds)
    avg_cache_latency_ms: float
    p50_cache_latency_ms: float
    p95_cache_latency_ms: float
    p99_cache_latency_ms: float
    avg_provider_latency_ms: float
    p50_provider_latency_ms: float
    p95_provider_latency_ms: float
    p99_provider_latency_ms: float
    latency_improvement_factor: float
    
    # Cost metrics
    tokens_saved: int
    estimated_cost_saved_usd: float
    total_requests_to_provider: int
    requests_avoided: int
    
    # Quality metrics
    precision: float
    recall: float
    false_hit_rate: float
    false_miss_rate: float
    f1_score: float
    
    # Semantic matching accuracy
    semantic_match_accuracy: float
    hard_negative_precision: float
    
    # Throughput
    requests_per_second: float


class DriftCacheBenchmark:
    """Benchmark runner for DriftCache"""
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.datasets_dir = Path(__file__).parent / "datasets"
        self.results_dir = Path(__file__).parent / "results"
        self.results_dir.mkdir(exist_ok=True)
        
        # Pricing estimates (per 1K tokens)
        self.gpt4_input_price = 0.03  # $0.03 per 1K tokens
        self.gpt4_output_price = 0.06  # $0.06 per 1K tokens
        
    def load_dataset(self, filename: str) -> Dict[str, Any]:
        """Load benchmark dataset"""
        dataset_path = self.datasets_dir / filename
        with open(dataset_path, 'r') as f:
            return json.load(f)
    
    def send_request(self, prompt: str, model: str = "gpt-4o-mini") -> Dict[str, Any]:
        """Send request to DriftCache API"""
        url = f"{self.api_base_url}/api/v1/chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 150
        }
        
        start_time = time.time()
        response = requests.post(url, json=payload)
        latency_ms = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "latency_ms": latency_ms,
                "cache_hit": data.get("cache_hit", False),
                "response": data.get("choices", [{}])[0].get("message", {}).get("content", ""),
                "usage": data.get("usage", {}),
                "similarity_score": data.get("similarity_score")
            }
        else:
            return {
                "success": False,
                "latency_ms": latency_ms,
                "error": response.text
            }
    
    def run_exact_repeats_test(self) -> Dict[str, Any]:
        """Test 1: Exact repeats - should have very high cache hit rate"""
        print("\n=== Test 1: Exact Repeats ===")
        dataset = self.load_dataset("easy_duplicates.json")
        
        results = []
        for prompt_config in dataset["prompts"]:
            prompt = prompt_config["prompt"]
            repeat_count = prompt_config["repeat_count"]
            
            print(f"Testing: '{prompt}' ({repeat_count} repeats)")
            for _ in range(repeat_count):
                result = self.send_request(prompt)
                results.append(result)
                time.sleep(0.01)  # Small delay to avoid overwhelming the system
        
        return results
    
    def run_semantic_duplicates_test(self) -> Dict[str, Any]:
        """Test 2: Semantic duplicates - should match semantically similar prompts"""
        print("\n=== Test 2: Semantic Duplicates ===")
        dataset = self.load_dataset("semantic_duplicates.json")
        
        results = []
        group_results = []
        
        for group in dataset["prompt_groups"]:
            print(f"Testing group {group['group_id']}: {group['topic']}")
            group_responses = []
            
            for prompt in group["prompts"]:
                result = self.send_request(prompt)
                results.append(result)
                group_responses.append(result)
                time.sleep(0.01)
            
            # Calculate within-group cache hit rate (should be high after first request)
            group_hits = sum(1 for r in group_responses[1:] if r.get("cache_hit", False))
            group_total = len(group_responses) - 1  # Exclude first request
            group_hit_rate = group_hits / group_total if group_total > 0 else 0
            
            group_results.append({
                "group_id": group["group_id"],
                "topic": group["topic"],
                "cache_hit_rate": group_hit_rate,
                "prompts_tested": len(group_responses)
            })
            
            print(f"  Group hit rate: {group_hit_rate:.2%}")
        
        return results, group_results
    
    def run_hard_negatives_test(self) -> Dict[str, Any]:
        """Test 3: Hard negatives - should NOT match similar-looking but different prompts"""
        print("\n=== Test 3: Hard Negatives ===")
        dataset = self.load_dataset("hard_negatives.json")
        
        results = []
        group_results = []
        
        for group in dataset["prompt_groups"]:
            print(f"Testing group {group['group_id']}: {group['topic']}")
            group_responses = []
            
            for prompt in group["prompts"]:
                result = self.send_request(prompt)
                results.append(result)
                group_responses.append(result)
                time.sleep(0.01)
            
            # Calculate within-group cache hit rate (should be low - these shouldn't match)
            group_hits = sum(1 for r in group_responses[1:] if r.get("cache_hit", False))
            group_total = len(group_responses) - 1
            group_hit_rate = group_hits / group_total if group_total > 0 else 0
            
            # For hard negatives, low hit rate is good (high precision)
            group_results.append({
                "group_id": group["group_id"],
                "topic": group["topic"],
                "false_match_rate": group_hit_rate,  # Should be low
                "prompts_tested": len(group_responses)
            })
            
            print(f"  False match rate: {group_hit_rate:.2%} (lower is better)")
        
        return results, group_results
    
    def calculate_percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile of values"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def calculate_metrics(
        self, 
        all_results: List[Dict[str, Any]], 
        semantic_groups: List[Dict[str, Any]],
        hard_negative_groups: List[Dict[str, Any]],
        total_duration: float
    ) -> BenchmarkResult:
        """Calculate comprehensive benchmark metrics"""
        
        # Filter successful requests
        successful = [r for r in all_results if r.get("success", False)]
        total_requests = len(successful)
        
        # Cache performance
        cache_hits = sum(1 for r in successful if r.get("cache_hit", False))
        cache_misses = total_requests - cache_hits
        cache_hit_rate = cache_hits / total_requests if total_requests > 0 else 0
        
        # Latency metrics
        cache_latencies = [r["latency_ms"] for r in successful if r.get("cache_hit", False)]
        provider_latencies = [r["latency_ms"] for r in successful if not r.get("cache_hit", False)]
        
        avg_cache_latency = statistics.mean(cache_latencies) if cache_latencies else 0
        p50_cache = self.calculate_percentile(cache_latencies, 50) if cache_latencies else 0
        p95_cache = self.calculate_percentile(cache_latencies, 95) if cache_latencies else 0
        p99_cache = self.calculate_percentile(cache_latencies, 99) if cache_latencies else 0
        
        avg_provider_latency = statistics.mean(provider_latencies) if provider_latencies else 0
        p50_provider = self.calculate_percentile(provider_latencies, 50) if provider_latencies else 0
        p95_provider = self.calculate_percentile(provider_latencies, 95) if provider_latencies else 0
        p99_provider = self.calculate_percentile(provider_latencies, 99) if provider_latencies else 0
        
        latency_improvement = avg_provider_latency / avg_cache_latency if avg_cache_latency > 0 else 1
        
        # Cost metrics (estimated)
        # Assume average prompt ~50 tokens, average completion ~100 tokens
        avg_input_tokens = 50
        avg_output_tokens = 100
        
        tokens_per_request = avg_input_tokens + avg_output_tokens
        tokens_saved = cache_hits * tokens_per_request
        
        cost_per_request = (avg_input_tokens / 1000 * self.gpt4_input_price + 
                           avg_output_tokens / 1000 * self.gpt4_output_price)
        estimated_cost_saved = cache_hits * cost_per_request
        
        # Quality metrics - semantic matching accuracy
        semantic_hit_rates = [g["cache_hit_rate"] for g in semantic_groups]
        semantic_match_accuracy = statistics.mean(semantic_hit_rates) if semantic_hit_rates else 0
        
        # Hard negative precision (should NOT match)
        hard_negative_false_matches = [g["false_match_rate"] for g in hard_negative_groups]
        hard_negative_precision = 1 - statistics.mean(hard_negative_false_matches) if hard_negative_false_matches else 1
        
        # Overall quality metrics (simplified estimates)
        # Precision: percentage of cache hits that were correct
        # For semantic duplicates, high hit rate = good
        # For hard negatives, low hit rate = good precision
        precision = hard_negative_precision
        
        # Recall: percentage of semantically similar queries that were cached
        recall = semantic_match_accuracy
        
        # False hit rate: cache returned wrong answer
        false_hit_rate = 1 - precision
        
        # False miss rate: cache missed semantically similar query
        false_miss_rate = 1 - recall
        
        # F1 score
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        # Throughput
        rps = total_requests / total_duration if total_duration > 0 else 0
        
        return BenchmarkResult(
            timestamp=datetime.now().isoformat(),
            total_requests=total_requests,
            test_duration_seconds=total_duration,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            cache_hit_rate=cache_hit_rate,
            avg_cache_latency_ms=avg_cache_latency,
            p50_cache_latency_ms=p50_cache,
            p95_cache_latency_ms=p95_cache,
            p99_cache_latency_ms=p99_cache,
            avg_provider_latency_ms=avg_provider_latency,
            p50_provider_latency_ms=p50_provider,
            p95_provider_latency_ms=p95_provider,
            p99_provider_latency_ms=p99_provider,
            latency_improvement_factor=latency_improvement,
            tokens_saved=tokens_saved,
            estimated_cost_saved_usd=estimated_cost_saved,
            total_requests_to_provider=cache_misses,
            requests_avoided=cache_hits,
            precision=precision,
            recall=recall,
            false_hit_rate=false_hit_rate,
            false_miss_rate=false_miss_rate,
            f1_score=f1_score,
            semantic_match_accuracy=semantic_match_accuracy,
            hard_negative_precision=hard_negative_precision,
            requests_per_second=rps
        )
    
    def print_report(self, results: BenchmarkResult):
        """Print human-readable benchmark report"""
        print("\n" + "=" * 80)
        print("DRIFTCACHE BENCHMARK REPORT")
        print("=" * 80)
        
        print(f"\nTest Date: {results.timestamp}")
        print(f"Total Requests: {results.total_requests}")
        print(f"Test Duration: {results.test_duration_seconds:.2f}s")
        
        print("\n--- CACHE PERFORMANCE ---")
        print(f"Cache Hit Rate: {results.cache_hit_rate:.1%}")
        print(f"Cache Hits: {results.cache_hits}")
        print(f"Cache Misses: {results.cache_misses}")
        print(f"Requests Avoided: {results.requests_avoided}")
        
        print("\n--- LATENCY METRICS ---")
        print(f"Cache Hit Latency:")
        print(f"  Average: {results.avg_cache_latency_ms:.1f}ms")
        print(f"  p50: {results.p50_cache_latency_ms:.1f}ms")
        print(f"  p95: {results.p95_cache_latency_ms:.1f}ms")
        print(f"  p99: {results.p99_cache_latency_ms:.1f}ms")
        
        print(f"\nProvider Call Latency:")
        print(f"  Average: {results.avg_provider_latency_ms:.1f}ms")
        print(f"  p50: {results.p50_provider_latency_ms:.1f}ms")
        print(f"  p95: {results.p95_provider_latency_ms:.1f}ms")
        print(f"  p99: {results.p99_provider_latency_ms:.1f}ms")
        
        print(f"\nLatency Improvement: {results.latency_improvement_factor:.1f}x faster")
        
        print("\n--- COST SAVINGS (Estimated) ---")
        print(f"Tokens Saved: {results.tokens_saved:,}")
        print(f"Estimated Cost Saved: ${results.estimated_cost_saved_usd:.2f}")
        print(f"Provider Requests Avoided: {results.requests_avoided}")
        
        print("\n--- QUALITY METRICS ---")
        print(f"Precision: {results.precision:.1%} (cache accuracy)")
        print(f"Recall: {results.recall:.1%} (semantic match rate)")
        print(f"F1 Score: {results.f1_score:.3f}")
        print(f"False Hit Rate: {results.false_hit_rate:.1%}")
        print(f"False Miss Rate: {results.false_miss_rate:.1%}")
        
        print("\n--- SEMANTIC MATCHING ---")
        print(f"Semantic Match Accuracy: {results.semantic_match_accuracy:.1%}")
        print(f"Hard Negative Precision: {results.hard_negative_precision:.1%}")
        
        print("\n--- THROUGHPUT ---")
        print(f"Requests per Second: {results.requests_per_second:.2f}")
        
        print("\n" + "=" * 80)
    
    def save_results(self, results: BenchmarkResult):
        """Save benchmark results to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.results_dir / f"benchmark_results_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(asdict(results), f, indent=2)
        
        print(f"\nResults saved to: {filename}")
        
        # Also save as latest
        latest_file = self.results_dir / "latest_benchmark.json"
        with open(latest_file, 'w') as f:
            json.dump(asdict(results), f, indent=2)
    
    def run_full_benchmark(self):
        """Run complete benchmark suite"""
        print("\n" + "=" * 80)
        print("STARTING DRIFTCACHE BENCHMARK SUITE")
        print("=" * 80)
        
        start_time = time.time()
        
        # Run all tests
        exact_results = self.run_exact_repeats_test()
        semantic_results, semantic_groups = self.run_semantic_duplicates_test()
        hard_negative_results, hard_negative_groups = self.run_hard_negatives_test()
        
        total_duration = time.time() - start_time
        
        # Combine all results
        all_results = exact_results + semantic_results + hard_negative_results
        
        # Calculate metrics
        metrics = self.calculate_metrics(
            all_results,
            semantic_groups,
            hard_negative_groups,
            total_duration
        )
        
        # Print and save results
        self.print_report(metrics)
        self.save_results(metrics)
        
        return metrics


if __name__ == "__main__":
    benchmark = DriftCacheBenchmark()
    results = benchmark.run_full_benchmark()
