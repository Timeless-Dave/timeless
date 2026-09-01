import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';

const CHAT_KEY = 'timeless_chat';

export function useChat(onRefresh) {
  const [open, setOpen] = useState(false);
  const [thread, setThread] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(CHAT_KEY) || '[]');
    } catch {
      return [];
    }
  });
  const [busy, setBusy] = useState(false);

  const save = useCallback(items => {
    localStorage.setItem(CHAT_KEY, JSON.stringify(items.slice(-40)));
  }, []);

  const send = useCallback(
    async message => {
      message = (message || '').trim();
      if (!message) return;
      const next = [...thread, { role: 'user', content: message }];
      setThread(next);
      setBusy(true);
      try {
        const r = await api('/api/chat', {
          method: 'POST',
          body: JSON.stringify({
            message,
            history: next.slice(0, -1).map(m => ({
              role: m.role === 'user' ? 'user' : 'assistant',
              content: m.content,
            })),
          }),
        });
        const updated = [
          ...next,
          { role: 'assistant', content: (r.offline ? '(offline) ' : '') + (r.reply || '') },
        ];
        setThread(updated);
        save(updated);
        if (onRefresh) await onRefresh({ force: true });
      } catch (err) {
        const updated = [...next, { role: 'assistant', content: err.message || 'Could not reach the brain.' }];
        setThread(updated);
      } finally {
        setBusy(false);
      }
    },
    [thread, save, onRefresh]
  );

  const clear = () => {
    setThread([]);
    save([]);
  };

  return { open, setOpen, thread, send, clear, busy };
}

export function ChatFab({ onRefresh, showToast }) {
  const { open, setOpen, thread, send, clear, busy } = useChat(onRefresh);
  const [draft, setDraft] = useState('');

  return (
    <div className={`chat${open ? ' open' : ''}`} id="fab">
      <button type="button" className="chat-toggle" onClick={() => setOpen(v => !v)} aria-label="Chat">
        Chat
      </button>
      <div className="chat-panel">
        <div className="card-head">
          <span>Timeless</span>
          <button type="button" className="ghost small-btn" onClick={clear}>
            Clear
          </button>
        </div>
        <div className="chat-log">
          {thread.length ? (
            thread.map((m, i) => (
              <div key={i} className={`bubble ${m.role === 'user' ? 'you' : 'bot'}`}>
                {m.content}
              </div>
            ))
          ) : (
            <div className="bubble bot">Ask about your day, or tell me to do something.</div>
          )}
        </div>
        <div className="row">
          <input
            value={draft}
            onChange={e => setDraft(e.target.value)}
            placeholder="Ask or tell me to do something…"
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                send(draft);
                setDraft('');
              }
            }}
          />
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              send(draft);
              setDraft('');
            }}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
