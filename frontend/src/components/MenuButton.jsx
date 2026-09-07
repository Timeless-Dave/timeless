import { useCallback, useEffect, useId, useRef, useState } from 'react';

/**
 * A menu button with the keyboard behaviour the role implies: Arrow keys move
 * between items, Home/End jump to the ends, Enter/Space and Arrow Down open with
 * the first item focused, Arrow Up opens on the last, Escape closes and returns
 * focus to the trigger. Declaring `role="menu"` without this is a promise the
 * component does not keep.
 */
export default function MenuButton({ label, children, className = '', disabled = false, align = 'end' }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const wrapRef = useRef(null);
  const triggerRef = useRef(null);
  const menuRef = useRef(null);
  const pendingFocus = useRef('first');

  const items = useCallback(
    () => Array.from(menuRef.current?.querySelectorAll('[role="menuitem"]:not([disabled])') || []),
    []
  );

  const close = useCallback(
    ({ restoreFocus = true } = {}) => {
      setOpen(false);
      if (restoreFocus) triggerRef.current?.focus();
    },
    []
  );

  // Focus lands inside the menu as soon as it opens, at whichever end the key implied.
  useEffect(() => {
    if (!open) return;
    const list = items();
    if (!list.length) return;
    const target = pendingFocus.current === 'last' ? list[list.length - 1] : list[0];
    target?.focus();
  }, [open, items]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = event => {
      const list = items();
      const index = list.indexOf(document.activeElement);
      switch (event.key) {
        case 'Escape':
          event.stopPropagation();
          close();
          break;
        case 'ArrowDown':
          event.preventDefault();
          list[(index + 1) % list.length]?.focus();
          break;
        case 'ArrowUp':
          event.preventDefault();
          list[(index - 1 + list.length) % list.length]?.focus();
          break;
        case 'Home':
          event.preventDefault();
          list[0]?.focus();
          break;
        case 'End':
          event.preventDefault();
          list[list.length - 1]?.focus();
          break;
        case 'Tab':
          // A menu does not hold Tab; leaving it closes it.
          close({ restoreFocus: false });
          break;
        default:
          break;
      }
    };
    const onPointerDown = event => {
      if (!wrapRef.current?.contains(event.target)) close({ restoreFocus: false });
    };
    document.addEventListener('keydown', onKey, true);
    document.addEventListener('pointerdown', onPointerDown);
    return () => {
      document.removeEventListener('keydown', onKey, true);
      document.removeEventListener('pointerdown', onPointerDown);
    };
  }, [open, items, close]);

  const openWith = where => {
    pendingFocus.current = where;
    setOpen(true);
  };

  return (
    <div className={`menu-wrap ${className}`.trim()} ref={wrapRef}>
      <button
        type="button"
        ref={triggerRef}
        className="ghost small-btn menu-trigger"
        aria-expanded={open}
        aria-controls={id}
        aria-haspopup="menu"
        disabled={disabled}
        onClick={() => (open ? close({ restoreFocus: false }) : openWith('first'))}
        onKeyDown={event => {
          if (event.key === 'ArrowDown') {
            event.preventDefault();
            openWith('first');
          } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            openWith('last');
          }
        }}
      >
        {label}
      </button>
      <div
        id={id}
        role="menu"
        ref={menuRef}
        className={`menu-pop menu-pop--${align}`}
        hidden={!open}
        onClick={() => close()}
      >
        {children}
      </div>
    </div>
  );
}
