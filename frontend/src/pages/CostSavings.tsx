/**
 * Cost Savings Page
 *
 * Financial impact analysis and cost optimization metrics
 */
import { useQuery } from '@tanstack/react-query';
import { DollarSign, TrendingDown, Coins, Percent } from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import {
  getSummary,
  getProviderUsage,
  MetricsSummary,
  ProviderUsage,
} from '../api/metricsApi';
import MetricCard from '../components/MetricCard';

export default function CostSavings() {
  // Fetch summary metrics
  const { data: summary, isLoading } = useQuery<MetricsSummary>({
    queryKey: ['summary', '24h'],
    queryFn: () => getSummary('24h'),
    refetchInterval: 30000,
  });

  // Fetch provider usage
  const { data: providerUsage } = useQuery<ProviderUsage>({
    queryKey: ['provider-usage', '24h'],
    queryFn: () => getProviderUsage('24h'),
    refetchInterval: 60000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading cost metrics...</p>
        </div>
      </div>
    );
  }

  if (!summary) return null;

  // Format currency
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  // Calculate total cost if no cache
  const totalCostWithoutCache = summary.estimated_cost_saved_usd +
    (providerUsage ? Object.values(providerUsage).reduce((sum, p) => sum + p.total_cost_usd, 0) : 0);

  // Calculate cache efficiency
  const cacheEfficiency = summary.total_requests > 0
    ? (summary.estimated_cost_saved_usd / totalCostWithoutCache) * 100
    : 0;

  // Prepare provider cost breakdown
  const providerCostData = providerUsage
    ? Object.entries(providerUsage).map(([provider, data]) => ({
        provider,
        actual_cost: data.total_cost_usd,
        calls: data.total_calls,
        tokens: data.total_tokens,
      }))
    : [];

  // Prepare model-level breakdown (for the first provider)
  const modelBreakdownData = providerUsage
    ? Object.entries(providerUsage)[0]?.[1]?.models
      ? Object.entries(Object.entries(providerUsage)[0][1].models).map(([model, data]) => ({
          model,
          cost: data.cost_usd,
          calls: data.calls,
          tokens: data.tokens,
        }))
      : []
    : [];

  // Prepare cost comparison data
  const costComparisonData = [
    {
      scenario: 'Without Cache',
      cost: totalCostWithoutCache,
      color: '#ef4444',
    },
    {
      scenario: 'With Cache',
      cost: totalCostWithoutCache - summary.estimated_cost_saved_usd,
      color: '#10b981',
    },
  ];

  // Calculate projected monthly savings
  const projectedMonthlySavings = summary.estimated_cost_saved_usd * 30;
  const projectedYearlySavings = summary.estimated_cost_saved_usd * 365;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Cost Savings</h1>
        <p className="text-gray-600 mt-1">
          Financial impact and ROI analysis
        </p>
      </div>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <MetricCard
          icon={DollarSign}
          label="Cost Saved (24h)"
          value={formatCurrency(summary.estimated_cost_saved_usd)}
          subtitle={`${summary.calls_avoided.toLocaleString()} calls avoided`}
          color="green"
        />

        <MetricCard
          icon={TrendingDown}
          label="Cache Efficiency"
          value={`${cacheEfficiency.toFixed(1)}%`}
          subtitle="Cost reduction percentage"
          color="blue"
        />

        <MetricCard
          icon={Coins}
          label="Projected Monthly"
          value={formatCurrency(projectedMonthlySavings)}
          subtitle="Based on 24h average"
          color="purple"
        />

        <MetricCard
          icon={Percent}
          label="Projected Yearly"
          value={formatCurrency(projectedYearlySavings)}
          subtitle="Estimated annual savings"
          color="orange"
        />
      </div>

      {/* Cost Comparison */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Cost Comparison: With vs Without Cache
        </h2>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={costComparisonData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="scenario" />
            <YAxis label={{ value: 'Cost (USD)', angle: -90, position: 'insideLeft' }} />
            <Tooltip formatter={(value) => formatCurrency(Number(value))} />
            <Bar dataKey="cost" name="Cost (USD)">
              {costComparisonData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Provider Cost Breakdown */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Provider Cost Breakdown
          </h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={providerCostData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="provider" />
              <YAxis label={{ value: 'Cost (USD)', angle: -90, position: 'insideLeft' }} />
              <Tooltip formatter={(value) => formatCurrency(Number(value))} />
              <Legend />
              <Bar dataKey="actual_cost" fill="#3b82f6" name="Actual Cost (USD)" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Model-Level Cost Breakdown */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Model-Level Cost Breakdown
          </h2>
          {modelBreakdownData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={modelBreakdownData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ model, cost, percent }) =>
                    `${model}: ${formatCurrency(cost)} (${(percent * 100).toFixed(0)}%)`
                  }
                  outerRadius={100}
                  fill="#8884d8"
                  dataKey="cost"
                >
                  {modelBreakdownData.map((_, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444'][index % 5]}
                    />
                  ))}
                </Pie>
                <Tooltip formatter={(value) => formatCurrency(Number(value))} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-64 text-gray-500">
              No model data available
            </div>
          )}
        </div>
      </div>

      {/* Provider Statistics Table */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Provider Statistics
        </h2>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Provider
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Total Calls
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Total Tokens
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actual Cost
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {providerCostData.map((provider) => (
                <tr key={provider.provider} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded font-medium">
                      {provider.provider}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {provider.calls.toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {provider.tokens.toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-green-600">
                    {formatCurrency(provider.actual_cost)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ROI Summary */}
      <div className="bg-gradient-to-r from-green-50 to-blue-50 rounded-lg p-6 border border-green-100">
        <div className="flex items-center mb-4">
          <DollarSign className="w-6 h-6 text-green-600 mr-2" />
          <h2 className="text-lg font-semibold text-gray-900">Return on Investment</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-3xl font-bold text-green-600">
              {formatCurrency(summary.estimated_cost_saved_usd)}
            </p>
            <p className="text-sm text-gray-600 mt-1">Saved (24h)</p>
          </div>
          <div>
            <p className="text-3xl font-bold text-blue-600">
              {formatCurrency(projectedMonthlySavings)}
            </p>
            <p className="text-sm text-gray-600 mt-1">Projected Monthly</p>
          </div>
          <div>
            <p className="text-3xl font-bold text-purple-600">
              {formatCurrency(projectedYearlySavings)}
            </p>
            <p className="text-sm text-gray-600 mt-1">Projected Yearly</p>
          </div>
        </div>
        <div className="mt-6 text-center">
          <p className="text-gray-700">
            DriftCache has reduced your LLM costs by{' '}
            <span className="font-bold text-green-600">{cacheEfficiency.toFixed(1)}%</span>,
            avoiding{' '}
            <span className="font-bold text-blue-600">
              {summary.calls_avoided.toLocaleString()}
            </span>{' '}
            expensive API calls in the last 24 hours.
          </p>
        </div>
      </div>
    </div>
  );
}
