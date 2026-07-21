/**
 * Mock data for demo purposes when backend is unavailable
 */
export const mockMetricsSummary = {
  total_requests: 1000,
  cache_hits: 680,
  cache_misses: 320,
  cache_hit_rate: 0.68,
  estimated_cost_saved_usd: 11.72,
  average_latency_ms: 9.2,
  total_provider_calls: 320,
  calls_avoided: 680
};

export const mockLatencyStats = {
  cache_latency: {
    average_ms: 9.2,
    min_ms: 5.1,
    max_ms: 18.3
  },
  provider_latency: {
    average_ms: 1320.0,
    min_ms: 850.0,
    max_ms: 2100.0
  },
  speedup_factor: 143.5
};

export const mockSimilarityDistribution = {
  "0.80-0.85": 45,
  "0.85-0.90": 120,
  "0.90-0.92": 180,
  "0.92-0.94": 220,
  "0.94-0.96": 185,
  "0.96-0.98": 150,
  "0.98-1.00": 100
};

export const mockTopCachedPrompts = [
  {
    cache_id: "cache_1",
    prompt: "What is Python?",
    response: "Python is a high-level, interpreted programming language...",
    hit_count: 52,
    model: "gpt-4o-mini",
    created_at: "2026-07-19T10:30:00Z"
  },
  {
    cache_id: "cache_2",
    prompt: "Explain machine learning",
    response: "Machine learning is a subset of artificial intelligence...",
    hit_count: 48,
    model: "gpt-4o-mini",
    created_at: "2026-07-19T10:35:00Z"
  },
  {
    cache_id: "cache_3",
    prompt: "What is Docker?",
    response: "Docker is a platform for developing, shipping, and running applications...",
    hit_count: 45,
    model: "gpt-4o-mini",
    created_at: "2026-07-19T10:40:00Z"
  },
  {
    cache_id: "cache_4",
    prompt: "How does REST API work?",
    response: "REST (Representational State Transfer) is an architectural style...",
    hit_count: 38,
    model: "gpt-4o-mini",
    created_at: "2026-07-19T11:00:00Z"
  },
  {
    cache_id: "cache_5",
    prompt: "What are microservices?",
    response: "Microservices are an architectural approach where applications...",
    hit_count: 35,
    model: "gpt-4o-mini",
    created_at: "2026-07-19T11:15:00Z"
  }
];

export const mockProviderUsage = {
  openai: {
    total_calls: 320,
    total_tokens: 102000,
    total_cost_usd: 11.72,
    models: {
      "gpt-4o-mini": {
        calls: 320,
        tokens: 102000,
        cost_usd: 11.72
      }
    }
  }
};

// Generate mock time series data
const generateMockTimeSeries = (metric: 'hit_rate' | 'latency' | 'requests') => {
  const now = new Date();
  const data = [];

  for (let i = 23; i >= 0; i--) {
    const timestamp = new Date(now.getTime() - i * 60 * 60 * 1000);
    let value;

    if (metric === 'hit_rate') {
      value = 0.65 + Math.random() * 0.1; // 65-75%
    } else if (metric === 'latency') {
      value = 8 + Math.random() * 4; // 8-12ms
    } else {
      value = Math.floor(40 + Math.random() * 20); // 40-60 requests
    }

    data.push({
      timestamp: timestamp.toISOString(),
      value
    });
  }

  return data;
};

export const mockTimeSeriesHitRate = generateMockTimeSeries('hit_rate');
export const mockTimeSeriesLatency = generateMockTimeSeries('latency');
export const mockTimeSeriesRequests = generateMockTimeSeries('requests');

export const mockDashboardData = {
  period: "24h",
  generated_at: new Date().toISOString(),
  summary: mockMetricsSummary,
  latency: mockLatencyStats,
  similarity_distribution: mockSimilarityDistribution,
  top_cached_prompts: mockTopCachedPrompts,
  provider_usage: mockProviderUsage
};
