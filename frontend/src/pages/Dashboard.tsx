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

  // Safety check: ensure data has required structure
  if (!data || !data.summary || !data.latency) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <p className="text-yellow-800">No data available. Please check backend connection.</p>
      </div>
    );
  }

  const { summary, latency, similarity_distribution, top_cached_prompts } = data;

  // Calculate hit rate percentage
  const hitRatePercent = Math.round((summary?.cache_hit_rate || 0) * 100);

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
    <div className="space-y-8">
      {/* Header */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-blue-600 via-purple-600 to-pink-600 p-8 shadow-2xl">
        <div className="absolute inset-0 bg-grid-white/10 [mask-image:linear-gradient(0deg,transparent,black)]"></div>
        <div className="relative">
          <h1 className="text-4xl font-bold text-white mb-2">Dashboard Overview</h1>
          <p className="text-blue-100 text-lg">
            Real-time semantic caching analytics and performance metrics
          </p>
        </div>
        {/* Decorative elements */}
        <div className="absolute top-0 right-0 w-64 h-64 bg-white/5 rounded-full blur-3xl"></div>
        <div className="absolute bottom-0 left-0 w-48 h-48 bg-purple-500/20 rounded-full blur-2xl"></div>
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
        <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-lg border border-gray-100 p-6 hover:shadow-xl transition-shadow">
          <div className="flex items-center mb-6">
            <div className="w-1 h-6 bg-gradient-to-b from-green-500 to-emerald-600 rounded-full mr-3"></div>
            <h2 className="text-lg font-bold text-gray-900">
              Cache Hit Distribution
            </h2>
          </div>
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
        <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-lg border border-gray-100 p-6 hover:shadow-xl transition-shadow">
          <div className="flex items-center mb-6">
            <div className="w-1 h-6 bg-gradient-to-b from-blue-500 to-purple-600 rounded-full mr-3"></div>
            <h2 className="text-lg font-bold text-gray-900">
              Similarity Score Distribution
            </h2>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={similarityData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="range" angle={-45} textAnchor="end" height={80} stroke="#9ca3af" />
              <YAxis stroke="#9ca3af" />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgba(255, 255, 255, 0.95)',
                  borderRadius: '8px',
                  border: '1px solid #e5e7eb',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
                }}
              />
              <Bar dataKey="count" fill="url(#colorGradient)" radius={[8, 8, 0, 0]} />
              <defs>
                <linearGradient id="colorGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity={1} />
                  <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.8} />
                </linearGradient>
              </defs>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Top Cached Prompts */}
      <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-lg border border-gray-100 p-6">
        <div className="flex items-center mb-6">
          <div className="w-1 h-6 bg-gradient-to-b from-purple-500 to-pink-600 rounded-full mr-3"></div>
          <h2 className="text-lg font-bold text-gray-900">
            Top Cached Prompts
          </h2>
        </div>
        <div className="space-y-3">
          {top_cached_prompts.slice(0, 5).map((prompt, index) => (
            <div
              key={prompt.cache_id}
              className="group relative border border-gray-200/50 rounded-xl p-4 hover:border-purple-300 hover:shadow-lg hover:shadow-purple-100/50 transition-all duration-200"
            >
              {/* Hit count badge */}
              <div className="absolute -top-2 -right-2 bg-gradient-to-br from-blue-600 to-purple-600 text-white rounded-full w-10 h-10 flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform">
                <div className="text-center">
                  <p className="text-sm font-bold">{prompt.hit_count}</p>
                </div>
              </div>

              <div className="pr-8">
                <p className="font-semibold text-gray-900 mb-2">{prompt.prompt}</p>
                <p className="text-sm text-gray-600 line-clamp-2 mb-3">{prompt.response}</p>
                <div className="flex items-center text-xs text-gray-500 space-x-3">
                  <span className="px-3 py-1 bg-gradient-to-r from-blue-50 to-purple-50 text-blue-700 font-medium rounded-full border border-blue-200/50">
                    {prompt.model}
                  </span>
                  <span className="flex items-center">
                    <span className="w-1.5 h-1.5 bg-gray-400 rounded-full mr-2"></span>
                    {new Date(prompt.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Performance Summary */}
      <div className="relative overflow-hidden bg-gradient-to-br from-blue-600 via-purple-600 to-pink-600 rounded-2xl p-8 shadow-2xl">
        <div className="absolute inset-0 bg-grid-white/10"></div>
        <div className="relative">
          <div className="flex items-center mb-6">
            <div className="p-2 bg-white/20 rounded-lg backdrop-blur-sm">
              <TrendingUp className="w-6 h-6 text-white" />
            </div>
            <h2 className="text-2xl font-bold text-white ml-3">Performance Impact</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-white/10 backdrop-blur-sm rounded-xl p-6 border border-white/20">
              <p className="text-sm font-semibold text-blue-100 uppercase tracking-wide mb-2">Cost Saved</p>
              <p className="text-4xl font-bold text-white mb-1">
                {formatCurrency(summary.estimated_cost_saved_usd)}
              </p>
              <p className="text-sm text-blue-100">in API expenses</p>
            </div>
            <div className="bg-white/10 backdrop-blur-sm rounded-xl p-6 border border-white/20">
              <p className="text-sm font-semibold text-green-100 uppercase tracking-wide mb-2">Speed Boost</p>
              <p className="text-4xl font-bold text-white mb-1">
                {latency.speedup_factor.toFixed(0)}x
              </p>
              <p className="text-sm text-green-100">faster than LLM calls</p>
            </div>
            <div className="bg-white/10 backdrop-blur-sm rounded-xl p-6 border border-white/20">
              <p className="text-sm font-semibold text-purple-100 uppercase tracking-wide mb-2">Calls Avoided</p>
              <p className="text-4xl font-bold text-white mb-1">
                {summary.calls_avoided.toLocaleString()}
              </p>
              <p className="text-sm text-purple-100">API requests saved</p>
            </div>
          </div>
        </div>
        {/* Decorative elements */}
        <div className="absolute top-0 right-0 w-64 h-64 bg-white/5 rounded-full blur-3xl"></div>
        <div className="absolute bottom-0 left-0 w-48 h-48 bg-purple-500/20 rounded-full blur-2xl"></div>
      </div>
    </div>
  );
}
