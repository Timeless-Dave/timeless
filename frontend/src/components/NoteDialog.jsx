import { useEffect, useId, useRef, useState } from 'react';

/**
 * A modal for capturing the reason behind an outcome.
 *
 * Replaces `window.prompt`, which could not say whether a reason was optional,
 * gave no confirmation, sat outside the page's visual language, and behaves
 * inconsistently on mobile and with assistive technology.
 */
export default function NoteDialog({
  // Rendered with a per-request key, so `initialValue` seeds state on mount and
  // never needs syncing back in from an effect.
  open,
  title,
  hint,
  confirmLabel = 'Save',
  initialValue = '',
  optional = true,
  busy = false,
  onConfirm,
  onCancel,
}) {
  const [value, setValue] = useState(initialValue);
  const dialogRef = useRef(null);
  const fieldRef = useRef(null);
  const titleId = useId();
  const hintId = useId();

  // Held in a ref so the focus effect depends only on `open`. A changing
  // callback identity would otherwise tear the effect down mid-edit, bouncing
  // focus out of the dialog and back in.
  const cancelRef = useRef(onCancel);
  useEffect(() => {
    cancelRef.current = onCancel;
  });

  useEffect(() => {
    if (!open) return undefined;
    // Captured in the closure, not a ref: this instance is unmounted when the
    // dialog closes, so restoring from its own cleanup is what actually runs.
    const previouslyFocused = document.activeElement;
    fieldRef.current?.focus();

    const onKey = event => {
      if (event.key === 'Escape') {
        event.stopPropagation();
        cancelRef.current?.();
        return;
      }
      if (event.key !== 'Tab') return;
      // Focus stays inside the dialog while it is open.
      const focusable = dialogRef.current?.querySelectorAll(
        'button:not([disabled]), textarea, input, [href], select, [tabindex]:not([tabindex="-1"])'
      );
      if (!focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKey, true);
    return () => {
      document.removeEventListener('keydown', onKey, true);
      if (previouslyFocused instanceof HTMLElement && document.contains(previouslyFocused)) {
        previouslyFocused.focus();
      }
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="note-dialog__scrim" onPointerDown={event => {
      if (event.target === event.currentTarget) onCancel?.();
    }}>
      <div
        className="note-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={hint ? hintId : undefined}
        ref={dialogRef}
      >
        <h2 id={titleId} className="note-dialog__title">
          {title}
        </h2>
        {hint ? (
          <p id={hintId} className="note-dialog__hint">
            {hint}
          </p>
        ) : null}
        <label className="note-dialog__field">
          <span className="note-dialog__label">
            Reason {optional ? <em>(optional)</em> : null}
          </span>
          <textarea
            ref={fieldRef}
            rows={3}
            maxLength={400}
            value={value}
            onChange={event => setValue(event.target.value)}
            onKeyDown={event => {
              if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) onConfirm?.(value);
            }}
          />
        </label>
        <div className="note-dialog__actions">
          <button type="button" className="ghost" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button type="button" onClick={() => onConfirm?.(value)} disabled={busy}>
            {busy ? 'Saving…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
