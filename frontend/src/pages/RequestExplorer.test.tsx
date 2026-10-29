import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import RequestExplorer from './RequestExplorer';
import { getRequestHistory, clearRequestHistory } from '../api/metricsApi';
vi.mock('../api/metricsApi', () => ({
  getRequestHistory: vi.fn(), clearRequestHistory: vi.fn(), USE_MOCK_DATA: false, getMetricsError: () => 'Unable to load requests',
}));
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.resetAllMocks(); });
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

it('confirms before clearing and leaves history untouched when cancelled', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(false);
  vi.mocked(getRequestHistory).mockResolvedValue({total: 1, items: [event(1, 'existing request')]});
  show();
  await screen.findByText('existing request');
  expect(screen.queryByRole('button', {name: 'Refresh'})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name: 'Clear requests'}));
  expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('cannot be undone'));
  expect(clearRequestHistory).not.toHaveBeenCalled();
  expect(screen.getByText('existing request')).toBeInTheDocument();
});

it('clears history and filters with visible progress and confirmation of success', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true);
  let finish!: (value: {deleted_requests: number}) => void;
  vi.mocked(getRequestHistory).mockResolvedValueOnce({total: 1, items: [event(1, 'old request')]})
    .mockResolvedValue({total: 0, items: []});
  vi.mocked(clearRequestHistory).mockImplementationOnce(() => new Promise(resolve => {finish = resolve;}));
  show();
  await screen.findByText('old request');
  fireEvent.change(screen.getByLabelText('Search this page'), {target: {value: 'old'}});
  fireEvent.change(screen.getByLabelText('Cache status'), {target: {value: 'hit'}});
  fireEvent.click(screen.getByRole('button', {name: 'Clear requests'}));
  expect(await screen.findByRole('button', {name: 'Clearing…'})).toBeDisabled();
  finish({deleted_requests: 1});
  await screen.findByText(/Cleared 1 request\./);
  expect(screen.queryByText('old request')).not.toBeInTheDocument();
  expect(screen.getByText(/0 total decisions/)).toBeInTheDocument();
  expect(screen.getByLabelText('Search this page')).toHaveValue('');
  expect(screen.getByLabelText('Cache status')).toHaveValue('all');
});

it('retains rows when clearing fails and allows another attempt', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true);
  vi.mocked(getRequestHistory).mockResolvedValue({total: 1, items: [event(1, 'existing request')]});
  vi.mocked(clearRequestHistory).mockRejectedValueOnce(new Error('offline'));
  show();
  await screen.findByText('existing request');
  fireEvent.click(screen.getByRole('button', {name: 'Clear requests'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Unable to clear requests');
  expect(screen.getByText('existing request')).toBeInTheDocument();
  expect(screen.getByRole('button', {name: 'Clear requests'})).toBeEnabled();
});

it('returns to the first page after clearing older requests', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true);
  vi.mocked(getRequestHistory).mockResolvedValueOnce({total: 101, items: [event(2, 'first page request')]})
    .mockResolvedValueOnce({total: 101, items: [event(1, 'older page request')]})
    .mockResolvedValue({total: 0, items: []});
  vi.mocked(clearRequestHistory).mockResolvedValue({deleted_requests: 101});
  show();
  await screen.findByText('first page request');
  fireEvent.click(screen.getByRole('button', {name: 'Next'}));
  await screen.findByText('older page request');
  fireEvent.click(screen.getByRole('button', {name: 'Clear requests'}));
  await screen.findByText(/Cleared 101 requests/);
  expect(screen.getByRole('button', {name: 'Previous'})).toBeDisabled();
  expect(screen.getByText(/0 total decisions/)).toBeInTheDocument();
});
