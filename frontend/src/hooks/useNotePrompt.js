import { useCallback, useRef, useState } from 'react';

/**
 * Promise-based access to the note dialog, so call sites read like the
 * `window.prompt` they replace without any of its behaviour.
 */
export function useNotePrompt() {
  const [request, setRequest] = useState(null);
  const resolver = useRef(null);

  const ask = useCallback(options => {
    return new Promise(resolve => {
      resolver.current = resolve;
      setRequest({ ...options, id: Date.now() });
    });
  }, []);

  const settle = useCallback(value => {
    setRequest(null);
    const resolve = resolver.current;
    resolver.current = null;
    resolve?.(value);
  }, []);

  return {
    ask,
    dialogProps: {
      // Used as the React key so each request gets a fresh dialog.
      requestId: request?.id ?? 'idle',
      open: Boolean(request),
      title: request?.title || '',
      hint: request?.hint,
      confirmLabel: request?.confirmLabel,
      initialValue: request?.initialValue || '',
      optional: request?.optional !== false,
      onConfirm: value => settle(value),
      onCancel: () => settle(null),
    },
  };
}
