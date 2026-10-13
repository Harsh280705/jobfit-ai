import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './layouts/Layout';
import Dashboard from './pages/Dashboard';
import NewAnalysis from './pages/NewAnalysis';
import Results from './pages/Results';
import RequirementDetail from './pages/RequirementDetail';
import Research from './pages/Research';

const qc = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/new" element={<NewAnalysis />} />
            <Route path="/results/:id" element={<Results />} />
            <Route path="/requirements/:analysisId/:reqId" element={<RequirementDetail />} />
            {/* Retained for compatibility; intentionally unreachable via navigation. */}
            <Route path="/research" element={<Research />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
