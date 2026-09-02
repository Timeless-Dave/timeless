import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import EffectsShell from '@/components/EffectsShell';
import OverlayBackground from '@/components/OverlayBackground';
import { useReducedMotion } from '@/hooks/useReducedMotion';
import { api } from '@/lib/api';

function CompareWeek({ week, blocks, events }) {
  const max = Math.max(blocks, events, 1);
  const peak = Math.max(...(week || []).map(d => d.events || 0), 1);

  return (
    <div className="recap-compare">
      <div className="recap-compare__bars">
        <div className="compare-row">
          <span>Planned</span>
          <div className="compare-track">
            <i className="compare-fill" style={{ width: `${Math.max(6, Math.round((blocks / max) * 100))}%` }} />
          </div>
          <b>{blocks}</b>
        </div>
        <div className="compare-row">
          <span>Showed up</span>
          <div className="compare-track">
            <i className="compare-fill" style={{ width: `${Math.max(6, Math.round((events / max) * 100))}%` }} />
          </div>
          <b>{events}</b>
        </div>
      </div>
      <p className="card-lead recap-body--muted">Last seven days (notes logged)</p>
      <div className="week-bars">
        {(week || []).map(d => {
          const h = Math.max(4, Math.round(((d.events || 0) / peak) * 72));
          const title = d.day?.slice(5) || d.day;
          return (
            <div key={d.day} className="week-col" title={d.day}>
              <i style={{ height: `${h}px` }} />
              <b>{d.label || title}</b>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RecapCard({ card }) {
  const lines = card.lines || [];

  return (
    <>
      {card.kicker ? <p className="get-started-kicker">{card.kicker}</p> : null}
      <h1 className="page-title">{card.title || 'Recap'}</h1>
      <div className="metric-value">{card.stat || 'Pending'}</div>
      {card.stat_label ? <p className="card-lead">{card.stat_label}</p> : null}
      <div className="recap-bar" />
      {card.body ? <p className="card-lead recap-body">{card.body}</p> : null}
      {card.kind === 'compare' && card.compare ? (
        <CompareWeek week={card.compare.week} blocks={card.compare.blocks} events={card.compare.events} />
      ) : null}
      {lines.length ? (
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
      const existing = t.recap?.cards;
      if (existing?.length && t.recap.phone_synced) {
        setCards(existing);
        return;
      }
      setPhoneStep(true);
    })().catch(e => setMsg(e.message));
  }, [navigate]);

  const runRecap = async body => {
    setMsg('Working…');
    const r = await api('/api/recap/generate', { method: 'POST', body: JSON.stringify(body) });
    setMsg(r.phone?.detail || (r.phone_synced ? 'Phone synced.' : 'Mac-only recap.'));
    setCards(r.cards || []);
    setIndex(0);
    setPhoneStep(false);
  };

  const card = cards[index] || {};

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
                <div className="recap-dots" aria-hidden="true">
                  {cards.map((_, n) => (
                    <i key={n} className={n === index ? 'on' : ''} />
                  ))}
                </div>
              ) : null}
              <RecapCard card={card} />
              <div className="row recap-nav">
                <button type="button" className="ghost" disabled={index <= 0} onClick={() => setIndex(i => i - 1)}>
                  Prev
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    if (index >= cards.length - 1) {
                      await api('/api/recap/ack', { method: 'POST' });
                      showToast?.('Recap acknowledged.', 'mint');
                      navigate('/');
                      return;
                    }
                    setIndex(i => i + 1);
                  }}
                >
                  {index >= cards.length - 1 ? 'I saw this' : 'Next'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </EffectsShell>
  );
}
