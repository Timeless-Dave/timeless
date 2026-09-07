let rowSeq = 0;

/** Client-side row key. Server goal ids are separate and live in `id`. */
export function newRowKey() {
  rowSeq += 1;
  return `row-${rowSeq}-${Date.now()}`;
}

function cleanLine(line) {
  return line.replace(/^\s*(?:[-•]|\d+[.)])\s*/, '').trim();
}

export function emptyGoal(overrides = {}) {
  return {
    key: newRowKey(),
    id: null,
    text: '',
    nextStep: '',
    status: 'planned',
    note: null,
    carriedFrom: null,
    deferredCount: 0,
    templateKey: null,
    ...overrides,
  };
}

export function emptyBlock(overrides = {}) {
  return {
    key: newRowKey(),
    // Server identity. A block's run history hangs off this, so it must survive
    // every edit; losing it orphans recorded work.
    blockId: null,
    start: '09:00',
    end: '10:00',
    task: '',
    goalKey: '',
    ...overrides,
  };
}

/** Goals for the editor, preferring stored rows over the legacy outcomes blob. */
export function goalsFromPlan(plan) {
  if (plan?.goals?.length) {
    return plan.goals.map(goal =>
      emptyGoal({
        id: goal.id,
        text: goal.text || '',
        nextStep: goal.next_step || '',
        status: goal.status || 'planned',
        note: goal.note || null,
        carriedFrom: goal.carried_from ?? null,
        deferredCount: goal.deferred_count || 0,
      })
    );
  }
  const lines = String(plan?.outcomes || '')
    .split(/\n|;/)
    .map(cleanLine)
    .filter(Boolean);
  if (!lines.length) return [emptyGoal()];
  return lines.map(text => emptyGoal({ text }));
}

export function blocksFromPlan(plan, goals) {
  const byId = new Map((goals || []).filter(goal => goal.id != null).map(goal => [goal.id, goal.key]));
  if (plan?.timeline?.length) {
    return plan.timeline.map(block =>
      emptyBlock({
        blockId: block.block_id || null,
        start: block.start || '09:00',
        end: block.end || '10:00',
        task: block.task || '',
        goalKey: byId.get(block.goal_id) || '',
      })
    );
  }
  return [emptyBlock()];
}

/** The request body for POST /api/plan. */
export function planPayload(goals, blocks) {
  const kept = (goals || []).filter(goal => goal.text.trim());
  const indexByKey = new Map(kept.map((goal, index) => [goal.key, index]));
  return {
    outcomes: kept.map(goal => goal.text.trim()).join('\n'),
    goals: kept.map(goal => ({
      id: goal.id ?? undefined,
      text: goal.text.trim(),
      next_step: goal.nextStep?.trim() || undefined,
      status: goal.status || 'planned',
      note: goal.note || undefined,
      carried_from: goal.carriedFrom ?? undefined,
    })),
    timeline: (blocks || [])
      .filter(block => (block.task || '').trim())
      .map(block => {
        const index = indexByKey.get(block.goalKey);
        return {
          ...(block.blockId ? { block_id: block.blockId } : {}),
          start: block.start,
          end: block.end,
          task: block.task.trim(),
          ...(index == null ? {} : { goal_index: index }),
        };
      }),
  };
}
