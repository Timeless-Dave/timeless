import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import EffectsShell from '@/components/EffectsShell';
import EvilEye from '@/components/EvilEye';
import { useIsMobile, useReducedMotion } from '@/hooks/useReducedMotion';
import { api } from '@/lib/api';
import { relTime, when } from '@/lib/summary';

export default function HaltPage({ showToast }) {
  const navigate = useNavigate();
  const reduce = useReducedMotion();
  const mobile = useIsMobile();
  const [halt, setHalt] = useState(null);
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);
  const [imInArmed, setImInArmed] = useState(false);
  const [miss, setMiss] = useState(0);

  const tick = async () => {
    if (busy) return;
    const t = await api('/api/today');
    const h = t.halt;
    if (!h) {
      setMiss(m => m + 1);
      if (miss >= 1) navigate(t.needs_recap ? '/recap' : t.needs_gate ? '/gate' : '/');
      return;
    }
    setMiss(0);
    setHalt(h);
    setImInArmed(false);
  };

  const tickRef = useRef(tick);
  useEffect(() => {
    tickRef.current = tick;
  });

  useEffect(() => {
    // The poll reads the latest tick through a ref so the interval is created
    // once, instead of being torn down and rebuilt on every state change.
    const run = () => tickRef.current();
    run();
    const id = setInterval(run, 4000);
    return () => clearInterval(id);
  }, []);

  const meetingId = () => halt?.meeting_id || halt?.id;

  const leave = async (msg, ok = true) => {
    setStatus(msg);
    showToast?.(msg, ok ? 'mint' : undefined);
    await new Promise(r => setTimeout(r, 1100));
    navigate('/');
  };

  return (
    <EffectsShell enableGlow={false}>
      <div className="overlay-page halt-page">
        {!reduce && !mobile ? (
          <div className="overlay-bg overlay-bg--full">
            <EvilEye eyeColor="#d08726" intensity={1.2} scale={1} backgroundColor="#120F17" />
          </div>
        ) : null}
        <div className="panel card">
          <p className="get-started-kicker">Halt</p>
          <h1 className="page-title">{halt?.title || 'Event'}</h1>
          <p className="card-lead">{halt ? when(halt.start_at) : ''}</p>
          <p>{halt?.halt_kind === 'reminder' ? 'Reminder' : `Meeting now, ${halt ? relTime(halt.start_at) : ''}`}</p>
          {status ? <p>{status}</p> : null}
          <div className="row">
            {halt?.can_open_link ? (
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await api(`/api/meetings/${meetingId()}/join`, {
                      method: 'POST',
                      body: JSON.stringify({ reminder_id: halt.id }),
                    });
                    await leave('Link opened — you will be reminded again at start time.');
                  } catch (e) {
                    setBusy(false);
                    setStatus(e.message);
                  }
                }}
              >
                Open link
              </button>
            ) : null}
            {halt?.requires_join ? (
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await api(`/api/meetings/${meetingId()}/join`, { method: 'POST', body: '{}' });
                    await leave('Opening meeting…');
                  } catch (e) {
                    setBusy(false);
                    setStatus(e.message);
                  }
                }}
              >
                Join
              </button>
            ) : null}
            {halt?.can_headed ? (
              <button
                type="button"
                className="ghost"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await api(`/api/reminders/${halt.id}/ack`, { method: 'POST', body: JSON.stringify({ action: 'headed' }) });
                    await leave('Marked as headed.');
                  } catch (e) {
                    setBusy(false);
                    setStatus(e.message);
                  }
                }}
              >
                I&apos;m headed
              </button>
            ) : null}
            {halt?.can_im_in ? (
              <button
                type="button"
                className={`ghost${imInArmed ? ' warn' : ''}`}
                disabled={busy}
                onClick={async () => {
                  if (!imInArmed) {
                    setImInArmed(true);
                    setStatus(halt.im_in_hint || 'Tap again to confirm.');
                    return;
                  }
                  setBusy(true);
                  try {
                    await api(`/api/meetings/${meetingId()}/ack`, {
                      method: 'POST',
                      body: JSON.stringify({ action: 'im_in', confirm: true }),
                    });
                    if (halt.halt_kind === 'reminder') {
                      await api(`/api/reminders/${halt.id}/ack`, { method: 'POST', body: JSON.stringify({ action: 'im_in' }) });
                    }
                    await leave('Checked in.');
                  } catch (e) {
                    setBusy(false);
                    setImInArmed(false);
                    setStatus(e.message);
                  }
                }}
              >
                {imInArmed ? 'Confirm in' : 'I\'m in'}
              </button>
            ) : null}
            {halt?.halt_kind === 'reminder' ? (
              <button
                type="button"
                className="ghost"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await api(`/api/reminders/${halt.id}/ack`, { method: 'POST', body: JSON.stringify({ action: 'dismiss' }) });
                    await leave('Dismissed.');
                  } catch (e) {
                    setBusy(false);
                    setStatus(e.message);
                  }
                }}
              >
                Dismiss
              </button>
            ) : null}
          </div>
          <button
            type="button"
            className="panic-btn"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await api('/api/quiet/panic', { method: 'POST' });
                await leave('Panic mode, 1 hour quiet.');
              } catch (e) {
                setBusy(false);
                setStatus(e.message);
              }
            }}
          >
            Panic, 1h quiet
          </button>
        </div>
      </div>
    </EffectsShell>
  );
}
