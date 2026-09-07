/** Explicit goal outcomes. These are the authoritative record of the day;
 * observed activity is supporting evidence and never sets them. */
export const GOAL_STATUS = {
  planned: { label: 'Planned', tone: 'neutral' },
  active: { label: 'Working on it', tone: 'amber' },
  done: { label: 'Done', tone: 'mint' },
  partial: { label: 'Partly done', tone: 'cyan' },
  deferred: { label: 'Deferred', tone: 'rose' },
  dropped: { label: 'Dropped', tone: 'neutral' },
};

/** Unfinished, so still worth carrying into another day. */
export const OPEN_STATUSES = ['planned', 'active', 'partial', 'deferred'];

/** What the day can still be pointed at, best first. Deferred is absent on
 * purpose: pushing a goal away should not hand it straight back. */
const PICKABLE_STATUSES = ['active', 'planned', 'partial'];

export function statusLabel(status) {
  return GOAL_STATUS[status]?.label || status || 'Planned';
}

export function statusTone(status) {
  return GOAL_STATUS[status]?.tone || 'neutral';
}

export function isOpen(goal) {
  return OPEN_STATUSES.includes(goal?.status || 'planned');
}

/** The goal the day is currently pointed at, in status preference order. */
export function currentGoal(goals) {
  const list = goals || [];
  for (const status of PICKABLE_STATUSES) {
    const match = list.find(goal => (goal.status || 'planned') === status);
    if (match) return match;
  }
  return null;
}

/** What each state means. Shown in the UI so the vocabulary is never guessed at. */
export const STATUS_HELP = {
  planned: 'Set for today, not started.',
  active: 'What you are working on right now. Only one goal at a time.',
  done: 'Finished. Counts toward the day.',
  partial: 'Real progress, not finished. Still actionable today, counts as half a goal, and carries forward.',
  deferred:
    'Deliberately not worked on today. Carries forward, but is never offered as your next goal.',
  dropped: 'No longer worth doing. Leaves the count entirely rather than reading as a failure.',
};

const START = { status: 'active', label: 'Start' };
const RESUME = { status: 'active', label: 'Resume' };
const DONE = { status: 'done', label: 'Done' };
const PARTIAL = { status: 'partial', label: 'Partly done', needsNote: true };
const DEFER = { status: 'deferred', label: 'Defer', needsNote: true };
const DROP = { status: 'dropped', label: 'Drop', needsNote: true };
// Reopening means the previous outcome note no longer describes the goal.
// Sending an explicit empty note clears it; omitting `note` would preserve it.
const REOPEN = { status: 'planned', label: 'Reopen', note: '' };

/** One primary action plus the rest behind a menu.
 *
 * Four peer buttons made deferring and dropping as prominent as finishing.
 * Only the ordinary next step stays visible. */
export function goalActions(goal) {
  switch (goal?.status || 'planned') {
    case 'active':
      return { primary: DONE, more: [PARTIAL, DEFER, DROP] };
    case 'partial':
      return { primary: DONE, more: [RESUME, DEFER, DROP] };
    case 'deferred':
      return { primary: START, more: [DONE, DROP] };
    case 'done':
      return { primary: REOPEN, more: [PARTIAL] };
    case 'dropped':
      return { primary: REOPEN, more: [] };
    default:
      return { primary: START, more: [DONE, DEFER, DROP] };
  }
}

/** Flattened, for surfaces that show every option at once. */
export function statusActions(goal) {
  const { primary, more } = goalActions(goal);
  return [primary, ...more];
}

export function goalProgressLabel(progress) {
  const total = progress?.counted ?? progress?.total ?? 0;
  if (!total) return 'No goals set for today.';
  const done = progress.done || 0;
  const partial = progress.partial || 0;
  const parts = [`${done} of ${total} done`];
  if (partial) parts.push(`${partial} partly done`);
  if (progress.open) parts.push(`${progress.open} still open`);
  return parts.join(', ');
}

/** Wording for the carried-forward badge. */
export function deferredLabel(count) {
  if (!count) return '';
  if (count === 1) return 'Carried over once';
  return `Carried over ${count} times`;
}
