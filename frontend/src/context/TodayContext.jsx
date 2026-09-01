import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '@/lib/api';

const TodayContext = createContext(null);

export function TodayProvider({ children, navigateOnLoad = false }) {
  const navigate = useNavigate();
  const [today, setToday] = useState(null);
  const [academics, setAcademics] = useState({ courses: [], presets: [], name: '' });
  const [googleState, setGoogleState] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const genRef = useRef(0);

  const refresh = useCallback(async (opts = {}) => {
    const gen = ++genRef.current;
    try {
      const t = await api('/api/today');
      if (gen !== genRef.current) return t;
      setToday(t);
      setError(null);
      if (navigateOnLoad || opts.nav) {
        if (t.halt) {
          navigate('/halt');
          return t;
        }
        if (t.needs_recap) {
          navigate('/recap');
          return t;
        }
        if (t.needs_gate) {
          navigate('/gate');
          return t;
        }
      }
      try {
        const google = await api('/api/integrations/google');
        if (gen === genRef.current) setGoogleState(google);
      } catch {
        /* optional */
      }
      return t;
    } catch (err) {
      if (gen === genRef.current) setError(err);
      throw err;
    } finally {
      if (gen === genRef.current) setLoading(false);
    }
  }, [navigate, navigateOnLoad]);

  useEffect(() => {
    refresh({ nav: navigateOnLoad }).catch(() => {});
    api('/api/academics/current')
      .then(setAcademics)
      .catch(() => {});
    const id = setInterval(() => {
      if (!document.hidden) refresh().catch(() => {});
    }, 60000);
    const onVis = () => {
      if (!document.hidden) refresh().catch(() => {});
    };
    document.addEventListener('visibilitychange', onVis);
    return () => {
      clearInterval(id);
      document.removeEventListener('visibilitychange', onVis);
    };
  }, [refresh, navigateOnLoad]);

  return (
    <TodayContext.Provider value={{ today, academics, googleState, setGoogleState, error, loading, refresh }}>
      {children}
    </TodayContext.Provider>
  );
}

export function useToday() {
  const ctx = useContext(TodayContext);
  if (!ctx) throw new Error('useToday must be used within TodayProvider');
  return ctx;
}
