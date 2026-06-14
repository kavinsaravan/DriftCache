# DriftCache Benchmarks

This directory contains benchmarking and load testing tools for DriftCache.

## Benchmark Scripts

### semantic_cache_benchmark.py

Comprehensive benchmark suite that tests:
- **Cache hit rate**: How often semantically similar queries are cached
- **Latency comparison**: Cache hits vs provider calls
- **Cost savings**: Estimated savings from avoided LLM calls
- **Quality metrics**: Precision, recall, false hit/miss rates
- **Semantic matching**: Accuracy on semantic duplicates and hard negatives

**Usage:**
```bash
python benchmarks/semantic_cache_benchmark.py
```

**Output:**
- Console report with all metrics
- JSON results saved to `results/benchmark_results_<timestamp>.json`
- Latest results at `results/latest_benchmark.json`

### load_test.py

Load testing for concurrent requests:
- **Throughput**: Requests per second under load
- **Error rate**: Failure rate under concurrent load
- **Latency under load**: p50, p95, p99 latencies
- **Cache performance**: Hit rate under concurrent access

**Usage:**
```bash
python benchmarks/load_test.py
```

**Configuration:**
- Default: 1000 requests with 20 concurrent connections
- Modify in script for different load profiles

## Benchmark Datasets

### datasets/easy_duplicates.json
Exact duplicate prompts repeated many times.
- **Purpose**: Verify basic caching works
- **Expected**: ~99% cache hit rate after first request

### datasets/semantic_duplicates.json
Semantically similar prompts with different wording.
- **Purpose**: Verify semantic matching works
- **Expected**: High within-group cache hit rate (>70%)
- **10 prompt groups** with 5 variations each

### datasets/hard_negatives.json
Similar-looking prompts that should NOT match.
- **Purpose**: Verify precision (no false positives)
- **Expected**: Low within-group cache hit rate (<10%)
- **10 prompt groups** testing different topics

## Results Directory

Benchmark results are saved to `results/`:
- `benchmark_results_<timestamp>.json` - Full benchmark results
- `load_test_<timestamp>.json` - Load test results
- `latest_benchmark.json` - Most recent benchmark (symlink)

## API Endpoints

The backend provides benchmark endpoints:

```bash
# Get latest benchmark summary
GET /benchmark/summary

# Get detailed stats
GET /benchmark/stats

# Run quick benchmark
POST /benchmark/quick
{
  "num_requests": 100,
  "test_semantic_matching": true,
  "test_hard_negatives": true
}

# Health check
GET /benchmark/health
```

## Key Metrics

### Cache Performance
- **Cache Hit Rate**: % of requests served from cache
- **Target**: >65% for real-world workloads

### Latency
- **Cache Hit Latency**: <15ms p95
- **Provider Call Latency**: 1000-2000ms typical
- **Improvement Factor**: 100x+ speedup

### Cost Savings
- **Tokens Saved**: Count of tokens not sent to provider
- **Estimated Cost**: Based on GPT-4 pricing (~$0.03/1K input tokens)
- **Target**: 60-70% cost reduction

### Quality Metrics
- **Precision**: % of cache hits that are correct (target: >90%)
- **Recall**: % of semantic duplicates that are cached (target: >70%)
- **False Hit Rate**: % of incorrect cache matches (target: <10%)
- **F1 Score**: Harmonic mean of precision and recall

### Semantic Matching
- **Semantic Match Accuracy**: Hit rate on semantic duplicates
- **Hard Negative Precision**: Ability to avoid false matches

## Example Results

```json
{
  "total_requests": 1000,
  "cache_hit_rate": 0.68,
  "avg_cache_latency_ms": 9.2,
  "p95_cache_latency_ms": 14.8,
  "avg_provider_latency_ms": 1320,
  "latency_improvement_factor": 143.5,
  "estimated_cost_saved_usd": 11.72,
  "precision": 0.94,
  "recall": 0.76,
  "false_hit_rate": 0.06,
  "semantic_match_accuracy": 0.76,
  "hard_negative_precision": 0.94,
  "requests_per_second": 45.2
}
```

## Running Benchmarks in Docker

```bash
# Start DriftCache
docker compose up -d

# Run benchmarks from host
pip install requests aiohttp
python benchmarks/semantic_cache_benchmark.py
python benchmarks/load_test.py

# Or run inside backend container
docker exec -it driftcache-backend python /app/../benchmarks/semantic_cache_benchmark.py
```

## Customizing Benchmarks

### Adding New Datasets
1. Create JSON file in `datasets/`
2. Follow existing format (see examples)
3. Update benchmark script to load new dataset

### Adjusting Test Parameters
Edit the scripts:
- `num_requests`: Total requests to send
- `concurrent_requests`: Concurrent connections (load test)
- `repeat_count`: Times to repeat each prompt
- Model pricing estimates

### Creating Custom Tests
```python
from semantic_cache_benchmark import DriftCacheBenchmark

benchmark = DriftCacheBenchmark()
# Add custom test methods
results = benchmark.run_custom_test()
```
