import MenuButton from '@/components/MenuButton';
import { goalActions } from '@/lib/goals';

/**
 * The next step for a goal as a single button, with the exceptional outcomes
 * (defer, drop) one level down so they never compete with finishing.
 */
export default function GoalActions({ goal, busy, onStatus, size = 'small' }) {
  const { primary, more } = goalActions(goal);
  return (
    <div className="goal-actions">
      <button
        type="button"
        className={size === 'large' ? '' : 'ghost small-btn'}
        disabled={busy}
        onClick={() => onStatus(goal, primary)}
      >
        {primary.label}
      </button>
      {more.length ? (
        <MenuButton label="More" disabled={busy}>
          {more.map(action => (
            <button
              key={action.status}
              type="button"
              role="menuitem"
              tabIndex={-1}
              className="menu-item"
              onClick={() => onStatus(goal, action)}
            >
              {action.label}
            </button>
          ))}
        </MenuButton>
      ) : null}
    </div>
  );
}
