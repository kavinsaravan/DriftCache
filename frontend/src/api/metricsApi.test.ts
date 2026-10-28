import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { AxiosError } from 'axios';
beforeEach(() => {
  sessionStorage.clear();
  vi.resetModules();
  vi.stubEnv('VITE_USE_MOCK_DATA', 'false');
});
afterEach(() => { vi.unstubAllEnvs(); });
describe('metrics client', () => {
  it('sends the current tab credential and removes it when cleared', async () => {
    const { default: api, setMetricsKey } = await import('./metricsApi');
    const credentials: unknown[] = [];
    api.defaults.adapter = async (config) => {
      credentials.push(config.headers.get('Authorization'));
      return { data: {}, status: 200, statusText: 'OK', headers: {}, config };
    };
    setMetricsKey(' dc_live_test ');
    await api.get('/summary');
    setMetricsKey('');
    await api.get('/summary');
    expect(credentials).toEqual(['Bearer dc_live_test', undefined]);
  });
  it('uses the workspace key and never sends a legacy account session or tenant selector', async () => {
    const { default: api, setMetricsKey } = await import('./metricsApi');
    sessionStorage.setItem('driftcache.account-session', 'dc_session_old');
    sessionStorage.setItem('driftcache.account-project', 'someone-else');
    const sent: unknown[] = [];
    api.defaults.adapter = async config => {
      sent.push([config.headers.get('Authorization'), config.headers.get('X-Project-ID')]);
      return {data: {}, status: 200, statusText: 'OK', headers: {}, config};
    };
    setMetricsKey('dc_live_one'); await api.get('/dashboard');
    setMetricsKey('dc_live_two'); await api.get('/dashboard');
    setMetricsKey(''); await api.get('/dashboard');
    expect(sent).toEqual([
      ['Bearer dc_live_one', undefined], ['Bearer dc_live_two', undefined], [undefined, undefined],
    ]);
  });
  it('propagates auth and network failures instead of returning sample data', async () => {
    const { default: api, getDashboardData, getRequestHistory, getTimeSeries, getTopCachedPrompts, getMetricsError } = await import('./metricsApi');
    const failure = new AxiosError('Unauthorized', 'ERR_BAD_REQUEST', undefined, undefined, { status: 401 } as never);
    api.defaults.adapter = async () => { throw failure; };
    for (const call of [getDashboardData, getRequestHistory, () => getTimeSeries('hit_rate'), getTopCachedPrompts]) {
      await expect(call()).rejects.toBe(failure);
    }
    expect(getMetricsError(failure)).toContain('valid workspace key');
    api.defaults.adapter = async () => { throw new Error('offline'); };
    await expect(getDashboardData()).rejects.toThrow('offline');
  });
  it('uses samples only in explicitly enabled demo mode', async () => {
    vi.stubEnv('VITE_USE_MOCK_DATA', 'true');
    const { default: api, getRequestHistory } = await import('./metricsApi');
    const adapter = vi.fn();
    api.defaults.adapter = adapter;
    const data = await getRequestHistory();
    expect(data.items.some((item) => item.status === 'MISS')).toBe(true);
    expect(adapter).not.toHaveBeenCalled();
  });
});
