import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import RequestExplorer from './RequestExplorer';
import { getRequestHistory } from '../api/metricsApi';
vi.mock('../api/metricsApi', () => ({
  getRequestHistory: vi.fn(), getMetricsError: () => 'Unable to load requests',
}));
afterEach(cleanup);
function show() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><RequestExplorer /></QueryClientProvider>);
}
it('renders real decisions and filters misses without labeling errors as misses', async () => {
  vi.mocked(getRequestHistory).mockResolvedValue({total: 3, items: ['HIT', 'THRESHOLD_NOT_MET', 'ERROR'].map((status, index) => ({
    event_id: index, request_id: `${index}`, prompt: `question-${status}`, model: 'm', status,
    similarity: .4, latency_ms: 5, created_at: '2026-10-21T12:00:00Z',
  }))});
  show();
  await screen.findByText('question-THRESHOLD_NOT_MET');
  fireEvent.change(screen.getByLabelText('Cache status'), { target: { value: 'miss' } });
  expect(screen.getByText('question-THRESHOLD_NOT_MET')).toBeInTheDocument();
  expect(screen.queryByText('question-HIT')).not.toBeInTheDocument();
  expect(screen.queryByText('question-ERROR')).not.toBeInTheDocument();
});
it('shows an error when history cannot be fetched', async () => {
  vi.mocked(getRequestHistory).mockRejectedValue(new Error('offline'));
  show();
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Unable to load requests'));
});
