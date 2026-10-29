/**
 * Metrics API Client
 *
 * Connects to DriftCache backend metrics endpoints
 */
import axios from 'axios';
import { API_BASE_URL, getWorkspaceKey, saveWorkspaceKey, workspaceApi } from './workspaceApi';
import {
  mockDashboardData,
  mockTimeSeriesHitRate,
  mockTimeSeriesRequests,
  mockTopCachedPrompts
} from './mockData';

export const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK_DATA === 'true';

const metricsApi = axios.create({
  baseURL: `${API_BASE_URL}/metrics`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// User-supplied credentials remain scoped to this browser tab, never the build.
export const getMetricsKey = getWorkspaceKey;
export const setMetricsKey = saveWorkspaceKey;
metricsApi.interceptors.request.use((config) => {
  const key = getMetricsKey();
  if (key) config.headers.set('Authorization', `Bearer ${key}`);
  return config;
});

export const getMetricsError = (error: unknown): string => {
  if (axios.isAxiosError(error) && [401, 403].includes(error.response?.status || 0)) {
    return 'Access denied. Connect with a valid workspace key, or apply a metrics key above.';
  }
  return 'Unable to load data. Check the API connection and try again.';
};

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

export interface RequestEvent {
  event_id: number;
  request_id: string;
  prompt: string;
  model: string;
  status: string;
  similarity: number | null;
  latency_ms: number | null;
  created_at: string;
}

export interface RequestHistory {
  total: number;
  items: RequestEvent[];
}

export const getTopCachedPrompts = async (
  limit = 10, period = '24h', tenantId?: string
): Promise<TopCachedPrompt[]> => {
  if (USE_MOCK_DATA) return mockTopCachedPrompts.slice(0, limit);
  const response = await metricsApi.get('/top-cached-prompts', {
    params: { limit, period, tenant_id: tenantId },
  });
  return response.data;
};

export const getTimeSeries = async (
  metric: 'hit_rate' | 'requests', period = '24h', interval = '1h', tenantId?: string
): Promise<TimeSeriesDataPoint[]> => {
  if (USE_MOCK_DATA) return metric === 'hit_rate' ? mockTimeSeriesHitRate : mockTimeSeriesRequests;
  const response = await metricsApi.get(`/time-series/${metric}`, {
    params: { period, interval, tenant_id: tenantId },
  });
  return response.data;
};

export const getDashboardData = async (period = '24h', tenantId?: string): Promise<DashboardData> => {
  if (USE_MOCK_DATA) return mockDashboardData;
  const response = await metricsApi.get('/dashboard', { params: { period, tenant_id: tenantId } });
  if (!response.data?.summary || !response.data?.latency || !response.data?.similarity_distribution) {
    throw new Error('Invalid dashboard response');
  }
  return response.data;
};

export const clearRequestHistory = async (): Promise<{deleted_requests: number}> => {
  if (USE_MOCK_DATA) throw new Error('Clearing requests is unavailable in demo mode.');
  return (await workspaceApi.delete('/current/requests')).data;
};

export const getRequestHistory = async (offset = 0, limit = 100): Promise<RequestHistory> => {
  if (USE_MOCK_DATA) {
    const items = mockTopCachedPrompts.map((prompt, index) => ({
      event_id: index + 1, request_id: `demo-${index + 1}`,
      prompt: prompt.prompt, model: prompt.model, created_at: prompt.created_at,
      status: index % 2 ? 'MISS' : 'HIT', similarity: index % 2 ? 0.5 : 0.95,
      latency_ms: 12,
    }));
    return { total: items.length, items: items.slice(offset, offset + limit) };
  }
  const response = await metricsApi.get('/requests', { params: { offset, limit, period: '24h' } });
  return response.data;
};

export default metricsApi;
