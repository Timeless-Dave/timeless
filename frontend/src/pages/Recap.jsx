import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import EffectsShell from '@/components/EffectsShell';
import SideRays from '@/components/SideRays';
import TextType from '@/components/TextType';
import { useReducedMotion } from '@/hooks/useReducedMotion';
import { api } from '@/lib/api';

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
      if (t.halt) { navigate('/halt'); return; }
      if (!t.needs_recap) { navigate(t.needs_gate ? '/gate' : '/'); return; }
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
        {!reduce ? (
          <div className="overlay-bg">
            <SideRays speed={1.8} rayColor1="#d08726" rayColor2="#f8debd" intensity={1} origin="top-right" />
          </div>
        ) : null}
        <div className="recap-ticket card">
          {phoneStep ? (
            <>
              <h1 className="page-title">Reconnect phone</h1>
              <p className="card-lead">Wireless on hotspot, USB if cabled, or skip for Mac-only recap.</p>
              <div className="row">
                <button type="button" onClick={() => runRecap({ skip_phone: false, mode: 'wireless' })}>Wireless</button>
                <button type="button" className="ghost" onClick={() => runRecap({ skip_phone: false, mode: 'usb' })}>USB</button>
                <button type="button" className="ghost" onClick={() => runRecap({ skip_phone: true })}>Skip</button>
              </div>
              {msg ? <p>{msg}</p> : null}
            </>
          ) : (
            <>
              <h1 className="page-title">
                {!reduce ? <TextType text={card.title || 'Recap'} loop={false} showCursor={false} /> : card.title}
              </h1>
              <div className="metric-value">{card.stat || 'Pending'}</div>
              <p>{card.body}</p>
              <div className="row">
                <button type="button" className="ghost" disabled={index <= 0} onClick={() => setIndex(i => i - 1)}>Prev</button>
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
