import { relTime } from '@/lib/summary';

/** How observed activity was bucketed against the plan. */
export const BUCKET = {
  aligned: { label: 'On plan', tone: 'mint' },
  productive_off_plan: { label: 'Useful detour', tone: 'cyan' },
  distracting: { label: 'Distraction', tone: 'rose' },
  unknown: { label: 'Unclassified', tone: 'neutral' },
};

export function bucketLabel(bucket) {
  return BUCKET[bucket]?.label || bucket || 'Unclassified';
}

export function bucketTone(bucket) {
  return BUCKET[bucket]?.tone || 'neutral';
}

const CONFIDENCE_NOTE = {
  low: 'Low confidence, treat as a rough hint.',
  medium: 'Medium confidence.',
  high: 'High confidence, though still an estimate.',
};

export function confidenceNote(productivity) {
  return CONFIDENCE_NOTE[productivity?.confidence] || CONFIDENCE_NOTE.low;
}

export function hasEstimate(productivity) {
  return productivity?.score != null;
}

/** Never render a bare percentage: the estimate always travels with its basis. */
export function alignmentHeadline(productivity) {
  if (!hasEstimate(productivity)) return 'Not enough activity to estimate yet';
  return `About ${productivity.score}% of judged time matched the plan`;
}

export function coverageNote(productivity) {
  const tracked = productivity?.tracked_minutes || 0;
  if (!tracked) return 'No activity observed on this Mac yet.';
  const judged = productivity.judged_minutes || 0;
  const unknown = productivity.minutes?.unknown || 0;
  const parts = [`${tracked} min observed`, `${judged} min judged`];
  if (unknown) parts.push(`${unknown} min unclassified`);
  return parts.join(' · ');
}

export function freshnessNote(productivity, now) {
  if (!productivity?.last_sample_at) return 'No signal yet today';
  return `Last signal ${relTime(productivity.last_sample_at, now)}`;
}

export function evidenceRows(productivity, limit = 4) {
  return (productivity?.evidence || []).slice(0, limit);
}

/** Minute splits worth charting, with absent measurements left absent. */
export function minuteSplit(productivity) {
  const minutes = productivity?.minutes;
  if (!minutes) return [];
  return Object.entries(BUCKET)
    .map(([key, meta]) => ({ key, label: meta.label, value: Math.round(minutes[key] || 0) }))
    .filter(entry => entry.value > 0);
}
