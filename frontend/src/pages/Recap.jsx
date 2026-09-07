import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import EffectsShell from '@/components/EffectsShell';
import NoteDialog from '@/components/NoteDialog';
import OverlayBackground from '@/components/OverlayBackground';
import { useReducedMotion } from '@/hooks/useReducedMotion';
import { api } from '@/lib/api';
import { useNotePrompt } from '@/hooks/useNotePrompt';
import { BUCKET, bucketLabel } from '@/lib/evidence';
import { deferredLabel, statusActions, statusLabel, statusTone } from '@/lib/goals';

function CompareWeek({ week, goals, done }) {
  const max = Math.max(goals, done, 1);
  const peak = Math.max(...(week || []).map(d => d.goals || 0), 1);

  return (
    <div className="recap-compare">
      <div className="recap-compare__bars">
        <div className="compare-row">
          <span>Goals set</span>
          <div className="compare-track">
            <i className="compare-fill" style={{ width: `${Math.max(6, Math.round((goals / max) * 100))}%` }} />
          </div>
          <b>{goals}</b>
        </div>
        <div className="compare-row">
          <span>Finished</span>
          <div className="compare-track">
            <i className="compare-fill" style={{ width: `${Math.max(6, Math.round((done / max) * 100))}%` }} />
          </div>
          <b>{done}</b>
        </div>
      </div>
      <p className="card-lead recap-body--muted">Last seven days (goals set, filled by goals finished)</p>
      <div className="week-bars">
        {(week || []).map(d => {
          const h = Math.max(4, Math.round(((d.goals || 0) / peak) * 72));
          const fill = d.goals ? Math.round(((d.done || 0) / d.goals) * 100) : 0;
          return (
            <div key={d.day} className="week-col" title={`${d.day}: ${d.done || 0} of ${d.goals || 0} finished`}>
              <i style={{ height: `${h}px` }}>
                <b style={{ height: `${fill}%` }} />
              </i>
              <b>{d.label || d.day?.slice(5)}</b>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Judge each goal. Only the owner can say what was finished. */
function GoalReview({ goals, busy, onStatus }) {
  if (!goals.length) return <p className="card-lead recap-body">No goals were set for this day.</p>;
  return (
    <ul className="recap-goals">
      {goals.map(goal => (
        <li key={goal.id} className={`recap-goal recap-goal--${goal.status}`}>
          <div className="recap-goal__body">
            <span className="recap-goal__text">{goal.text}</span>
            <span className="recap-goal__meta">
              <span className={`chip ${statusTone(goal.status)}`}>{statusLabel(goal.status)}</span>
              {goal.deferred_count ? (
                <span className="recap-goal__carried">{deferredLabel(goal.deferred_count)}</span>
              ) : null}
              {goal.note ? <span className="recap-goal__note">{goal.note}</span> : null}
            </span>
          </div>
          <div className="recap-goal__actions">
            {statusActions(goal)
              .filter(action => action.status !== 'active')
              .map(action => (
                <button
                  key={action.status}
                  type="button"
                  className="ghost small-btn"
                  disabled={busy === goal.id}
                  onClick={() => onStatus(goal, action)}
                >
                  {action.label}
                </button>
              ))}
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Correct what the classifier got wrong; the estimate is rebuilt from the ruling. */
function EvidenceReview({ evidence, busy, onCorrect }) {
  if (!evidence.length) return <p className="card-lead recap-body">Nothing was classified for this day.</p>;
  return (
    <ul className="recap-evidence">
      {evidence.map(row => (
        <li key={row.title}>
          <div className="recap-evidence__head">
            <span className="recap-evidence__title">{row.label || row.title}</span>
            <span className="recap-evidence__minutes">{row.minutes} min</span>
          </div>
          <div className="recap-evidence__buckets">
            {Object.keys(BUCKET).map(bucket => (
              <button
                key={bucket}
                type="button"
                className={`ghost small-btn${row.bucket === bucket ? ' on' : ''}`}
                aria-pressed={row.bucket === bucket}
                disabled={busy === row.title}
                onClick={() => onCorrect(row, bucket)}
              >
                {bucketLabel(bucket)}
              </button>
            ))}
            {row.corrected ? <span className="recap-evidence__flag">your call</span> : null}
          </div>
        </li>
      ))}
    </ul>
  );
}

function RecapCard({ card, live, busy, onStatus, onCorrect, onLesson }) {
  const lines = card.lines || [];
  const interactive = ['goals', 'evidence', 'lesson', 'tomorrow'].includes(card.kind);

  return (
    <>
      {card.kicker ? <p className="get-started-kicker">{card.kicker}</p> : null}
      <h1 className="page-title">{card.title || 'Recap'}</h1>
      <div className="metric-value">{card.stat || 'Pending'}</div>
      {card.stat_label ? <p className="card-lead">{card.stat_label}</p> : null}
      <div className="recap-bar" />
      {card.body ? <p className="card-lead recap-body">{card.body}</p> : null}

      {card.kind === 'goals' ? (
        <GoalReview goals={live.goals} busy={busy} onStatus={onStatus} />
      ) : null}

      {card.kind === 'evidence' ? (
        <>
          <EvidenceReview evidence={live.evidence} busy={busy} onCorrect={onCorrect} />
          <p className="recap-caveat">
            Estimated by {live.productivity?.method || 'matching plan text against observed activity'}. Your
            corrections replace the guess.
          </p>
        </>
      ) : null}

      {card.kind === 'lesson' ? (
        <label className="recap-lesson">
          <span className="recap-lesson__label">Lesson for next time</span>
          <textarea
            rows={3}
            value={live.lesson}
            maxLength={600}
            placeholder="What would you tell yourself before starting this day again?"
            onChange={e => onLesson(e.target.value)}
          />
        </label>
      ) : null}

      {card.kind === 'tomorrow' ? (
        live.open.length ? (
          <ul className="recap-lines card-lead">
            {live.open.map(goal => (
              <li key={goal.id}>
                {goal.text}
                {goal.deferred_count ? <em> — {deferredLabel(goal.deferred_count)}</em> : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="card-lead recap-body">Nothing is left open. Tomorrow starts clean.</p>
        )
      ) : null}

      {card.kind === 'compare' && card.compare ? (
        <CompareWeek week={card.compare.week} goals={card.compare.goals} done={card.compare.done} />
      ) : null}

      {!interactive && lines.length ? (
        <ul className="recap-lines card-lead">
          {lines.map((line, i) => (
            <li key={`${card.title}-${i}`}>{line}</li>
          ))}
        </ul>
      ) : null}
    </>
  );
}

export default function RecapPage({ showToast }) {
  const navigate = useNavigate();
  const reduce = useReducedMotion();
  const [cards, setCards] = useState([]);
  const [index, setIndex] = useState(0);
  const [phoneStep, setPhoneStep] = useState(false);
  const [msg, setMsg] = useState('');
  const [day, setDay] = useState('');
  const [goals, setGoals] = useState([]);
  const [productivity, setProductivity] = useState(null);
  const [lesson, setLesson] = useState('');
  const [busy, setBusy] = useState(null);
  const { ask, dialogProps } = useNotePrompt();

  // Goals and evidence change while the recap is open, so the interactive cards
  // read live state rather than the snapshot stored with the cards.
  const loadLive = useCallback(async recapDay => {
    if (!recapDay) return;
    const [goalData, prod, reflection] = await Promise.all([
      api('/api/goals?day=' + encodeURIComponent(recapDay)),
      api('/api/productivity?day=' + encodeURIComponent(recapDay)),
      api('/api/recap/reflection?day=' + encodeURIComponent(recapDay)),
    ]);
    setGoals(goalData.goals || []);
    setProductivity(prod);
    setLesson(reflection.lesson || '');
  }, []);

  useEffect(() => {
    (async () => {
      const t = await api('/api/today');
      if (t.halt) {
        navigate('/halt');
        return;
      }
      if (!t.needs_recap) {
        navigate(t.needs_gate ? '/gate' : '/');
        return;
      }
      setDay(t.recap_day || '');
      await loadLive(t.recap_day);
      const existing = t.recap?.cards;
      if (existing?.length && t.recap.phone_synced) {
        setCards(existing);
        return;
      }
      setPhoneStep(true);
    })().catch(e => setMsg(e.message));
  }, [navigate, loadLive]);

  const runRecap = async body => {
    setMsg('Working…');
    try {
      const r = await api('/api/recap/generate', { method: 'POST', body: JSON.stringify(body) });
      setMsg(r.phone?.detail || (r.phone_synced ? 'Phone synced.' : 'Mac-only recap.'));
      setCards(r.cards || []);
      setIndex(0);
      setPhoneStep(false);
      await loadLive(r.day || day);
    } catch (err) {
      setMsg(err.message);
    }
  };

  const setStatus = async (goal, action) => {
    let note = action.note;
    if (action.needsNote) {
      note = await ask({
        title: `${action.label}: ${goal.text}`,
        hint: 'Why it went this way. This is what the recap is for.',
        confirmLabel: action.label,
        initialValue: goal.note || '',
      });
      if (note === null) return;
    }
    setBusy(goal.id);
    try {
      await api(`/api/goals/${goal.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: action.status, note }),
      });
      await loadLive(day);
    } catch (err) {
      showToast?.(err.message);
    } finally {
      setBusy(null);
    }
  };

  const correct = async (row, bucket) => {
    if (row.bucket === bucket) return;
    setBusy(row.title);
    try {
      await api('/api/activity/correct', {
        method: 'POST',
        body: JSON.stringify({ day, title: row.title, bucket }),
      });
      await loadLive(day);
    } catch (err) {
      showToast?.(err.message);
    } finally {
      setBusy(null);
    }
  };

  const deferRemaining = async () => {
    const note = await ask({
      title: `Defer ${unjudged.length} goal${unjudged.length === 1 ? '' : 's'}`,
      hint: 'They carry into your next planned day. One reason covers all of them.',
      confirmLabel: 'Defer them',
    });
    if (note === null) return;
    setBusy('bulk');
    try {
      for (const goal of unjudged) {
        await api(`/api/goals/${goal.id}`, {
          method: 'PATCH',
          body: JSON.stringify({ status: 'deferred', note }),
        });
      }
      await loadLive(day);
    } catch (err) {
      showToast?.(err.message);
    } finally {
      setBusy(null);
    }
  };

  const finish = async () => {
    try {
      // Sent unconditionally so clearing a lesson persists as a clear.
      await api('/api/recap/reflect', { method: 'POST', body: JSON.stringify({ day, lesson }) });
      await api('/api/recap/ack', { method: 'POST' });
      showToast?.('Day closed.', 'mint');
      navigate('/');
    } catch (err) {
      // The server enforces the same rule the button does. If this state is
      // stale, reload the goals so the screen agrees with the record.
      showToast?.(err.message);
      await loadLive(day).catch(() => {});
    }
  };

  const card = cards[index] || {};
  const open = goals.filter(g => ['planned', 'active', 'partial', 'deferred'].includes(g.status));
  // A goal left planned or active was never judged. Closing on that would make the
  // day's most important record ambiguous, so the close is held until it is settled.
  const unjudged = goals.filter(g => ['planned', 'active'].includes(g.status));
  const goalsCardIndex = cards.findIndex(c => c.kind === 'goals');
  const last = index >= cards.length - 1;
  const blocked = last && unjudged.length > 0;
  const live = { goals, evidence: productivity?.evidence || [], productivity, lesson, open };

  return (
    <EffectsShell enableGlow={false}>
      <div className="overlay-page recap-page">
        {!reduce ? <OverlayBackground variant="recap" /> : null}
        <div className="recap-ticket card">
          {phoneStep ? (
            <>
              <h1 className="page-title">Reconnect phone</h1>
              <p className="card-lead">Wireless on hotspot, USB if cabled, or skip for Mac-only recap.</p>
              <div className="row">
                <button type="button" onClick={() => runRecap({ skip_phone: false, mode: 'wireless' })}>
                  Wireless
                </button>
                <button type="button" className="ghost" onClick={() => runRecap({ skip_phone: false, mode: 'usb' })}>
                  USB
                </button>
                <button type="button" className="ghost" onClick={() => runRecap({ skip_phone: true })}>
                  Skip
                </button>
              </div>
              {msg ? <p className="recap-body">{msg}</p> : null}
            </>
          ) : (
            <>
              {cards.length ? (
                <>
                  <p className="recap-step">
                    Step {index + 1} of {cards.length}
                  </p>
                  <div className="recap-dots" aria-hidden="true">
                    {cards.map((_, n) => (
                      <i key={n} className={n === index ? 'on' : ''} />
                    ))}
                  </div>
                </>
              ) : null}
              <RecapCard
                card={card}
                live={live}
                busy={busy}
                onStatus={setStatus}
                onCorrect={correct}
                onLesson={setLesson}
              />
              {blocked ? (
                <div className="recap-block" role="status">
                  <p>
                    {unjudged.length} goal{unjudged.length === 1 ? '' : 's'} still{' '}
                    {unjudged.length === 1 ? 'needs' : 'need'} an outcome. The day cannot close on an
                    unanswered record.
                  </p>
                  <div className="row">
                    <button
                      type="button"
                      disabled={goalsCardIndex < 0}
                      onClick={() => setIndex(goalsCardIndex)}
                    >
                      Judge {unjudged.length} goal{unjudged.length === 1 ? '' : 's'}
                    </button>
                    <button
                      type="button"
                      className="ghost"
                      disabled={busy === 'bulk'}
                      onClick={deferRemaining}
                    >
                      {busy === 'bulk' ? 'Deferring…' : 'Defer the rest'}
                    </button>
                  </div>
                </div>
              ) : null}
              <div className="row recap-nav">
                <button type="button" className="ghost" disabled={index <= 0} onClick={() => setIndex(i => i - 1)}>
                  Prev
                </button>
                <button
                  type="button"
                  disabled={blocked}
                  onClick={last ? finish : () => setIndex(i => i + 1)}
                >
                  {last ? 'Close the day' : 'Next'}
                </button>
              </div>
            </>
          )}
        </div>
        {dialogProps.open ? (
          <NoteDialog key={dialogProps.requestId} {...dialogProps} busy={busy === 'bulk'} />
        ) : null}
      </div>
    </EffectsShell>
  );
}
