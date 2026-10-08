/**
 * Dashboard Overview Page
 *
 * Main demo screen showing high-level metrics
 *
 * Success criteria: Recruiter understands project in 10 seconds
 */
import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  CheckCircle2,
  DollarSign,
  TrendingUp,
  Zap,
} from 'lucide-react';
import {
  getDashboardData,
  getTimeSeries,
  DashboardData,
  TimeSeriesDataPoint,
} from '../api/metricsApi';
import MetricCard from '../components/MetricCard';
import LoadingSpinner from '../components/LoadingSpinner';
import { formatCurrency } from '../utils/formatting';
import { REFETCH_INTERVALS } from '../utils/constants';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  AreaChart,
  Area,
} from 'recharts';

export default function Dashboard() {
  const { data, isLoading, error } = useQuery<DashboardData>({
    queryKey: ['dashboard', '24h'],
    queryFn: () => getDashboardData('24h'),
    refetchInterval: REFETCH_INTERVALS.FAST,
  });

  const {
    data: hitRateData,
    isLoading: isHitRateLoading,
    error: hitRateError,
  } = useQuery<TimeSeriesDataPoint[]>({
    queryKey: ['timeseries', 'hit_rate', '24h'],
    queryFn: () => getTimeSeries('hit_rate', '24h', '1h'),
    refetchInterval: REFETCH_INTERVALS.FAST,
  });

  if (isLoading || isHitRateLoading) {
    return <LoadingSpinner message="Loading metrics..." />;
  }

  if (error || hitRateError) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-red-800">Failed to load metrics. Please check if backend is running.</p>
      </div>
    );
  }

  // Safety check: ensure data has required structure
  if (!data || !data.summary) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <p className="text-yellow-800">No data available. Please check backend connection.</p>
      </div>
    );
  }

  const { summary, latency, similarity_distribution } = data;

  // Calculate hit rate percentage
  const hitRatePercent = Math.round((summary?.cache_hit_rate || 0) * 100);

  // Prepare similarity distribution data for chart
  const similarityData = Object.entries(similarity_distribution).map(([range, count]) => ({
    range,
    count,
  }));

  // Prepare hit/miss data for pie chart
  const hitMissData = [
    { name: 'Cache Hits', value: summary.cache_hits, color: '#10b981' },
    { name: 'Cache Misses', value: summary.cache_misses, color: '#ef4444' },
  ];

  const hitRateChartData = hitRateData?.map((point) => ({
    time: new Date(point.timestamp).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    }),
    rate: Number((point.value * 100).toFixed(1)),
  }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Dashboard Overview</h1>
        <p className="text-gray-600 mt-1">
          Real-time metrics from the last 24 hours
        </p>
      </div>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          icon={Activity}
          label="Total Requests"
          value={summary.total_requests.toLocaleString()}
          subtitle="Last 24 hours"
          color="blue"
        />

        <MetricCard
          icon={CheckCircle2}
          label="Cache Hit Rate"
          value={`${hitRatePercent}%`}
          subtitle={`${summary.cache_hits.toLocaleString()} hits, ${summary.cache_misses.toLocaleString()} misses`}
          color="green"
        />

        <MetricCard
          icon={DollarSign}
          label="Cost Saved"
          value={formatCurrency(summary.estimated_cost_saved_usd)}
          subtitle={`${summary.calls_avoided.toLocaleString()} LLM calls avoided`}
          color="purple"
        />

        <MetricCard
          icon={Zap}
          label="Cache Speedup"
          value={`${latency.speedup_factor.toFixed(0)}x`}
          subtitle={`${latency.cache_average_ms.toFixed(1)}ms vs ${latency.provider_average_ms.toFixed(0)}ms`}
          color="orange"
        />

      </div>

      {/* Cache Hit Rate Over Time */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center mb-4">
          <TrendingUp className="w-5 h-5 text-blue-600 mr-2" />
          <h2 className="text-lg font-semibold text-gray-900">
            Cache Hit Rate Over Time
          </h2>
        </div>
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={hitRateChartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" />
            <YAxis
              domain={[0, 100]}
              label={{ value: 'Hit Rate (%)', angle: -90, position: 'insideLeft' }}
            />
            <Tooltip formatter={(value) => [`${value}%`, 'Hit Rate']} />
            <Area
              type="monotone"
              dataKey="rate"
              stroke="#3b82f6"
              fill="#93c5fd"
              name="Hit Rate (%)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Hit/Miss Distribution */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Cache Hit Distribution
          </h2>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={hitMissData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, value, percent }) =>
                  `${name}: ${value} (${(percent * 100).toFixed(0)}%)`
                }
                outerRadius={100}
                fill="#8884d8"
                dataKey="value"
              >
                {hitMissData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Similarity Distribution */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Similarity Score Distribution
          </h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={similarityData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="range" angle={-45} textAnchor="end" height={80} />
              <YAxis />
              <Tooltip />
              <Bar dataKey="count" fill="#3b82f6" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

    </div>
  );
}
