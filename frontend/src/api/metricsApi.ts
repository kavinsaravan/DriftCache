/**
 * Metrics API Client
 *
 * Connects to DriftCache backend metrics endpoints
 */
import axios from 'axios';
import {
  mockDashboardData,
  mockTimeSeriesHitRate,
  mockTimeSeriesRequests,
  mockTopCachedPrompts
} from './mockData';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';
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
  calls_avoided: number;
}

export interface DashboardLatency {
  cache_average_ms: number;
  provider_average_ms: number;
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

export interface TimeSeriesDataPoint {
  timestamp: string;
  value: number;
}

export interface DashboardData {
  period: string;
  generated_at: string;
  summary: MetricsSummary;
  latency: DashboardLatency;
  similarity_distribution: SimilarityDistribution;
}

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
    const params: Record<string, string | number> = { limit, period };
    if (tenantId) params.tenant_id = tenantId;

    const response = await metricsApi.get('/top-cached-prompts', { params });
    return response.data;
  } catch (error) {
    return Promise.resolve(mockTopCachedPrompts);
  }
};

/**
 * Get time series data
 */
export const getTimeSeries = async (
  metric: 'hit_rate' | 'requests',
  period: string = '24h',
  interval: string = '1h',
  tenantId?: string
): Promise<TimeSeriesDataPoint[]> => {
  if (USE_MOCK_DATA) {
    const mockData = metric === 'hit_rate' ? mockTimeSeriesHitRate : mockTimeSeriesRequests;
    return Promise.resolve(mockData);
  }

  try {
    const params: Record<string, string> = { period, interval };
    if (tenantId) params.tenant_id = tenantId;

    const response = await metricsApi.get(`/time-series/${metric}`, { params });
    return response.data;
  } catch (error) {
    const mockData = metric === 'hit_rate' ? mockTimeSeriesHitRate : mockTimeSeriesRequests;
    return Promise.resolve(mockData);
  }
};

/**
 * Get complete dashboard data in one call
 */
export const getDashboardData = async (period: string = '24h', tenantId?: string): Promise<DashboardData> => {
  // Use mock data if enabled or if backend fails
  if (USE_MOCK_DATA) {
    return Promise.resolve(mockDashboardData);
  }

  try {
    const params: Record<string, string> = { period };
    if (tenantId) params.tenant_id = tenantId;

    const response = await metricsApi.get('/dashboard', { params });

    // Validate response has required structure
    if (!response.data || !response.data.summary) {
      return Promise.resolve(mockDashboardData);
    }

    return response.data;
  } catch (error) {
    return Promise.resolve(mockDashboardData);
  }
};

export default metricsApi;
