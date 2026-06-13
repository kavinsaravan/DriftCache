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
import { getDashboardData, DashboardData } from '../api/metricsApi';
import MetricCard from '../components/MetricCard';
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
} from 'recharts';

export default function Dashboard() {
  const { data, isLoading, error } = useQuery<DashboardData>({
    queryKey: ['dashboard', '24h'],
    queryFn: () => getDashboardData('24h'),
    refetchInterval: 30000, // Refetch every 30 seconds
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading metrics...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-red-800">Failed to load metrics. Please check if backend is running.</p>
      </div>
    );
  }

  if (!data) return null;

  const { summary, latency, similarity_distribution, top_cached_prompts } = data;

  // Calculate hit rate percentage
  const hitRatePercent = Math.round(summary.cache_hit_rate * 100);

  // Format currency
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

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
          subtitle={`${latency.cache_latency.average_ms.toFixed(1)}ms vs ${latency.provider_latency.average_ms.toFixed(0)}ms`}
          color="orange"
        />
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

      {/* Top Cached Prompts */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Top Cached Prompts
        </h2>
        <div className="space-y-4">
          {top_cached_prompts.slice(0, 5).map((prompt) => (
            <div
              key={prompt.cache_id}
              className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex-1">
                  <p className="font-medium text-gray-900">{prompt.prompt}</p>
                  <p className="text-sm text-gray-600 mt-1">{prompt.response}</p>
                </div>
                <div className="ml-4 text-right">
                  <p className="text-2xl font-bold text-blue-600">{prompt.hit_count}</p>
                  <p className="text-xs text-gray-500">hits</p>
                </div>
              </div>
              <div className="flex items-center text-xs text-gray-500 space-x-4">
                <span className="px-2 py-1 bg-gray-100 rounded">{prompt.model}</span>
                <span>{new Date(prompt.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Performance Summary */}
      <div className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg p-6 border border-blue-100">
        <div className="flex items-center mb-4">
          <TrendingUp className="w-6 h-6 text-blue-600 mr-2" />
          <h2 className="text-lg font-semibold text-gray-900">Performance Impact</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-3xl font-bold text-blue-600">
              {formatCurrency(summary.estimated_cost_saved_usd)}
            </p>
            <p className="text-sm text-gray-600 mt-1">Cost Saved</p>
          </div>
          <div>
            <p className="text-3xl font-bold text-green-600">
              {latency.speedup_factor.toFixed(0)}x
            </p>
            <p className="text-sm text-gray-600 mt-1">Faster than LLM</p>
          </div>
          <div>
            <p className="text-3xl font-bold text-purple-600">
              {summary.calls_avoided.toLocaleString()}
            </p>
            <p className="text-sm text-gray-600 mt-1">API Calls Avoided</p>
          </div>
        </div>
      </div>
    </div>
  );
}
