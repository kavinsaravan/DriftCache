import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import Applications from './Applications';
import Layout from '../components/Layout';
import { WorkspaceProvider } from '../context/WorkspaceProvider';
import { workspaceApi } from '../api/workspaceApi';
vi.mock('../api/workspaceApi', async importOriginal => {
  const original = await importOriginal<typeof import('../api/workspaceApi')>();
  return {...original, workspaceApi: {get: vi.fn(), post: vi.fn(), delete: vi.fn()}};
});
const workspace = {id: 'p1', name: 'Support bot', tenant_id: 'project:p1'};
const configuration = {default_model: 'claude-sonnet-5-5', default_provider: 'anthropic', configured: true, available_models: ['claude-sonnet-5-5']};
afterEach(cleanup);
beforeEach(() => {
  sessionStorage.clear(); vi.clearAllMocks();
  vi.mocked(workspaceApi.get).mockImplementation(async path => ({data: path === '/current' ? workspace : path === '/integration' ? configuration : []}));
});
function show() {
  return render(<QueryClientProvider client={new QueryClient({defaultOptions: {queries: {retry: false}}})}>
    <WorkspaceProvider><MemoryRouter initialEntries={['/applications']}><Routes>
      <Route element={<Layout />}><Route path="/applications" element={<Applications />} /></Route>
    </Routes></MemoryRouter></WorkspaceProvider>
  </QueryClientProvider>);
}
it('creates a workspace without signup and preserves the one-time key until saved', async () => {
  vi.mocked(workspaceApi.post).mockResolvedValue({data: {project_id: 'p1', project_name: workspace.name, tenant_id: workspace.tenant_id, api_key: 'dc_live_shown_once'}});
  show();
  expect(screen.queryByLabelText('Email')).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Password')).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Workspace name'), {target: {value: workspace.name}});
  fireEvent.click(screen.getByRole('button', {name: 'Create workspace'}));
  await screen.findByText('dc_live_shown_once');
  expect(sessionStorage.getItem('driftcache.metrics-key')).toBeNull();
  expect(workspaceApi.post).toHaveBeenCalledWith('', {name: workspace.name, key_name: 'default'});
  fireEvent.click(screen.getByRole('button', {name: 'I saved it — open workspace'}));
  const example = await screen.findByText(/DRIFTCACHE_API_KEY/, {selector: 'pre'});
  expect(example).toHaveTextContent('claude-sonnet-5-5');
  expect(example).not.toHaveTextContent('gpt-4o-mini');
  expect(sessionStorage.getItem('driftcache.metrics-key')).toBe('dc_live_shown_once');
  expect(screen.queryByText('dc_live_shown_once')).not.toBeInTheDocument();
});
it('connects with an existing key and clears the connection on disconnect', async () => {
  sessionStorage.setItem('driftcache.account-session', 'old_session');
  show();
  fireEvent.change(screen.getByLabelText('Workspace API key'), {target: {value: 'dc_live_existing'}});
  fireEvent.click(screen.getByRole('button', {name: 'Connect workspace'}));
  await screen.findByRole('heading', {name: workspace.name});
  expect(workspaceApi.get).toHaveBeenCalledWith('/current', {headers: {Authorization: 'Bearer dc_live_existing'}});
  expect(sessionStorage.getItem('driftcache.account-session')).toBeNull();
  fireEvent.click(screen.getByRole('button', {name: 'Disconnect'}));
  await screen.findByRole('button', {name: 'Create workspace'});
  expect(sessionStorage.getItem('driftcache.metrics-key')).toBeNull();
  expect(screen.queryByRole('heading', {name: 'Workspace keys'})).not.toBeInTheDocument();
});
it('does not store a rejected key', async () => {
  vi.mocked(workspaceApi.get).mockRejectedValue(new Error('offline'));
  show();
  fireEvent.change(screen.getByLabelText('Workspace API key'), {target: {value: 'bad-key'}});
  fireEvent.click(screen.getByRole('button', {name: 'Connect workspace'}));
  await screen.findByRole('alert');
  expect(sessionStorage.getItem('driftcache.metrics-key')).toBeNull();
});
async function showConnected(config: unknown, failure = false) {
  sessionStorage.setItem('driftcache.metrics-key', 'dc_live_existing');
  vi.mocked(workspaceApi.get).mockImplementation(async path => {
    if (path === '/current') return {data: workspace};
    if (path === '/integration') {
      if (failure) throw new Error('offline');
      return {data: config};
    }
    return {data: []};
  });
  show();
  await screen.findByRole('heading', {name: 'Connect your AI application'});
}
it('uses the configured OpenAI model instead of assuming Claude', async () => {
  await showConnected({...configuration, default_model: 'gpt-custom', default_provider: 'openai'});
  expect(await screen.findByText(/DRIFTCACHE_API_KEY/, {selector: 'pre'})).toHaveTextContent('gpt-custom');
});
it('shows setup guidance without a configured provider', async () => {
  await showConnected({...configuration, configured: false});
  await screen.findByText(/default model has no configured provider/);
  expect(screen.queryByText(/DRIFTCACHE_API_KEY/, {selector: 'pre'})).not.toBeInTheDocument();
});
it('offers retry if connection settings cannot be loaded', async () => {
  await showConnected(null, true);
  await screen.findByRole('button', {name: 'Retry connection settings'});
  expect(screen.queryByText(/DRIFTCACHE_API_KEY/, {selector: 'pre'})).not.toBeInTheDocument();
});
it('shows a rotation key only until dismissed', async () => {
  await showConnected(configuration);
  vi.mocked(workspaceApi.post).mockResolvedValue({data: {project_id: workspace.id, api_key: 'dc_live_rotated'}});
  fireEvent.click(screen.getByRole('button', {name: 'Create key'}));
  await screen.findByText('dc_live_rotated');
  fireEvent.click(screen.getByRole('button', {name: 'I saved it — dismiss'}));
  await waitFor(() => expect(screen.queryByText('dc_live_rotated')).not.toBeInTheDocument());
});
