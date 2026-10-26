import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { accountApi, Application, getProject, getSession, saveProject, saveSession, User } from '../api/accountApi';
import { setMetricsKey } from '../api/metricsApi';

interface AccountState {
  user: User | null; loading: boolean; signedIn: boolean;
  projects: Application[]; projectId: string; projectsLoading: boolean; projectsError: unknown;
  selectProject: (id: string) => void; authenticate: (mode: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}
const AccountContext = createContext<AccountState | null>(null);
export const useAccount = () => useContext(AccountContext);

export function AccountProvider({ children }: { children: ReactNode }) {
  const client = useQueryClient();
  const [token, setToken] = useState(getSession);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(!!token);
  const [projectId, setProjectId] = useState(getProject);
  useEffect(() => {
    if (!token) return;
    let active = true;
    accountApi.get<User>('/me').then(({ data }) => { if (active) setUser(data); }).catch(error => {
      if (active && error.response?.status === 401) { saveSession(''); setToken(''); setUser(null); }
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token]);
  const projectsQuery = useQuery<Application[]>({
    queryKey: ['account-projects', user?.id], enabled: !!user,
    queryFn: async () => (await accountApi.get('/projects')).data,
  });
  const projects = projectsQuery.data || [];
  const selectProject = (id: string) => { saveProject(id); setProjectId(id); };
  useEffect(() => {
    if (projectsQuery.data && !projectsQuery.data.some(project => project.id === projectId)) {
      const id = projectsQuery.data[0]?.id || '';
      saveProject(id); setProjectId(id);
    }
  }, [projectsQuery.data, projectId]);
  const authenticate = async (mode: string, email: string, password: string) => {
    const { data } = await accountApi.post<{token: string; user: User}>(`/${mode}`, {email, password});
    client.clear(); setMetricsKey(''); saveProject(''); setProjectId('');
    saveSession(data.token); setToken(data.token); setUser(data.user);
  };
  const logout = async () => {
    await accountApi.post('/logout').catch(error => { if (error.response?.status !== 401) throw error; });
    saveSession(''); saveProject(''); setMetricsKey(''); setToken(''); setUser(null); setProjectId(''); client.clear();
  };
  return <AccountContext.Provider value={{ user, loading, signedIn: !!token, projects, projectId,
    projectsLoading: projectsQuery.isLoading, projectsError: projectsQuery.error, selectProject, authenticate, logout }}>
    {children}
  </AccountContext.Provider>;
}
