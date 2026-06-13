/**
 * Request Explorer Page
 *
 * Browse and search through recent cache requests and events
 */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, Filter, Download, RefreshCw } from 'lucide-react';
import { getTopCachedPrompts, TopCachedPrompt } from '../api/metricsApi';

type CacheStatusFilter = 'all' | 'hit' | 'miss';

export default function RequestExplorer() {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<CacheStatusFilter>('all');

  // Fetch cached prompts (as a proxy for request history)
  const { data: requests, isLoading, refetch } = useQuery<TopCachedPrompt[]>({
    queryKey: ['request-explorer', 100],
    queryFn: () => getTopCachedPrompts(100, '24h'),
    refetchInterval: 30000,
  });

  // Filter requests based on search and status
  const filteredRequests = requests?.filter((request) => {
    const matchesSearch =
      searchQuery === '' ||
      request.prompt.toLowerCase().includes(searchQuery.toLowerCase()) ||
      request.response.toLowerCase().includes(searchQuery.toLowerCase()) ||
      request.model.toLowerCase().includes(searchQuery.toLowerCase());

    // Since we're using cached prompts, all have hits
    // In a real implementation, this would filter by actual cache_status
    const matchesStatus = statusFilter === 'all' || statusFilter === 'hit';

    return matchesSearch && matchesStatus;
  });

  // Export to CSV
  const handleExport = () => {
    if (!filteredRequests) return;

    const headers = ['Timestamp', 'Prompt', 'Response', 'Model', 'Hit Count', 'Cache ID'];
    const rows = filteredRequests.map((req) => [
      new Date(req.created_at).toISOString(),
      `"${req.prompt.replace(/"/g, '""')}"`,
      `"${req.response.replace(/"/g, '""')}"`,
      req.model,
      req.hit_count.toString(),
      req.cache_id,
    ]);

    const csv = [headers.join(','), ...rows.map((row) => row.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `driftcache-requests-${new Date().toISOString()}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading requests...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Request Explorer</h1>
          <p className="text-gray-600 mt-1">
            Browse and search through recent cache requests
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => refetch()}
            className="px-4 py-2 bg-white border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 flex items-center"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </button>
          <button
            onClick={handleExport}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 flex items-center"
          >
            <Download className="w-4 h-4 mr-2" />
            Export CSV
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Search */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Search
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search prompts, responses, or models..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Status Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Cache Status
            </label>
            <div className="relative">
              <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as CacheStatusFilter)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 appearance-none"
              >
                <option value="all">All Requests</option>
                <option value="hit">Cache Hits</option>
                <option value="miss">Cache Misses</option>
              </select>
            </div>
          </div>
        </div>

        {/* Results Count */}
        <div className="mt-4 text-sm text-gray-600">
          Showing {filteredRequests?.length || 0} of {requests?.length || 0} requests
        </div>
      </div>

      {/* Request Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Timestamp
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Prompt
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Response
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Model
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Hit Count
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredRequests?.map((request, index) => (
                <tr key={`${request.cache_id}-${index}`} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(request.created_at).toLocaleString()}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900 max-w-md">
                    <div className="truncate" title={request.prompt}>
                      {request.prompt}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600 max-w-md">
                    <div className="truncate" title={request.response}>
                      {request.response}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded">
                      {request.model}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="px-2 py-1 text-xs bg-green-100 text-green-800 rounded font-medium">
                      HIT
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-bold text-blue-600">
                    {request.hit_count}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Empty State */}
        {filteredRequests && filteredRequests.length === 0 && (
          <div className="text-center py-12">
            <Search className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600">No requests found matching your criteria</p>
          </div>
        )}
      </div>

      {/* Stats Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Total Cached Entries</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">
                {requests?.length || 0}
              </p>
            </div>
            <div className="w-12 h-12 bg-blue-50 rounded-lg flex items-center justify-center">
              <Search className="w-6 h-6 text-blue-600" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Total Cache Hits</p>
              <p className="text-2xl font-bold text-green-600 mt-1">
                {requests?.reduce((sum, r) => sum + r.hit_count, 0) || 0}
              </p>
            </div>
            <div className="w-12 h-12 bg-green-50 rounded-lg flex items-center justify-center">
              <Filter className="w-6 h-6 text-green-600" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Average Hits per Entry</p>
              <p className="text-2xl font-bold text-purple-600 mt-1">
                {requests && requests.length > 0
                  ? (requests.reduce((sum, r) => sum + r.hit_count, 0) / requests.length).toFixed(1)
                  : '0'}
              </p>
            </div>
            <div className="w-12 h-12 bg-purple-50 rounded-lg flex items-center justify-center">
              <RefreshCw className="w-6 h-6 text-purple-600" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
