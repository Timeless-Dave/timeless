import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChatCircleDots, CaretRight, PaperPlaneRight, X } from '@phosphor-icons/react';
import { ChatContext, useChatPanel } from '@/components/chat-context';
import { api } from '@/lib/api';
import '@/styles/chat-sidebar.css';

const CHAT_KEY = 'timeless_chat';

const HINTS = [
  'What matters now?',
  'Summarize my plan',
  'What meetings are left?',
  'open leetcode',
];

function loadThread() {
  try {
    const raw = JSON.parse(localStorage.getItem(CHAT_KEY) || '[]');
    return raw.map((m, i) => ({
      id: m.id || `legacy-${i}`,
      role: m.role,
      content: m.content || '',
    }));
  } catch {
    return [];
  }
}

export function ChatProvider({ onRefresh, children }) {
  const [open, setOpen] = useState(false);
  const [thread, setThread] = useState(loadThread);
  const [busy, setBusy] = useState(false);
  const threadRef = useRef(thread);

  useEffect(() => {
    threadRef.current = thread;
  }, [thread]);

  const save = useCallback(items => {
    localStorage.setItem(CHAT_KEY, JSON.stringify(items.slice(-40)));
  }, []);

  const send = useCallback(
    async rawMessage => {
      const message = (rawMessage || '').trim();
      if (!message || busy) return;

      const userTurn = { id: `u-${Date.now()}`, role: 'user', content: message };
      const withUser = [...threadRef.current, userTurn];
      threadRef.current = withUser;
      setThread(withUser);
      setBusy(true);

      try {
        const r = await api('/api/chat', {
          method: 'POST',
          body: JSON.stringify({
            message,
            history: withUser.slice(0, -1).map(m => ({
              role: m.role === 'user' ? 'user' : 'assistant',
              content: m.content,
            })),
          }),
        });
        const text =
          (r.offline ? '(offline) ' : '') +
          (r.reply || r.detail || (r.did ? 'Done.' : 'No reply from the brain.'));
        const withBot = [
          ...withUser,
          { id: `a-${Date.now()}`, role: 'assistant', content: text },
        ];
        threadRef.current = withBot;
        setThread(withBot);
        save(withBot);
        if (onRefresh) await onRefresh({ force: true });
      } catch (err) {
        const withBot = [
          ...withUser,
          {
            id: `e-${Date.now()}`,
            role: 'assistant',
            content: err.message || 'Could not reach the brain.',
          },
        ];
        threadRef.current = withBot;
        setThread(withBot);
        save(withBot);
      } finally {
        setBusy(false);
      }
    },
    [busy, onRefresh, save]
  );

  const clear = useCallback(() => {
    threadRef.current = [];
    setThread([]);
    save([]);
  }, [save]);

  const openChat = useCallback(() => setOpen(true), []);
  const closeChat = useCallback(() => setOpen(false), []);
  const toggleChat = useCallback(() => setOpen(v => !v), []);

  const value = useMemo(
    () => ({ open, setOpen, openChat, closeChat, toggleChat, thread, send, clear, busy }),
    [open, openChat, closeChat, toggleChat, thread, send, clear, busy]
  );

  return (
    <ChatContext.Provider value={value}>
      {children}
      <ChatSidebarUI />
    </ChatContext.Provider>
  );
}


function ChatSidebarUI() {
  const { open, toggleChat, closeChat, thread, send, clear, busy } = useChatPanel();
  const [draft, setDraft] = useState('');
  const logRef = useRef(null);
  const inputRef = useRef(null);
  const toggleRef = useRef(null);

  const dismiss = useCallback(() => {
    closeChat();
    requestAnimationFrame(() => toggleRef.current?.focus());
  }, [closeChat]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  useEffect(() => {
    const log = logRef.current;
    if (!log) return;
    log.scrollTop = log.scrollHeight;
  }, [thread, busy, open]);

  useEffect(() => {
    const onKey = e => {
      if (e.key === 'Escape' && open) dismiss();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, dismiss]);

  const submit = () => {
    if (!draft.trim()) return;
    send(draft);
    setDraft('');
  };

  return (
    <>
      <button
        ref={toggleRef}
        type="button"
        className={`chat-sidebar-toggle${open ? ' chat-sidebar-toggle--open' : ''}`}
        onClick={toggleChat}
        aria-label={open ? 'Close chat' : 'Open chat'}
        aria-expanded={open}
        aria-controls="timeless-chat"
      >
        {open ? <X size={26} weight="bold" /> : <ChatCircleDots size={28} weight="fill" />}
      </button>

      {open ? (
        <>
          <div
            className="chat-sidebar-backdrop open"
            onClick={dismiss}
            aria-hidden="false"
          />

          <aside
            className="chat-sidebar open"
            id="timeless-chat"
            aria-label="Timeless chat"
          >
        <header className="chat-sidebar__head">
          <div>
            <p className="chat-sidebar__kicker">Assistant</p>
            <h2 className="chat-sidebar__title">Timeless</h2>
          </div>
          <div className="chat-sidebar__head-actions">
            <button type="button" className="ghost small-btn" onClick={clear}>
              Clear
            </button>
            <button
              type="button"
              className="ghost small-btn chat-sidebar__close"
              onClick={dismiss}
              aria-label="Collapse chat"
            >
              <CaretRight size={18} weight="bold" aria-hidden />
            </button>
          </div>
        </header>

        <div className="chat-sidebar__log" ref={logRef} role="log" aria-live="polite">
          {thread.length ? (
            thread.map(m => (
              <div key={m.id} className={`chat-bubble chat-bubble--${m.role === 'user' ? 'you' : 'bot'}`}>
                {m.content}
              </div>
            ))
          ) : (
            <div className="chat-bubble chat-bubble--bot">
              Ask about your day, or tell me to do something.
            </div>
          )}
          {busy ? <div className="chat-bubble chat-bubble--bot chat-bubble--typing">Thinking…</div> : null}
        </div>

        <div className="chat-sidebar__hints">
          {HINTS.map(hint => (
            <button
              key={hint}
              type="button"
              className="chat-hint"
              disabled={busy}
              onClick={() => send(hint)}
            >
              {hint}
            </button>
          ))}
        </div>

        <footer className="chat-sidebar__composer">
          <input
            ref={inputRef}
            value={draft}
            onChange={e => setDraft(e.target.value)}
            placeholder="Ask or tell me to do something…"
            disabled={busy}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
          />
          <button type="button" className="chat-sidebar__send" disabled={busy || !draft.trim()} onClick={submit}>
            <PaperPlaneRight size={20} weight="fill" aria-hidden />
            <span>Send</span>
          </button>
        </footer>
      </aside>
        </>
      ) : null}
    </>
  );
}