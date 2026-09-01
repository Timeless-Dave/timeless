let goalSeq = 0;

export function newGoalId() {
  goalSeq += 1;
  return `goal-${goalSeq}-${Date.now()}`;
}

export function goalsFromOutcomes(outcomes) {
  const lines = String(outcomes || '')
    .split('\n')
    .map(s => s.trim())
    .filter(Boolean);
  if (!lines.length) return [{ id: newGoalId(), text: '' }];
  return lines.map(text => ({ id: newGoalId(), text }));
}

export function outcomesFromGoals(goals) {
  return (goals || [])
    .map(g => (typeof g === 'string' ? g : g.text).trim())
    .filter(Boolean)
    .join('\n');
}

export function blocksFromTimeline(timeline) {
  if (timeline?.length) {
    return timeline.map(b => ({
      id: newGoalId(),
      start: b.start || '09:00',
      end: b.end || '10:00',
      task: b.task || '',
    }));
  }
  return [{ id: newGoalId(), start: '09:00', end: '10:00', task: '' }];
}

export function timelineFromBlocks(blocks) {
  return (blocks || [])
    .map(b => ({
      start: b.start,
      end: b.end,
      task: (b.task || '').trim(),
    }))
    .filter(b => b.task);
}
