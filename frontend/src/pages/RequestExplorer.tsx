import { useWorkspace } from '../context/workspaceState';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getRequestHistory, getMetricsError } from '../api/metricsApi';
import LoadingSpinner from '../components/LoadingSpinner';
import { REFETCH_INTERVALS } from '../utils/constants';

const PAGE_SIZE = 100;
export default function RequestExplorer() {
  const scope = useWorkspace()?.workspace?.id || 'key-access';
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('all');
  const [offset, setOffset] = useState(0);
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['request-explorer', scope, offset],
    queryFn: () => getRequestHistory(offset, PAGE_SIZE),
    refetchInterval: REFETCH_INTERVALS.FAST,
  });
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
  if (error) return <div role="alert" className="bg-red-50 p-4">{getMetricsError(error)}</div>;
  return (
    <div className="space-y-6">
      <div className="flex justify-between">
        <div><h1 className="text-3xl font-bold">Request Explorer</h1>
          <p className="text-gray-600">Individual cache decisions from the last 24 hours, newest first.</p></div>
        <button onClick={exportCsv} className="border rounded px-4 py-2">Export this page</button>
        <button onClick={() => void refetch()} className="border rounded px-4 py-2">Refresh</button>
      </div>
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
      <div className="bg-white rounded overflow-x-auto">
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
