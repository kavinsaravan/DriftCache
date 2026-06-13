/**
 * Cache Analytics Page
 *
 * Detailed cache performance metrics and analysis
 */
import { useQuery } from '@tanstack/react-query';
import { BarChart3, TrendingUp, PieChart as PieChartIcon } from 'lucide-react';
import {
  AreaChart,
  Area,
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
  Legend,
} from 'recharts';
import {
  getTimeSeries,
  getSimilarityDistribution,
  getTopCachedPrompts,
  TimeSeriesDataPoint,
  SimilarityDistribution,
  TopCachedPrompt,
} from '../api/metricsApi';

export default function CacheAnalytics() {
  // Fetch cache hit rate over time
  const { data: hitRateData } = useQuery<TimeSeriesDataPoint[]>({
    queryKey: ['timeseries', 'hit_rate', '24h'],
    queryFn: () => getTimeSeries('hit_rate', '24h', '1h'),
    refetchInterval: 60000,
  });

  // Fetch similarity distribution
  const { data: similarityDist } = useQuery<SimilarityDistribution>({
    queryKey: ['similarity-distribution', '24h'],
    queryFn: () => getSimilarityDistribution('24h', 10),
    refetchInterval: 60000,
  });

  // Fetch top cached prompts
  const { data: topPrompts } = useQuery<TopCachedPrompt[]>({
    queryKey: ['top-cached-prompts', 20],
    queryFn: () => getTopCachedPrompts(20, '24h'),
    refetchInterval: 60000,
  });

  // Prepare similarity distribution data for chart
  const similarityData = similarityDist
    ? Object.entries(similarityDist).map(([range, count]) => ({
        range,
        count,
      }))
    : [];

  // Prepare hit rate time series data
  const hitRateChartData = hitRateData?.map((point) => ({
    time: new Date(point.timestamp).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    }),
    rate: (point.value * 100).toFixed(1),
  }));

  // Calculate hit rate categories for pie chart
  const calculateHitRateCategories = () => {
    if (!topPrompts) return [];

    const high = topPrompts.filter((p) => p.hit_count >= 10).length;
    const medium = topPrompts.filter((p) => p.hit_count >= 5 && p.hit_count < 10).length;
    const low = topPrompts.filter((p) => p.hit_count < 5).length;

    return [
      { name: 'High Usage (10+)', value: high, color: '#10b981' },
      { name: 'Medium Usage (5-9)', value: medium, color: '#f59e0b' },
      { name: 'Low Usage (<5)', value: low, color: '#ef4444' },
    ];
  };

  const usageCategories = calculateHitRateCategories();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Cache Analytics</h1>
        <p className="text-gray-600 mt-1">
          Deep dive into cache performance and patterns
        </p>
      </div>

      {/* Hit Rate Over Time */}
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
            <YAxis label={{ value: 'Hit Rate (%)', angle: -90, position: 'insideLeft' }} />
            <Tooltip />
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
        {/* Similarity Score Distribution */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center mb-4">
            <BarChart3 className="w-5 h-5 text-purple-600 mr-2" />
            <h2 className="text-lg font-semibold text-gray-900">
              Similarity Score Distribution
            </h2>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={similarityData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="range" angle={-45} textAnchor="end" height={80} />
              <YAxis />
              <Tooltip />
              <Bar dataKey="count" fill="#8b5cf6" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Cache Entry Usage Distribution */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center mb-4">
            <PieChartIcon className="w-5 h-5 text-green-600 mr-2" />
            <h2 className="text-lg font-semibold text-gray-900">
              Cache Entry Usage Distribution
            </h2>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={usageCategories}
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
                {usageCategories.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Top Cached Prompts Table */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          All Cached Prompts (Top 20)
        </h2>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Prompt
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Response (Preview)
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Model
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Hit Count
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Created
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {topPrompts?.map((prompt) => (
                <tr key={prompt.cache_id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-sm text-gray-900 max-w-xs truncate">
                    {prompt.prompt}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600 max-w-xs truncate">
                    {prompt.response}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded">
                      {prompt.model}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="text-lg font-bold text-blue-600">
                      {prompt.hit_count}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(prompt.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
