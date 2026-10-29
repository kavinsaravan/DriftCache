import { useWorkspace } from '../context/workspaceState';
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getRequestHistory, clearRequestHistory, getMetricsError, USE_MOCK_DATA } from '../api/metricsApi';
import { workspaceError } from '../api/workspaceApi';
import LoadingSpinner from '../components/LoadingSpinner';
import { REFETCH_INTERVALS } from '../utils/constants';

const PAGE_SIZE = 100;
export default function RequestExplorer() {
  const queryClient = useQueryClient();
  const scope = useWorkspace()?.workspace?.id || 'key-access';
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('all');
  const [offset, setOffset] = useState(0);
  const { data, isLoading, isFetching, dataUpdatedAt, error, refetch } = useQuery({
    queryKey: ['request-explorer', scope, offset],
    queryFn: () => getRequestHistory(offset, PAGE_SIZE),
    refetchInterval: REFETCH_INTERVALS.FAST,
  });
  const clearHistory = useMutation({
    mutationFn: clearRequestHistory,
    onMutate: () => queryClient.cancelQueries({queryKey: ['request-explorer', scope]}),
    onSuccess: async () => {
      setSearch(''); setStatus('all'); setOffset(0);
      queryClient.setQueriesData({queryKey: ['request-explorer', scope]}, {total: 0, items: []});
      await queryClient.invalidateQueries({queryKey: ['request-explorer', scope]});
    },
  });
  const clearRequests = () => {
    if (window.confirm('Permanently clear all request history for this workspace? Cached responses and dashboard metrics will be kept. This cannot be undone.')) {
      clearHistory.mutate();
    }
  };
  const items = (data?.items || []).filter((item) => {
    const matchesStatus = status === 'all' || (status === 'hit'
      ? item.status === 'HIT'
      : ['MISS', 'THRESHOLD_NOT_MET', 'EXPIRED', 'MODEL_MISMATCH', 'SYSTEM_MISMATCH'].includes(item.status));
    return matchesStatus && `${item.prompt} ${item.model} ${item.request_id}`.toLowerCase().includes(search.toLowerCase());
  });
  const exportCsv = () => {
    const rows = [
      ['Timestamp', 'Request ID', 'Prompt', 'Model', 'Status', 'Similarity', 'Lookup latency (ms)'],
      ...items.map((item) => [item.created_at, item.request_id, item.prompt, item.model, item.status, item.similarity ?? '', item.latency_ms ?? '']),
    ];
    const csv = rows.map((row) => row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(',')).join('\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'driftcache-request-decisions.csv';
    link.click();
    URL.revokeObjectURL(url);
  };
  if (isLoading) return <LoadingSpinner message="Loading requests..." />;
  return (
    <div className="space-y-6">
      <div className="flex justify-between">
        <div><h1 className="text-3xl font-bold">Request Explorer</h1>
          <p className="text-gray-600">Individual cache decisions from the last 24 hours, newest first.</p></div>
        <button onClick={exportCsv} className="border rounded px-4 py-2">Export this page</button>
        <button onClick={clearRequests} disabled={clearHistory.isPending || USE_MOCK_DATA} className="border rounded px-4 py-2 disabled:opacity-50">
          {clearHistory.isPending ? 'Clearing…' : 'Clear requests'}
        </button>
      </div>
      <p role="status" className="text-sm text-gray-500">
        {isFetching ? 'Fetching the latest requests…' : dataUpdatedAt ? `Last updated ${new Date(dataUpdatedAt).toLocaleTimeString()}. Request history updates automatically.` : 'No requests loaded yet.'}
      </p>
      {error && <div role="alert" className="bg-red-50 text-red-800 p-4 rounded">
        {getMetricsError(error)} {data ? 'Showing previously loaded requests.' : ''}
        <button className="underline ml-2" onClick={() => void refetch()}>Retry loading</button>
      </div>}
      {clearHistory.error && <div role="alert" className="bg-red-50 text-red-800 p-4 rounded">
        Unable to clear requests. {workspaceError(clearHistory.error)}
      </div>}
      {clearHistory.isSuccess && <p role="status" className="text-green-800">
        Cleared {clearHistory.data.deleted_requests} request{clearHistory.data.deleted_requests === 1 ? '' : 's'}. Cached responses and dashboard metrics were kept.
      </p>}
      <div className="flex gap-4 bg-white p-4 rounded">
        <label>Search this page
          <input className="border rounded px-3 py-2 ml-2" value={search} onChange={(event) => setSearch(event.target.value)} />
        </label>
        <label>Cache status
          <select className="border rounded px-3 py-2 ml-2" value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="all">All decisions</option><option value="hit">Cache hits</option><option value="miss">Cache misses</option>
          </select>
        </label>
      </div>
      <p>Showing {items.length} matching decisions on this page · {data?.total || 0} total decisions</p>
      <div className="bg-white rounded overflow-x-auto" aria-busy={isFetching}>
        <table className="min-w-full text-sm text-left">
          <thead><tr>{['Timestamp', 'Prompt', 'Model', 'Status', 'Similarity', 'Lookup latency'].map((title) => <th key={title} className="p-3">{title}</th>)}</tr></thead>
          <tbody>{items.map((item) => <tr key={item.event_id} className="border-t">
            <td className="p-3">{new Date(item.created_at).toLocaleString()}</td>
            <td className="p-3">{item.prompt}</td><td className="p-3">{item.model}</td>
            <td className="p-3">{item.status}</td>
            <td className="p-3">{item.similarity?.toFixed(3) ?? '—'}</td>
            <td className="p-3">{item.latency_ms == null ? '—' : `${item.latency_ms.toFixed(1)} ms`}</td>
          </tr>)}</tbody>
        </table>
        {!items.length && <p className="p-4">No requests found matching your criteria.</p>}
      </div>
      <div className="flex gap-4">
        <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Previous</button>
        <button disabled={offset + PAGE_SIZE >= (data?.total || 0)} onClick={() => setOffset(offset + PAGE_SIZE)}>Next</button>
      </div>
    </div>
  );
}
