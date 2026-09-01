import { lazy, Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { TodayProvider } from '@/context/TodayContext';
import { useToast } from '@/hooks/useToast';
import { loadTheme } from '@/lib/theme';

const Dashboard = lazy(() => import('@/pages/Dashboard'));
const GatePage = lazy(() => import('@/pages/Gate'));
const HaltPage = lazy(() => import('@/pages/Halt'));
const RecapPage = lazy(() => import('@/pages/Recap'));

loadTheme();

function Shell({ showToast, toast }) {
  return (
    <>
      <Suspense fallback={<div className="route-loading" role="status">Loading Timeless...</div>}>
        <Routes>
        <Route path="/" element={<Dashboard showToast={showToast} />} />
        <Route path="/gate" element={<GatePage showToast={showToast} />} />
        <Route path="/halt" element={<HaltPage showToast={showToast} />} />
        <Route path="/recap" element={<RecapPage showToast={showToast} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
      {toast ? <div className={`toast show${toast.tone ? ` toast-${toast.tone}` : ''}`}>{toast.message}</div> : null}
    </>
  );
}

export default function App() {
  const { toast, showToast } = useToast();

  return (
    <BrowserRouter>
      <TodayProvider navigateOnLoad={window.location.pathname === '/'}>
        <Shell showToast={showToast} toast={toast} />
      </TodayProvider>
    </BrowserRouter>
  );
}
