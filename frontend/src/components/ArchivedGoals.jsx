import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '@/lib/api';
import { deferredLabel, statusLabel, statusTone } from '@/lib/goals';

/**
 * Goals removed from a plan after they had already been worked on. The editor
 * promises their history is kept; this is where it can actually be retrieved
 * once the immediate Undo is gone.
 */
export default function ArchivedGoals({ day, refreshToken, onRestored, showToast }) {
  const [goals, setGoals] = useState([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState('');

  const request = useRef(0);

  const load = useCallback(async () => {
    if (!day) return;
    // Flipping through days races these fetches; only the newest wins.
    const ticket = ++request.current;
    try {
      const data = await api(`/api/goals/archived?day=${encodeURIComponent(day)}`);
      if (ticket !== request.current) return;
      setGoals(data.goals || []);
      setError('');
    } catch (err) {
      if (ticket === request.current) setError(err.message);
    }
  }, [day]);

  useEffect(() => {
    // Fetching on mount is what effects are for. `load` is async, so its state
    // updates happen after an await, not synchronously in this effect.
    // oxlint-disable-next-line react/set-state-in-effect
    load();
    return () => {
      request.current += 1;
    };
    // `refreshToken` changes when the plan is saved, so the list refetches
    // without remounting — remounting collapsed the panel under the reader.
  }, [load, refreshToken]);

  const restore = async goal => {
    setBusy(goal.id);
    try {
      await api(`/api/goals/${goal.id}/restore`, { method: 'POST', body: '{}' });
      showToast?.(`Restored “${goal.text}”.`, 'mint');
      await load();
      await onRestored?.();
    } catch (err) {
      showToast?.(err.message);
    } finally {
      setBusy(null);
    }
  };

  if (!goals.length && !error) return null;

  return (
    <section className="archived-goals">
      <button
        type="button"
        className="ghost small-btn"
        aria-expanded={open}
        aria-controls="archived-goals-list"
        onClick={() => setOpen(value => !value)}
      >
        {open ? 'Hide' : 'Show'} removed goals ({goals.length})
      </button>
      <div id="archived-goals-list" hidden={!open}>
        {error ? (
          <p className="issue issue--error" role="alert">
            {error}
          </p>
        ) : null}
        <p className="goal-section__hint">
          Removed from this day&apos;s plan after they had history. Restoring brings back the status
          and notes exactly as they were.
        </p>
        <ul className="archived-goals__list">
          {goals.map(goal => (
            <li key={goal.id}>
              <div className="archived-goals__body">
                <span className="archived-goals__text">{goal.text}</span>
                <span className="archived-goals__meta">
                  <span className={`chip ${statusTone(goal.status)}`}>{statusLabel(goal.status)}</span>
                  {goal.deferred_count ? <span>{deferredLabel(goal.deferred_count)}</span> : null}
                  {goal.note ? <span className="archived-goals__note">{goal.note}</span> : null}
                </span>
              </div>
              <button
                type="button"
                className="ghost small-btn"
                disabled={busy === goal.id}
                onClick={() => restore(goal)}
              >
                {busy === goal.id ? 'Restoring…' : 'Restore'}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
