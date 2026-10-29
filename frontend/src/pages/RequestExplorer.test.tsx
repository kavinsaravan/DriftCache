import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import RequestExplorer from './RequestExplorer';
import { getRequestHistory } from '../api/metricsApi';
vi.mock('../api/metricsApi', () => ({
  getRequestHistory: vi.fn(), getMetricsError: () => 'Unable to load requests',
}));
afterEach(() => { cleanup(); vi.resetAllMocks(); });
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


function event(id: number, prompt: string) {
  return {event_id: id, request_id: String(id), prompt, model: 'claude-test', status: 'HIT',
    similarity: 1, latency_ms: 10, created_at: '2026-10-28T07:00:00Z'};
}

it('shows refresh progress and replaces the table with newly fetched requests', async () => {
  let finish!: (value: {total: number; items: ReturnType<typeof event>[]}) => void;
  vi.mocked(getRequestHistory).mockResolvedValueOnce({total: 1, items: [event(1, 'old request')]})
    .mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  show();
  await screen.findByText('old request');
  fireEvent.click(screen.getByRole('button', {name: 'Refresh'}));
  expect(await screen.findByRole('button', {name: 'Refreshing…'})).toBeDisabled();
  expect(screen.getByText('old request')).toBeInTheDocument();
  finish({total: 2, items: [event(2, 'new request'), event(1, 'old request')]});
  await screen.findByText('new request');
  expect(screen.getByRole('button', {name: 'Refresh'})).toBeEnabled();
  expect(screen.getByRole('status')).toHaveTextContent('Last updated');
  expect(screen.getByText(/2 total decisions/)).toBeInTheDocument();
});

it('keeps loaded rows and lets the user retry a failed refresh', async () => {
  vi.mocked(getRequestHistory).mockResolvedValueOnce({total: 1, items: [event(1, 'existing request')]})
    .mockRejectedValueOnce(new Error('offline'))
    .mockResolvedValueOnce({total: 1, items: [event(2, 'recovered request')]});
  show();
  await screen.findByText('existing request');
  fireEvent.click(screen.getByRole('button', {name: 'Refresh'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Showing previously loaded requests');
  expect(screen.getByText('existing request')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name: 'Refresh'}));
  await screen.findByText('recovered request');
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

it('refreshes the newest page when the user is viewing older requests', async () => {
  vi.mocked(getRequestHistory).mockResolvedValueOnce({total: 101, items: [event(2, 'first page request')]})
    .mockResolvedValueOnce({total: 101, items: [event(1, 'older page request')]})
    .mockResolvedValueOnce({total: 102, items: [event(3, 'latest request')]});
  show();
  await screen.findByText('first page request');
  fireEvent.click(screen.getByRole('button', {name: 'Next'}));
  await screen.findByText('older page request');
  fireEvent.click(screen.getByRole('button', {name: 'Refresh'}));
  await screen.findByText('latest request');
  expect(getRequestHistory).toHaveBeenLastCalledWith(0, 100);
  expect(screen.getByRole('button', {name: 'Previous'})).toBeDisabled();
});
