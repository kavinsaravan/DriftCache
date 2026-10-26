import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import Applications from './Applications';
import { AccountProvider } from '../context/AccountContext';
import { accountApi } from '../api/accountApi';
vi.mock('../api/accountApi', async importOriginal => {
  const original = await importOriginal<typeof import('../api/accountApi')>();
  return { ...original, accountApi: {get: vi.fn(), post: vi.fn(), delete: vi.fn()} };
});
afterEach(cleanup);
beforeEach(() => { sessionStorage.clear(); vi.clearAllMocks(); });
function show() {
  return render(<QueryClientProvider client={new QueryClient({defaultOptions: {queries: {retry: false}}})}>
    <MemoryRouter><AccountProvider><Applications /></AccountProvider></MemoryRouter>
  </QueryClientProvider>);
}
it('lets a new user sign up and create an application with a one-time key', async () => {
  const user = {id: 'u1', email: 'alice@example.com'};
  const projects: {id: string; name: string; tenant_id: string}[] = [];
  vi.mocked(accountApi.get).mockImplementation(async path => ({data: path === '/me' ? user : path === '/projects' ? [...projects] : []}));
  vi.mocked(accountApi.post).mockImplementation(async path => {
    if (path === '/register') return {data: {token: 'dc_session_test', user}};
    projects.push({id: 'p1', name: 'Support bot', tenant_id: 'project:p1'});
    return {data: {project_id: 'p1', api_key: 'dc_live_shown_once'}};
  });
  show();
  fireEvent.change(screen.getByLabelText('Email'), {target: {value: user.email}});
  fireEvent.change(screen.getByLabelText('Password'), {target: {value: 'a-long-password-123'}});
  fireEvent.click(screen.getByRole('button', {name: 'Create account'}));
  await screen.findByRole('heading', {name: 'Your applications'});
  expect(accountApi.post).toHaveBeenCalledWith('/register', {email: user.email, password: 'a-long-password-123'});
  fireEvent.change(screen.getByLabelText('Application name'), {target: {value: 'Support bot'}});
  fireEvent.click(screen.getByRole('button', {name: 'Create application'}));
  await screen.findByText('dc_live_shown_once');
  await waitFor(() => expect(sessionStorage.getItem('driftcache.account-project')).toBe('p1'));
  expect(screen.getByText(/DRIFTCACHE_API_KEY/, {selector: 'pre'})).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name: 'I saved it — dismiss'}));
  expect(screen.queryByText('dc_live_shown_once')).not.toBeInTheDocument();
});
it('shows a failed login and does not create a session', async () => {
  vi.mocked(accountApi.post).mockRejectedValue(new Error('offline'));
  show();
  fireEvent.click(screen.getByRole('button', {name: 'Already have an account? Sign in'}));
  fireEvent.change(screen.getByLabelText('Email'), {target: {value: 'a@example.com'}});
  fireEvent.change(screen.getByLabelText('Password'), {target: {value: 'a-long-password-123'}});
  fireEvent.click(screen.getByRole('button', {name: 'Sign in'}));
  await screen.findByRole('alert');
  expect(sessionStorage.getItem('driftcache.account-session')).toBeNull();
  expect(screen.queryByRole('heading', {name: 'Your applications'})).not.toBeInTheDocument();
});
