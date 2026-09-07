/** Feasibility rules for a day's plan, mirroring src/timeless/planning.py.
 * Errors block the save; warnings inform it. */

const TIME = /^(\d{1,2}):(\d{2})$/;

export const DEFAULT_CAPACITY_MINUTES = 10 * 60;
const LONG_BLOCK_MINUTES = 4 * 60;
const BUSY_GOAL_COUNT = 6;

export function minutesOfDay(value) {
  const match = TIME.exec(String(value || '').trim());
  if (!match) return null;
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (hours > 23 || minutes > 59) return null;
  return hours * 60 + minutes;
}

function span(block) {
  const start = minutesOfDay(block.start);
  const end = minutesOfDay(block.end);
  return start == null || end == null ? null : { start, end };
}

export function plannedMinutes(blocks) {
  return (blocks || []).reduce((total, block) => {
    const s = span(block);
    return s && s.end > s.start ? total + (s.end - s.start) : total;
  }, 0);
}

export function formatDuration(minutes) {
  if (!minutes) return '0h';
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (!hours) return `${rest}m`;
  return rest ? `${hours}h ${rest}m` : `${hours}h`;
}

function meetingMinutes(stamp) {
  const text = String(stamp || '');
  if (!text.includes('T')) return null;
  const local = new Date(text.endsWith('Z') ? text : `${text}Z`);
  return Number.isNaN(local.getTime()) ? null : local.getHours() * 60 + local.getMinutes();
}

/**
 * All issues for a plan, keyed to the row that caused them.
 * @returns {{errors: object[], warnings: object[], byKey: Map<string, object[]>}}
 */
export function validatePlan(goals, blocks, { meetings, capacityMinutes = DEFAULT_CAPACITY_MINUTES } = {}) {
  const rows = (blocks || []).filter(block => (block.task || '').trim());
  const errors = [];
  const warnings = [];
  const spans = [];

  rows.forEach((block, index) => {
    const s = span(block);
    if (!s) return;
    if (s.end <= s.start) {
      errors.push({ key: block.key, field: 'end', message: `Block ${index + 1} ends before it starts.` });
      return;
    }
    spans.push({ ...s, index, key: block.key });
    if (s.end - s.start > LONG_BLOCK_MINUTES) {
      warnings.push({
        key: block.key,
        field: 'end',
        message: `${formatDuration(s.end - s.start)} without a break.`,
      });
    }
  });

  const ordered = [...spans].sort((a, b) => a.start - b.start);
  for (let i = 0; i < ordered.length - 1; i += 1) {
    const current = ordered[i];
    const next = ordered[i + 1];
    if (next.start < current.end) {
      errors.push({
        key: next.key,
        field: 'start',
        message: `Overlaps block ${current.index + 1}.`,
      });
    }
  }

  spans.forEach(block => {
    const clash = (meetings || []).find(meeting => {
      const start = meetingMinutes(meeting.start_at);
      const end = meetingMinutes(meeting.end_at);
      return start != null && end != null && start < block.end && block.start < end;
    });
    if (clash) {
      warnings.push({
        key: block.key,
        field: 'start',
        message: `Overlaps “${clash.title || 'a calendar event'}”.`,
      });
    }
  });

  const total = plannedMinutes(rows);
  if (total > capacityMinutes) {
    warnings.push({
      field: 'capacity',
      message: `${formatDuration(total)} planned. That is more than most days hold.`,
    });
  }

  const liveGoals = (goals || []).filter(goal => (goal.text || '').trim());
  if (!liveGoals.length) {
    // The one thing a plan cannot do without. Caught here so the save button
    // reports it inline instead of the server rejecting the work afterwards.
    errors.push({ field: 'goals', message: 'Add at least one goal for the day.' });
  }
  if (liveGoals.length > BUSY_GOAL_COUNT) {
    warnings.push({
      field: 'goals',
      message: `${liveGoals.length} goals for one day. Consider which ones truly matter.`,
    });
  }

  const byKey = new Map();
  [...errors, ...warnings].forEach(issue => {
    if (!issue.key) return;
    byKey.set(issue.key, [...(byKey.get(issue.key) || []), issue]);
  });

  return { errors, warnings, byKey, plannedMinutes: total };
}
