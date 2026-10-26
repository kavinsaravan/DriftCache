import axios from 'axios';

export const API_BASE_URL = (import.meta.env.VITE_API_URL || '/api/v1').replace(/\/$/, '');
const SESSION = 'driftcache.account-session';
const PROJECT = 'driftcache.account-project';
export const getSession = () => sessionStorage.getItem(SESSION) || '';
export const saveSession = (token: string) => token ? sessionStorage.setItem(SESSION, token) : sessionStorage.removeItem(SESSION);
export const getProject = () => sessionStorage.getItem(PROJECT) || '';
export const saveProject = (id: string) => id ? sessionStorage.setItem(PROJECT, id) : sessionStorage.removeItem(PROJECT);
export interface User { id: string; email: string }
export interface Application { id: string; name: string; tenant_id: string }
export interface ApplicationKey { id: string; name: string; key_prefix: string; is_active: boolean; created_at: string }
export interface NewKey { api_key: string; project_id: string }
export const accountApi = axios.create({ baseURL: `${API_BASE_URL}/account` });
accountApi.interceptors.request.use(config => {
  const token = getSession();
  if (token) config.headers.set('Authorization', `Bearer ${token}`);
  return config;
});
export function accountError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (error.response?.status === 422) return 'Use a valid email and a password of 12–256 characters.';
  }
  return 'Unable to reach the API. Please try again.';
}
