/**
 * Main Application Component
 *
 * Sets up routing and React Query
 */
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Applications from './pages/Applications';
import { AccountProvider } from './context/AccountContext';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import RequestExplorer from './pages/RequestExplorer';

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
      <AccountProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="applications" element={<Applications />} />
            <Route path="requests" element={<RequestExplorer />} />
          </Route>
        </Routes>
      </BrowserRouter>
      </AccountProvider>
    </QueryClientProvider>
  );
}

export default App;
