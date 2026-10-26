import { useAccount } from '../context/AccountContext';
import { accountError } from '../api/accountApi';
import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { getMetricsKey, setMetricsKey, USE_MOCK_DATA } from '../api/metricsApi';
/**
 * Layout Component
 *
 * Main application layout with navigation
 */
import { Link, Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Database,
} from 'lucide-react';

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Requests', href: '/requests', icon: Database },
  { name: 'Applications', href: '/applications', icon: Database },
];

export default function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const account = useAccount();
  const [accountFailure, setAccountFailure] = useState('');
  const queryClient = useQueryClient();
  const [key, setKey] = useState(getMetricsKey);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    if (account?.signedIn) { setKey(''); setSaved(false); }
  }, [account?.signedIn]);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Sidebar */}
      <div className="fixed inset-y-0 left-0 w-64 bg-white border-r border-gray-200">
        {/* Logo */}
        <div className="flex items-center h-16 px-6 border-b border-gray-200">
          <div className="flex items-center">
            <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-purple-600 rounded-lg"></div>
            <span className="ml-3 text-xl font-bold text-gray-900">DriftCache</span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="p-4 space-y-1">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href;
            return (
              <Link
                key={item.name}
                to={item.href}
                className={`flex items-center px-4 py-3 text-sm font-medium rounded-lg transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-600'
                    : 'text-gray-700 hover:bg-gray-50 hover:text-gray-900'
                }`}
              >
                <item.icon className="w-5 h-5 mr-3" />
                {item.name}
              </Link>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-200">
          <div className="text-xs text-gray-500">
            <p className="font-medium">Adaptive Semantic Caching</p>
            <p className="mt-1">Analytics Dashboard</p>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="pl-64">
        {/* Top Bar */}
        <div className="bg-white border-b border-gray-200 px-8 py-4">
          {USE_MOCK_DATA && account?.signedIn && <p className="text-amber-800 mb-3">Demo mode — showing sample data.</p>}
          {account?.signedIn ? <div className="flex items-center gap-4">
            <span className="text-sm text-gray-600">{account.user?.email || 'Account'}</span>
            <label className="text-sm">Application <select aria-label="Application" className="border rounded px-3 py-2 ml-2" value={account.projectId} onChange={e => account.selectProject(e.target.value)}>
              {!account.projects.length && <option value="">Create an application</option>}
              {account.projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}
            </select></label>
            <button className="text-blue-700" onClick={() => { setAccountFailure(''); void account.logout().catch(error => setAccountFailure(accountError(error))); }}>Sign out</button>
            {accountFailure && <p role="alert" className="text-red-700">{accountFailure}</p>}
          </div> : USE_MOCK_DATA ? <p className="text-amber-800">Demo mode — showing sample data.</p> : (
            <details open={location.pathname !== '/applications'}>
            <summary className="text-sm text-gray-600 cursor-pointer">Use an existing API key</summary>
            <form className="flex items-center gap-3 mt-3" onSubmit={(event) => {
              event.preventDefault();
              setMetricsKey(key);
              setSaved(true);
              void queryClient.resetQueries();
              if (key.trim()) navigate('/');
            }}>
              <label htmlFor="metrics-key" className="text-sm">Metrics or project API key</label>
              <input id="metrics-key" type="password" autoComplete="off" value={key}
                onChange={(event) => { setKey(event.target.value); setSaved(false); }}
                className="border rounded px-3 py-2" />
              <button type="submit" className="bg-blue-600 text-white rounded px-3 py-2">Apply key</button>
              <span className="text-sm text-gray-500" role="status">{saved ? 'Key applied.' : 'Stored for this tab only.'}</span>
            </form>
            </details>
          )}
        </div>

        {/* Page Content */}
        <main className="p-8">
          {account?.loading ? <p>Loading your account…</p> :
            location.pathname !== '/applications' && !USE_MOCK_DATA &&
            ((account?.signedIn && !account.projectId) || (!account?.signedIn && !getMetricsKey())) ?
            <Navigate to="/applications" replace /> :
            <Outlet key={account?.user?.id || 'key-access'} />}

        </main>
      </div>
    </div>
  );
}
