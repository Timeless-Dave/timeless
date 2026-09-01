import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import EffectsShell from '@/components/EffectsShell';
import PlanEditor from '@/components/PlanEditor';
import SideRays from '@/components/SideRays';
import { useReducedMotion } from '@/hooks/useReducedMotion';
import { api } from '@/lib/api';

export default function GatePage({ showToast }) {
  const navigate = useNavigate();
  const reduce = useReducedMotion();
  const [today, setToday] = useState('');
  const [day, setDay] = useState('');
  const [plan, setPlan] = useState(null);
  const [academics, setAcademics] = useState({ courses: [], presets: [], name: '' });
  const [err, setErr] = useState('');

  useEffect(() => {
    (async () => {
      const t = await api('/api/today');
      if (t.halt) {
        navigate('/halt');
        return;
      }
      if (t.needs_recap) {
        navigate('/recap');
        return;
      }
      setToday(t.day);
      setDay(t.day);
      const p = await api('/api/plan?day=' + encodeURIComponent(t.day));
      setPlan(p);
      try {
        const a = await api('/api/academics/current');
        setAcademics(a);
      } catch {
        /* optional */
      }
    })().catch(e => setErr(e.message));
  }, [navigate]);

  const onDayChange = async nextDay => {
    setDay(nextDay);
    try {
      const p = await api('/api/plan?day=' + encodeURIComponent(nextDay));
      setPlan(p);
    } catch (e) {
      setErr(e.message);
    }
  };

  const onSaved = async () => {
    if (day === today) navigate('/');
    else setErr(`Saved for ${day}. Today still needs a plan.`);
  };

  return (
    <EffectsShell enableGlow={false}>
      <div className="overlay-page gate-page">
        {!reduce ? (
          <div className="overlay-bg">
            <SideRays speed={1.5} rayColor1="#d08726" rayColor2="#f8debd" intensity={1.2} origin="top-left" opacity={0.7} />
          </div>
        ) : null}
        <div className="panel card">
          <p className="get-started-kicker">Daily gate</p>
          <h1 className="page-title">Lock a plan</h1>
          <p className="card-lead">Today stays locked until this day&apos;s plan is saved.</p>
          {err ? <p className="empty-note">{err}</p> : null}
          <PlanEditor
            compact
            plan={plan}
            planDay={day}
            minDay={today}
            academics={academics}
            onDayChange={onDayChange}
            onSaved={onSaved}
            showToast={showToast}
            showCalendarSync={false}
          />
        </div>
      </div>
    </EffectsShell>
  );
}
