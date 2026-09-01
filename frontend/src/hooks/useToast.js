import { useCallback, useState } from 'react';

export function useToast() {
  const [toast, setToast] = useState(null);

  const show = useCallback((message, tone) => {
    setToast({ message, tone, id: Date.now() });
    window.clearTimeout(show._timer);
    show._timer = window.setTimeout(() => setToast(null), 3200);
  }, []);

  return { toast, showToast: show };
}
