/**
 * Main Application Component
 *
 * Sets up routing and React Query
 */
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import CacheAnalytics from './pages/CacheAnalytics';
import LatencyAnalytics from './pages/LatencyAnalytics';
import CostSavings from './pages/CostSavings';
import RequestExplorer from './pages/RequestExplorer';
import Settings from './pages/Settings';
import './App.css';

// Create React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30000, // 30 seconds
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="cache" element={<CacheAnalytics />} />
            <Route path="latency" element={<LatencyAnalytics />} />
            <Route path="cost" element={<CostSavings />} />
            <Route path="requests" element={<RequestExplorer />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
