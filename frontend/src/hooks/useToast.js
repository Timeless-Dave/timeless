import { useCallback, useEffect, useRef, useState } from 'react';

const VISIBLE_MS = 3200;

export function useToast() {
  const [toast, setToast] = useState(null);
  const timer = useRef(0);

  const showToast = useCallback((message, tone) => {
    setToast({ message, tone, id: Date.now() });
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setToast(null), VISIBLE_MS);
  }, []);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  return { toast, showToast };
}
