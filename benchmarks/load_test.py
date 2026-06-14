#!/usr/bin/env python3
"""
Load Test for DriftCache

Tests system behavior under concurrent load:
- Requests per second
- Error rate under load
- Latency under concurrent requests
- System stability
"""

import json
import time
import asyncio
import aiohttp
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import statistics
from pathlib import Path


@dataclass
class LoadTestResult:
    """Load test results"""
    timestamp: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    error_rate: float
    test_duration_seconds: float
    
    # Throughput
    requests_per_second: float
    avg_concurrent_requests: int
    
    # Latency under load
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    max_latency_ms: float
    min_latency_ms: float
    
    # Cache performance under load
    cache_hit_rate: float
    cache_hits: int
    cache_misses: int
    
    # Error details
    error_types: Dict[str, int]


class LoadTester:
    """Load testing for DriftCache"""
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.results_dir = Path(__file__).parent / "results"
        self.results_dir.mkdir(exist_ok=True)
    
    async def send_async_request(
        self, 
        session: aiohttp.ClientSession, 
        prompt: str,
        request_id: int
    ) -> Dict[str, Any]:
        """Send async request to DriftCache"""
        url = f"{self.api_base_url}/v1/chat/completions"
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 100
        }
        
        start_time = time.time()
        try:
            async with session.post(url, json=payload) as response:
                latency_ms = (time.time() - start_time) * 1000
                
                if response.status == 200:
                    data = await response.json()
                    return {
                        "request_id": request_id,
                        "success": True,
                        "latency_ms": latency_ms,
                        "cache_hit": data.get("cache_hit", False),
                        "status_code": response.status
                    }
                else:
                    return {
                        "request_id": request_id,
                        "success": False,
                        "latency_ms": latency_ms,
                        "status_code": response.status,
                        "error": f"HTTP {response.status}"
                    }
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return {
                "request_id": request_id,
                "success": False,
                "latency_ms": latency_ms,
                "error": str(e)
            }
    
    async def run_concurrent_requests(
        self,
        prompts: List[str],
        concurrent_requests: int = 10
    ) -> List[Dict[str, Any]]:
        """Send multiple concurrent requests"""
        print(f"\nSending {len(prompts)} requests with {concurrent_requests} concurrent connections...")
        
        results = []
        connector = aiohttp.TCPConnector(limit=concurrent_requests)
        timeout = aiohttp.ClientTimeout(total=60)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = [
                self.send_async_request(session, prompt, idx)
                for idx, prompt in enumerate(prompts)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = [r for r in results if isinstance(r, dict)]
        return valid_results
    
    def generate_test_prompts(self, count: int = 1000) -> List[str]:
        """Generate test prompts with mix of duplicates and unique"""
        base_prompts = [
            "What is Python?",
            "Explain machine learning.",
            "What are the benefits of cloud computing?",
            "How does Docker work?",
            "Explain REST API.",
            "What is Kubernetes?",
            "Describe microservices architecture.",
            "What is continuous integration?",
            "Explain database indexing.",
            "What is Redis used for?",
            "What is semantic caching?",
            "Explain GraphQL.",
            "What is serverless computing?",
            "Describe event-driven architecture.",
            "What is API gateway?",
            "Explain load balancing.",
            "What is CDN?",
            "Describe OAuth 2.0.",
            "What is JWT?",
            "Explain CORS.",
        ]
        
        prompts = []
        for i in range(count):
            # 70% duplicates, 30% unique variations
            if i % 10 < 7:
                prompts.append(base_prompts[i % len(base_prompts)])
            else:
                base = base_prompts[i % len(base_prompts)]
                prompts.append(f"{base} (variation {i})")
        
        return prompts
    
    def calculate_percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def analyze_results(
        self,
        results: List[Dict[str, Any]],
        duration: float
    ) -> LoadTestResult:
        """Analyze load test results"""
        total_requests = len(results)
        successful = [r for r in results if r.get("success", False)]
        failed = [r for r in results if not r.get("success", False)]
        
        successful_count = len(successful)
        failed_count = len(failed)
        error_rate = failed_count / total_requests if total_requests > 0 else 0
        
        # Latency metrics
        latencies = [r["latency_ms"] for r in successful]
        avg_latency = statistics.mean(latencies) if latencies else 0
        p50_latency = self.calculate_percentile(latencies, 50) if latencies else 0
        p95_latency = self.calculate_percentile(latencies, 95) if latencies else 0
        p99_latency = self.calculate_percentile(latencies, 99) if latencies else 0
        max_latency = max(latencies) if latencies else 0
        min_latency = min(latencies) if latencies else 0
        
        # Cache performance
        cache_hits = sum(1 for r in successful if r.get("cache_hit", False))
        cache_misses = successful_count - cache_hits
        cache_hit_rate = cache_hits / successful_count if successful_count > 0 else 0
        
        # Error analysis
        error_types = {}
        for r in failed:
            error_msg = r.get("error", "Unknown")
            error_types[error_msg] = error_types.get(error_msg, 0) + 1
        
        # Throughput
        rps = total_requests / duration if duration > 0 else 0
        
        return LoadTestResult(
            timestamp=datetime.now().isoformat(),
            total_requests=total_requests,
            successful_requests=successful_count,
            failed_requests=failed_count,
            error_rate=error_rate,
            test_duration_seconds=duration,
            requests_per_second=rps,
            avg_concurrent_requests=20,  # From test config
            avg_latency_ms=avg_latency,
            p50_latency_ms=p50_latency,
            p95_latency_ms=p95_latency,
            p99_latency_ms=p99_latency,
            max_latency_ms=max_latency,
            min_latency_ms=min_latency,
            cache_hit_rate=cache_hit_rate,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            error_types=error_types
        )
    
    def print_report(self, results: LoadTestResult):
        """Print load test report"""
        print("\n" + "=" * 80)
        print("DRIFTCACHE LOAD TEST REPORT")
        print("=" * 80)
        
        print(f"\nTest Date: {results.timestamp}")
        print(f"Test Duration: {results.test_duration_seconds:.2f}s")
        print(f"Total Requests: {results.total_requests}")
        
        print("\n--- THROUGHPUT ---")
        print(f"Requests per Second: {results.requests_per_second:.2f}")
        print(f"Concurrent Connections: {results.avg_concurrent_requests}")
        
        print("\n--- SUCCESS RATE ---")
        print(f"Successful Requests: {results.successful_requests} ({(1-results.error_rate)*100:.1f}%)")
        print(f"Failed Requests: {results.failed_requests} ({results.error_rate*100:.1f}%)")
        
        print("\n--- LATENCY UNDER LOAD ---")
        print(f"Average: {results.avg_latency_ms:.1f}ms")
        print(f"p50: {results.p50_latency_ms:.1f}ms")
        print(f"p95: {results.p95_latency_ms:.1f}ms")
        print(f"p99: {results.p99_latency_ms:.1f}ms")
        print(f"Min: {results.min_latency_ms:.1f}ms")
        print(f"Max: {results.max_latency_ms:.1f}ms")
        
        print("\n--- CACHE PERFORMANCE ---")
        print(f"Cache Hit Rate: {results.cache_hit_rate:.1%}")
        print(f"Cache Hits: {results.cache_hits}")
        print(f"Cache Misses: {results.cache_misses}")
        
        if results.error_types:
            print("\n--- ERROR BREAKDOWN ---")
            for error, count in results.error_types.items():
                print(f"  {error}: {count}")
        
        print("\n" + "=" * 80)
    
    def save_results(self, results: LoadTestResult):
        """Save results to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.results_dir / f"load_test_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(asdict(results), f, indent=2)
        
        print(f"\nResults saved to: {filename}")
    
    async def run_load_test(
        self,
        num_requests: int = 1000,
        concurrent_connections: int = 20
    ):
        """Run complete load test"""
        print("\n" + "=" * 80)
        print("STARTING DRIFTCACHE LOAD TEST")
        print("=" * 80)
        print(f"Requests: {num_requests}")
        print(f"Concurrent Connections: {concurrent_connections}")
        
        # Generate test prompts
        prompts = self.generate_test_prompts(num_requests)
        
        # Run test
        start_time = time.time()
        results = await self.run_concurrent_requests(prompts, concurrent_connections)
        duration = time.time() - start_time
        
        # Analyze and report
        metrics = self.analyze_results(results, duration)
        self.print_report(metrics)
        self.save_results(metrics)
        
        return metrics


async def main():
    """Main entry point"""
    tester = LoadTester()
    
    # Run load test with 1000 requests, 20 concurrent connections
    await tester.run_load_test(num_requests=1000, concurrent_connections=20)


if __name__ == "__main__":
    asyncio.run(main())
