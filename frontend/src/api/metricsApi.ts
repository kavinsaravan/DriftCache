/**
 * Metrics API Client
 *
 * Connects to DriftCache backend metrics endpoints
 */
import axios from 'axios';
import {
  mockDashboardData,
  mockTimeSeriesHitRate,
  mockTimeSeriesLatency,
  mockTimeSeriesRequests,
  mockLatencyStats,
  mockSimilarityDistribution,
  mockTopCachedPrompts,
  mockProviderUsage
} from './mockData';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK_DATA === 'true';

const metricsApi = axios.create({
  baseURL: `${API_BASE_URL}/metrics`,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface MetricsSummary {
  total_requests: number;
  cache_hits: number;
  cache_misses: number;
  cache_hit_rate: number;
  estimated_cost_saved_usd: number;
  average_latency_ms: number;
  total_provider_calls: number;
  calls_avoided: number;
}

export interface LatencyStats {
  cache_latency: {
    average_ms: number;
    min_ms: number;
    max_ms: number;
  };
  provider_latency: {
    average_ms: number;
    min_ms: number;
    max_ms: number;
  };
  speedup_factor: number;
}

export interface SimilarityDistribution {
  [key: string]: number;
}

export interface TopCachedPrompt {
  cache_id: string;
  prompt: string;
  response: string;
  hit_count: number;
  model: string;
  created_at: string;
}

export interface ProviderUsage {
  [provider: string]: {
    total_calls: number;
    total_tokens: number;
    total_cost_usd: number;
    models: {
      [model: string]: {
        calls: number;
        tokens: number;
        cost_usd: number;
      };
    };
  };
}

export interface TimeSeriesDataPoint {
  timestamp: string;
  value: number;
}

export interface DashboardData {
  period: string;
  generated_at: string;
  summary: MetricsSummary;
  latency: LatencyStats;
  similarity_distribution: SimilarityDistribution;
  top_cached_prompts: TopCachedPrompt[];
  provider_usage: ProviderUsage;
}

/**
 * Get summary metrics
 */
export const getSummary = async (period: string = '24h', tenantId?: string): Promise<MetricsSummary> => {
  if (USE_MOCK_DATA) return Promise.resolve(mockDashboardData.summary);

  try {
    const params: any = { period };
    if (tenantId) params.tenant_id = tenantId;

    const response = await metricsApi.get('/summary', { params });
    return response.data;
  } catch (error) {
    console.warn('Falling back to mock summary data');
    return Promise.resolve(mockDashboardData.summary);
  }
};

/**
 * Get latency statistics
 */
export const getLatencyStats = async (period: string = '24h', tenantId?: string): Promise<LatencyStats> => {
  if (USE_MOCK_DATA) return Promise.resolve(mockLatencyStats);

  try {
    const params: any = { period };
    if (tenantId) params.tenant_id = tenantId;

    const response = await metricsApi.get('/latency', { params });
    return response.data;
  } catch (error) {
    console.warn('Falling back to mock latency stats');
    return Promise.resolve(mockLatencyStats);
  }
};

/**
 * Get similarity score distribution
 */
export const getSimilarityDistribution = async (
  period: string = '24h',
  bins: number = 10,
  tenantId?: string
): Promise<SimilarityDistribution> => {
  if (USE_MOCK_DATA) return Promise.resolve(mockSimilarityDistribution);

  try {
    const params: any = { period, bins };
    if (tenantId) params.tenant_id = tenantId;

    const response = await metricsApi.get('/similarity-distribution', { params });
    return response.data;
  } catch (error) {
    console.warn('Falling back to mock similarity distribution');
    return Promise.resolve(mockSimilarityDistribution);
  }
};

/**
 * Get top cached prompts
 */
export const getTopCachedPrompts = async (
  limit: number = 10,
  period: string = '24h',
  tenantId?: string
): Promise<TopCachedPrompt[]> => {
  if (USE_MOCK_DATA) return Promise.resolve(mockTopCachedPrompts);

  try {
    const params: any = { limit, period };
    if (tenantId) params.tenant_id = tenantId;

    const response = await metricsApi.get('/top-cached-prompts', { params });
    return response.data;
  } catch (error) {
    console.warn('Falling back to mock top cached prompts');
    return Promise.resolve(mockTopCachedPrompts);
  }
};

/**
 * Get provider usage statistics
 */
export const getProviderUsage = async (period: string = '24h', tenantId?: string): Promise<ProviderUsage> => {
  if (USE_MOCK_DATA) return Promise.resolve(mockProviderUsage);

  try {
    const params: any = { period };
    if (tenantId) params.tenant_id = tenantId;

    const response = await metricsApi.get('/provider-usage', { params });
    return response.data;
  } catch (error) {
    console.warn('Falling back to mock provider usage');
    return Promise.resolve(mockProviderUsage);
  }
};

/**
 * Get time series data
 */
export const getTimeSeries = async (
  metric: 'hit_rate' | 'latency' | 'requests',
  period: string = '24h',
  interval: string = '1h',
  tenantId?: string
): Promise<TimeSeriesDataPoint[]> => {
  if (USE_MOCK_DATA) {
    const mockData = metric === 'hit_rate' ? mockTimeSeriesHitRate :
                     metric === 'latency' ? mockTimeSeriesLatency :
                     mockTimeSeriesRequests;
    return Promise.resolve(mockData);
  }

  try {
    const params: any = { period, interval };
    if (tenantId) params.tenant_id = tenantId;

    const response = await metricsApi.get(`/time-series/${metric}`, { params });
    return response.data;
  } catch (error) {
    console.warn(`Falling back to mock time series for ${metric}`);
    const mockData = metric === 'hit_rate' ? mockTimeSeriesHitRate :
                     metric === 'latency' ? mockTimeSeriesLatency :
                     mockTimeSeriesRequests;
    return Promise.resolve(mockData);
  }
};

/**
 * Get complete dashboard data in one call
 */
export const getDashboardData = async (period: string = '24h', tenantId?: string): Promise<DashboardData> => {
  // Use mock data if enabled or if backend fails
  if (USE_MOCK_DATA) {
    console.log('Using mock data for demo');
    return Promise.resolve(mockDashboardData);
  }

  try {
    const params: any = { period };
    if (tenantId) params.tenant_id = tenantId;

    const response = await metricsApi.get('/dashboard', { params });

    // Validate response has required structure
    if (!response.data || !response.data.summary || !response.data.latency) {
      console.warn('Invalid response structure, falling back to mock data');
      return Promise.resolve(mockDashboardData);
    }

    return response.data;
  } catch (error) {
    console.error('Backend unavailable, falling back to mock data', error);
    return Promise.resolve(mockDashboardData);
  }
};

export default metricsApi;
