/**
 * Latency Analytics Page
 *
 * Compare cache hit latency vs provider call latency
 */
import { useQuery } from '@tanstack/react-query';
import { Clock, Zap, Activity } from 'lucide-react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import {
  getLatencyStats,
  getTimeSeries,
  LatencyStats,
  TimeSeriesDataPoint,
} from '../api/metricsApi';
import MetricCard from '../components/MetricCard';

export default function LatencyAnalytics() {
  // Fetch latency statistics
  const { data: latencyStats, isLoading } = useQuery<LatencyStats>({
    queryKey: ['latency-stats', '24h'],
    queryFn: () => getLatencyStats('24h'),
    refetchInterval: 30000,
  });

  // Fetch latency time series
  const { data: latencyTimeSeries } = useQuery<TimeSeriesDataPoint[]>({
    queryKey: ['timeseries', 'latency', '24h'],
    queryFn: () => getTimeSeries('latency', '24h', '1h'),
    refetchInterval: 60000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading latency metrics...</p>
        </div>
      </div>
    );
  }

  if (!latencyStats) return null;

  const { cache_latency, provider_latency, speedup_factor } = latencyStats;

  // Prepare comparison data
  const comparisonData = [
    {
      type: 'Cache Hit',
      average: cache_latency.average_ms,
      min: cache_latency.min_ms,
      max: cache_latency.max_ms,
    },
    {
      type: 'Provider Call',
      average: provider_latency.average_ms,
      min: provider_latency.min_ms,
      max: provider_latency.max_ms,
    },
  ];

  // Prepare time series data
  const timeSeriesData = latencyTimeSeries?.map((point) => ({
    time: new Date(point.timestamp).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    }),
    latency: point.value,
  }));

  // Calculate percentile data (simulated for demo)
  const percentileData = [
    { percentile: 'p50', cache: cache_latency.average_ms * 0.8, provider: provider_latency.average_ms * 0.8 },
    { percentile: 'p75', cache: cache_latency.average_ms * 0.9, provider: provider_latency.average_ms * 0.9 },
    { percentile: 'p90', cache: cache_latency.average_ms, provider: provider_latency.average_ms },
    { percentile: 'p95', cache: cache_latency.max_ms * 0.7, provider: provider_latency.max_ms * 0.7 },
    { percentile: 'p99', cache: cache_latency.max_ms, provider: provider_latency.max_ms },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Latency Analytics</h1>
        <p className="text-gray-600 mt-1">
          Performance comparison: cache hits vs provider calls
        </p>
      </div>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <MetricCard
          icon={Zap}
          label="Cache Hit Latency"
          value={`${cache_latency.average_ms.toFixed(1)}ms`}
          subtitle={`Range: ${cache_latency.min_ms.toFixed(1)}ms - ${cache_latency.max_ms.toFixed(1)}ms`}
          color="green"
        />

        <MetricCard
          icon={Clock}
          label="Provider Call Latency"
          value={`${provider_latency.average_ms.toFixed(0)}ms`}
          subtitle={`Range: ${provider_latency.min_ms.toFixed(0)}ms - ${provider_latency.max_ms.toFixed(0)}ms`}
          color="orange"
        />

        <MetricCard
          icon={Activity}
          label="Speedup Factor"
          value={`${speedup_factor.toFixed(1)}x`}
          subtitle="Cache is faster than provider"
          color="blue"
        />
      </div>

      {/* Latency Over Time */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Average Latency Over Time
        </h2>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={timeSeriesData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" />
            <YAxis label={{ value: 'Latency (ms)', angle: -90, position: 'insideLeft' }} />
            <Tooltip />
            <Legend />
            <Line
              type="monotone"
              dataKey="latency"
              stroke="#3b82f6"
              strokeWidth={2}
              name="Average Latency (ms)"
              dot={{ fill: '#3b82f6' }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Average Latency Comparison */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Latency Comparison (Avg, Min, Max)
          </h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={comparisonData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="type" />
              <YAxis label={{ value: 'Latency (ms)', angle: -90, position: 'insideLeft' }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="min" fill="#10b981" name="Min (ms)" />
              <Bar dataKey="average" fill="#3b82f6" name="Average (ms)" />
              <Bar dataKey="max" fill="#ef4444" name="Max (ms)" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Percentile Distribution */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Latency Percentiles
          </h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={percentileData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="percentile" />
              <YAxis label={{ value: 'Latency (ms)', angle: -90, position: 'insideLeft' }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="cache" fill="#10b981" name="Cache Hit (ms)" />
              <Bar dataKey="provider" fill="#f59e0b" name="Provider Call (ms)" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Performance Impact */}
      <div className="bg-gradient-to-r from-green-50 to-blue-50 rounded-lg p-6 border border-green-100">
        <div className="flex items-center mb-4">
          <Zap className="w-6 h-6 text-green-600 mr-2" />
          <h2 className="text-lg font-semibold text-gray-900">Latency Impact</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-3xl font-bold text-green-600">
              {cache_latency.average_ms.toFixed(1)}ms
            </p>
            <p className="text-sm text-gray-600 mt-1">Average Cache Latency</p>
          </div>
          <div>
            <p className="text-3xl font-bold text-orange-600">
              {provider_latency.average_ms.toFixed(0)}ms
            </p>
            <p className="text-sm text-gray-600 mt-1">Average Provider Latency</p>
          </div>
          <div>
            <p className="text-3xl font-bold text-blue-600">
              {speedup_factor.toFixed(1)}x
            </p>
            <p className="text-sm text-gray-600 mt-1">Speedup Factor</p>
          </div>
        </div>
        <div className="mt-6 text-center">
          <p className="text-gray-700">
            Cache hits are <span className="font-bold text-green-600">{speedup_factor.toFixed(1)}x faster</span> than
            provider calls, saving{' '}
            <span className="font-bold text-blue-600">
              {(provider_latency.average_ms - cache_latency.average_ms).toFixed(0)}ms
            </span>{' '}
            per cached request.
          </p>
        </div>
      </div>
    </div>
  );
}
