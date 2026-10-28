import { createContext, useContext } from 'react';
import { CreatedWorkspace, Workspace } from '../api/workspaceApi';

interface WorkspaceState {
  workspace: Workspace | null; loading: boolean; error: string;
  connect: (key: string) => Promise<void>;
  connectCreated: (created: CreatedWorkspace) => void;
  disconnect: () => void;
}
export const WorkspaceContext = createContext<WorkspaceState | null>(null);
export const useWorkspace = () => useContext(WorkspaceContext);
