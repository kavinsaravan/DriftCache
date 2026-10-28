import axios from 'axios';

export const API_BASE_URL = (import.meta.env.VITE_API_URL || '/api/v1').replace(/\/$/, '');
const KEY_STORAGE = 'driftcache.metrics-key';
export const getWorkspaceKey = () => sessionStorage.getItem(KEY_STORAGE) || '';
export const saveWorkspaceKey = (key: string) => key.trim()
  ? sessionStorage.setItem(KEY_STORAGE, key.trim()) : sessionStorage.removeItem(KEY_STORAGE);
export interface Workspace { id: string; name: string; tenant_id: string }
export interface WorkspaceKey { id: string; name: string; key_prefix: string; is_active: boolean; created_at: string }
export interface NewKey { api_key: string; project_id: string }
export interface CreatedWorkspace extends NewKey { project_name: string; tenant_id: string }
export interface IntegrationConfiguration {
  default_model: string; default_provider: string | null; configured: boolean; available_models: string[];
}
export const workspaceApi = axios.create({baseURL: `${API_BASE_URL}/workspaces`});
workspaceApi.interceptors.request.use(config => {
  const key = getWorkspaceKey();
  if (key && !config.headers.has('Authorization')) config.headers.set('Authorization', `Bearer ${key}`);
  return config;
});
export function workspaceError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (error.response?.status === 422) return 'Enter a workspace or key name between 1 and 100 characters.';
  }
  return 'Unable to reach the API. Please try again.';
}
