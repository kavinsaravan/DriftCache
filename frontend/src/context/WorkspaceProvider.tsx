import { ReactNode, useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { CreatedWorkspace, getWorkspaceKey, saveWorkspaceKey, Workspace, workspaceApi, workspaceError } from '../api/workspaceApi';
import { WorkspaceContext } from './workspaceState';

export function WorkspaceProvider({children}: {children: ReactNode}) {
  const client = useQueryClient();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [loading, setLoading] = useState(() => getWorkspaceKey().startsWith('dc_live_'));
  const [error, setError] = useState('');
  const generation = useRef(0);
  useEffect(() => {
    // Account sessions are no longer used by this UI; do not send them as keys.
    sessionStorage.removeItem('driftcache.account-session');
    sessionStorage.removeItem('driftcache.account-project');
    if (!getWorkspaceKey().startsWith('dc_live_')) return;
    let active = true;
    const initialGeneration = generation.current;
    workspaceApi.get<Workspace>('/current').then(({data}) => {
      if (active && generation.current === initialGeneration) setWorkspace(data);
    }).catch(err => {
      if (active && generation.current === initialGeneration) {
        if (err.response?.status === 401) saveWorkspaceKey('');
        setError(workspaceError(err));
      }
    }).finally(() => { if (active && generation.current === initialGeneration) setLoading(false); });
    return () => { active = false; };
  }, []);
  const activate = (key: string, data: Workspace) => {
    generation.current++; client.clear(); saveWorkspaceKey(key); setWorkspace(data); setLoading(false); setError('');
  };
  const connect = async (key: string) => {
    const {data} = await workspaceApi.get<Workspace>('/current', {headers: {Authorization: `Bearer ${key.trim()}`}});
    activate(key, data);
  };
  const connectCreated = (created: CreatedWorkspace) => activate(created.api_key,
    {id: created.project_id, name: created.project_name, tenant_id: created.tenant_id});
  const disconnect = () => {
    generation.current++; saveWorkspaceKey(''); setWorkspace(null); setLoading(false); setError(''); client.clear();
  };
  return <WorkspaceContext.Provider value={{workspace, loading, error, connect, connectCreated, disconnect}}>{children}</WorkspaceContext.Provider>;
}
