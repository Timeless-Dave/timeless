import { useCallback, useEffect, useRef, useState } from 'react';

const PREFIX = 'timeless_plan_draft:';

function readDraft(day) {
  try {
    const raw = window.localStorage.getItem(PREFIX + day);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/**
 * Keeps unsaved plan edits alive across reloads and date switches.
 *
 * A draft is only offered back when it is newer than the saved plan, so a plan
 * changed elsewhere is never silently overwritten by a stale local copy.
 */
export function usePlanDraft(day, savedAt) {
  const [status, setStatus] = useState('saved');
  const dirtyRef = useRef(false);

  const save = useCallback(
    payload => {
      if (!day) return;
      dirtyRef.current = true;
      setStatus('unsaved');
      try {
        window.localStorage.setItem(
          PREFIX + day,
          JSON.stringify({ ...payload, at: new Date().toISOString() })
        );
      } catch {
        /* storage can be unavailable; the in-memory edits still stand */
      }
    },
    [day]
  );

  const clear = useCallback(() => {
    dirtyRef.current = false;
    setStatus('saved');
    try {
      window.localStorage.removeItem(PREFIX + day);
    } catch {
      /* nothing to clean up */
    }
  }, [day]);

  const restore = useCallback(() => {
    const draft = readDraft(day);
    if (!draft) return null;
    if (savedAt && draft.at && Date.parse(draft.at) <= Date.parse(`${savedAt}Z`.replace('ZZ', 'Z'))) {
      return null;
    }
    return draft;
  }, [day, savedAt]);

  // Closing the tab mid-edit should cost a confirmation, not the work.
  useEffect(() => {
    const onBeforeUnload = event => {
      if (!dirtyRef.current) return undefined;
      event.preventDefault();
      event.returnValue = '';
      return '';
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, []);

  return { status, setStatus, save, clear, restore, isDirty: () => dirtyRef.current };
}
