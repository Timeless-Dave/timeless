import { useCallback, useId, useRef } from 'react';

/**
 * A radiogroup with roving tabindex: arrow keys move between options,
 * Home/End jump to the ends, Space/Enter select the focused option.
 */
export default function RadioGroup({ labelId, options, value, onChange, className = '' }) {
  const groupRef = useRef(null);
  const id = useId();

  const radios = useCallback(
    () => Array.from(groupRef.current?.querySelectorAll('[role="radio"]') || []),
    []
  );

  const focusIndex = index => {
    const list = radios();
    list[index]?.focus();
  };

  const handleKeyDown = event => {
    const list = radios();
    const index = list.indexOf(document.activeElement);
    if (index < 0) return;

    switch (event.key) {
      case 'ArrowRight':
      case 'ArrowDown':
        event.preventDefault();
        focusIndex((index + 1) % list.length);
        break;
      case 'ArrowLeft':
      case 'ArrowUp':
        event.preventDefault();
        focusIndex((index - 1 + list.length) % list.length);
        break;
      case 'Home':
        event.preventDefault();
        focusIndex(0);
        break;
      case 'End':
        event.preventDefault();
        focusIndex(list.length - 1);
        break;
      case ' ':
      case 'Enter':
        event.preventDefault();
        onChange(list[index]?.dataset?.value);
        break;
      default:
        break;
    }
  };

  return (
    <div
      ref={groupRef}
      id={id}
      role="radiogroup"
      aria-labelledby={labelId}
      className={`choice-row ${className}`.trim()}
      onKeyDown={handleKeyDown}
    >
      {options.map(([optionValue, label]) => {
        const checked = value === optionValue;
        return (
          <button
            key={optionValue}
            type="button"
            role="radio"
            data-value={optionValue}
            aria-checked={checked}
            tabIndex={checked ? 0 : -1}
            className={`ghost${checked ? ' on' : ''}`}
            onClick={() => onChange(optionValue)}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
