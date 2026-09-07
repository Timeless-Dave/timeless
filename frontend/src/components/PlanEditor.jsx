import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ArchivedGoals from '@/components/ArchivedGoals';
import { api } from '@/lib/api';
import {
  blocksFromPlan,
  emptyBlock,
  emptyGoal,
  goalsFromPlan,
  planPayload,
} from '@/lib/plan-form';
import { formatDuration, validatePlan } from '@/lib/plan-validation';
import { deferredLabel, statusLabel, statusTone } from '@/lib/goals';
import { usePlanDraft } from '@/hooks/usePlanDraft';

const SAVE_LABEL = { saved: 'Saved', unsaved: 'Unsaved changes', saving: 'Saving…' };

export default function PlanEditor({
  plan,
  planDay,
  minDay,
  academics,
  carryForward = [],
  meetings = [],
  onDayChange,
  onSaved,
  showToast,
  showCalendarSync = true,
  compact = false,
}) {
  const [goals, setGoals] = useState(() => goalsFromPlan(plan));
  const [blocks, setBlocks] = useState(() => blocksFromPlan(plan, goalsFromPlan(plan)));
  const [removed, setRemoved] = useState(null);
  const [saving, setSaving] = useState(false);
  const [serverError, setServerError] = useState('');
  const loadedDay = useRef('');
  const draft = usePlanDraft(planDay, plan?.updated_at);

  const applyPlan = useCallback(
    source => {
      const nextGoals = goalsFromPlan(source);
      setGoals(nextGoals);
      setBlocks(blocksFromPlan(source, nextGoals));
    },
    []
  );

  useEffect(() => {
    if (loadedDay.current === planDay && plan == null) return;
    loadedDay.current = planDay;
    setRemoved(null);
    setServerError('');
    const saved = draft.restore();
    if (saved?.goals?.length) {
      setGoals(saved.goals);
      setBlocks(saved.blocks || [emptyBlock()]);
      draft.setStatus('unsaved');
      showToast?.('Restored unsaved changes for this day.', 'cyan');
      return;
    }
    applyPlan(plan);
    draft.setStatus('saved');
    // `draft` is stable per day; re-running on its identity would loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [planDay, plan, applyPlan]);

  // Every edit funnels through here so dirty state and the draft stay in step.
  const edit = useCallback(
    (nextGoals, nextBlocks) => {
      if (nextGoals) setGoals(nextGoals);
      if (nextBlocks) setBlocks(nextBlocks);
      draft.save({ goals: nextGoals || goals, blocks: nextBlocks || blocks });
    },
    [draft, goals, blocks]
  );

  const validation = useMemo(
    () => validatePlan(goals, blocks, { meetings }),
    [goals, blocks, meetings]
  );

  const presetActive = useMemo(() => {
    const texts = new Set(goals.map(g => g.text.trim().toLowerCase()).filter(Boolean));
    return new Set((academics?.presets || []).filter(p => texts.has(p.toLowerCase())));
  }, [goals, academics?.presets]);

  const pending = useMemo(() => {
    const taken = new Set(goals.map(g => g.carriedFrom).filter(v => v != null));
    return (carryForward || []).filter(goal => !taken.has(goal.id));
  }, [carryForward, goals]);

  const addGoalRow = goal => edit([...goals.filter(g => g.text.trim()), goal]);

  const togglePreset = preset => {
    const lower = preset.toLowerCase();
    if (goals.some(g => g.text.trim().toLowerCase() === lower)) {
      edit(goals.filter(g => g.text.trim().toLowerCase() !== lower));
      return;
    }
    addGoalRow(emptyGoal({ text: preset }));
  };

  const carryGoal = goal =>
    addGoalRow(
      emptyGoal({ text: goal.text, carriedFrom: goal.id, deferredCount: (goal.deferred_count || 0) + 1 })
    );

  const updateGoal = (key, text) =>
    edit(goals.map(g => (g.key === key ? { ...g, text } : g)));

  const removeGoal = key => {
    const goal = goals.find(g => g.key === key);
    const detached = blocks.filter(b => b.goalKey === key).length;
    const next = goals.filter(g => g.key !== key);
    edit(
      next.length ? next : [emptyGoal()],
      blocks.map(b => (b.goalKey === key ? { ...b, goalKey: '' } : b))
    );
    setRemoved({ goal, detached, blockKeys: blocks.filter(b => b.goalKey === key).map(b => b.key) });
  };

  const undoRemove = () => {
    if (!removed) return;
    const index = goals.findIndex(g => !g.text.trim());
    const restored = [...goals.filter(g => g.text.trim() || goals.length === 1), removed.goal];
    edit(
      index >= 0 && goals.length === 1 ? [removed.goal] : restored,
      blocks.map(b => (removed.blockKeys.includes(b.key) ? { ...b, goalKey: removed.goal.key } : b))
    );
    setRemoved(null);
  };

  const updateBlock = (key, field, value) =>
    edit(null, blocks.map(b => (b.key === key ? { ...b, [field]: value } : b)));

  const removeBlock = key => {
    const next = blocks.filter(b => b.key !== key);
    edit(null, next.length ? next : [emptyBlock()]);
  };

  const addBlock = () => {
    const last = [...blocks].reverse().find(b => b.end);
    edit(null, [...blocks, emptyBlock(last ? { start: last.end, end: last.end } : {})]);
  };

  const changeDay = next => {
    if (draft.isDirty() && !window.confirm('You have unsaved changes for this day. Switch anyway?')) {
      return;
    }
    onDayChange?.(next);
  };

  const save = async () => {
    if (validation.errors.length) {
      showToast?.('Fix the schedule errors first.');
      return;
    }
    setSaving(true);
    draft.setStatus('saving');
    setServerError('');
    try {
      await api('/api/plan', {
        method: 'POST',
        body: JSON.stringify({ ...planPayload(goals, blocks), day: planDay }),
      });
      draft.clear();
      setRemoved(null);
      showToast?.('Plan saved.', 'mint');
      await onSaved?.();
    } catch (err) {
      setServerError(err.message);
      draft.setStatus('unsaved');
      showToast?.(err.message);
    } finally {
      setSaving(false);
    }
  };

  const issuesFor = key => validation.byKey.get(key) || [];
  const goalOptions = goals.filter(g => g.text.trim());
  const planTotal = formatDuration(validation.plannedMinutes);
  const globalIssues = [...validation.errors, ...validation.warnings].filter(issue => !issue.key);

  return (
    <div className={`plan-editor${compact ? ' plan-editor--compact' : ''}`}>
      {!compact ? (
        <div className="card-head">
          <h2>Plan</h2>
          <label className="plan-editor__day plan-editor__day--inline">
            <span className="visually-hidden">Plan day</span>
            <input type="date" value={planDay} min={minDay} onChange={e => changeDay(e.target.value)} />
          </label>
        </div>
      ) : (
        <label className="plan-editor__day">
          <span>Day</span>
          <input type="date" value={planDay} min={minDay} onChange={e => changeDay(e.target.value)} />
        </label>
      )}

      {!compact && showCalendarSync ? (
        <div className="semester-strip">
          <span>
            <strong>{academics?.name || 'Study presets'}</strong>
            {academics?.courses?.length ? `, ${academics.courses.length} courses` : ''}
          </span>
          <button
            type="button"
            className="ghost small-btn"
            onClick={async () => {
              try {
                const out = await api('/api/academics/calendar/sync', { method: 'POST' });
                showToast?.(`${out.total} ${out.semester} events synced.`, 'mint');
              } catch (err) {
                showToast?.(err.message);
              }
            }}
          >
            Add to Calendar
          </button>
        </div>
      ) : null}

      {pending.length ? (
        <div className="carry-forward">
          <p className="goal-section__hint">
            Unfinished from your last planned day. Pull anything still worth doing.
          </p>
          <div className="preset-chips" role="group" aria-label="Unfinished goals to carry forward">
            {pending.map(goal => (
              <button key={goal.id} type="button" className="ghost preset-chip" onClick={() => carryGoal(goal)}>
                {goal.text}
                {goal.deferred_count ? <em> · {deferredLabel(goal.deferred_count)}</em> : null}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="goal-section">
        <div className="goal-section__head">
          <div>
            <strong className="goal-section__title">Today&apos;s wins</strong>
            <p className="goal-section__hint">One line per outcome. Tap a preset or type your own.</p>
          </div>
          <button type="button" className="ghost small-btn" onClick={() => edit([...goals, emptyGoal()])}>
            + Goal
          </button>
        </div>

        {(academics?.presets || []).length ? (
          <div className="preset-chips" role="group" aria-label="Study presets">
            {(academics.presets || []).map(preset => (
              <button
                key={preset}
                type="button"
                className={`ghost preset-chip${presetActive.has(preset) ? ' on' : ''}`}
                aria-pressed={presetActive.has(preset)}
                onClick={() => togglePreset(preset)}
              >
                {preset}
              </button>
            ))}
          </div>
        ) : null}

        <ul className="goal-list">
          {goals.map((goal, index) => (
            <li key={goal.key} className="goal-row">
              <span className="goal-row__index" aria-hidden="true">
                {index + 1}
              </span>
              <input
                type="text"
                value={goal.text}
                onChange={e => updateGoal(goal.key, e.target.value)}
                placeholder="Concrete win for today"
                aria-label={`Goal ${index + 1}`}
              />
              {goal.id && goal.status !== 'planned' ? (
                <span className={`chip ${statusTone(goal.status)}`}>{statusLabel(goal.status)}</span>
              ) : null}
              {goal.carriedFrom ? (
                <span className="goal-row__carried">{deferredLabel(goal.deferredCount)}</span>
              ) : null}
              <button
                type="button"
                className="ghost goal-row__remove"
                onClick={() => removeGoal(goal.key)}
                aria-label={`Remove goal ${index + 1}`}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>

        {removed?.goal ? (
          <div className="undo-strip" role="status">
            <span>
              Removed “{removed.goal.text || 'empty goal'}”.
              {removed.detached
                ? ` ${removed.detached} time block${removed.detached === 1 ? '' : 's'} no longer point at it.`
                : ''}
              {removed.goal.id ? ' Its history is kept.' : ''}
            </span>
            <button type="button" className="ghost small-btn" onClick={undoRemove}>
              Undo
            </button>
          </div>
        ) : null}
      </div>

      <ArchivedGoals
        key={`${planDay}-${plan?.updated_at || ''}`}
        day={planDay}
        onRestored={onSaved}
        showToast={showToast}
      />

      <div className="block-section">
        <div className="goal-section__head">
          <div>
            <strong className="goal-section__title">Time blocks</strong>
            <p className="goal-section__hint">
              Optional. Shape the day in focused chunks, and say which goal each one serves.
            </p>
          </div>
          <div className="block-section__meta">
            <span className="plan-total">{planTotal} planned</span>
            <button type="button" className="ghost small-btn" onClick={addBlock}>
              + Block
            </button>
          </div>
        </div>
        <ul className="block-list">
          {blocks.map((block, index) => {
            const issues = issuesFor(block.key);
            const hasError = validation.errors.some(issue => issue.key === block.key);
            // Screen readers hear the reason, not just that a field is invalid.
            const issuesId = issues.length ? `block-issues-${block.key}` : undefined;
            const describe = field =>
              issues.some(issue => issue.field === field) ? issuesId : undefined;
            return (
              <li key={block.key} className={`block-row${hasError ? ' block-row--error' : ''}`}>
                <span className="block-row__index" aria-hidden="true">
                  {index + 1}
                </span>
                <input
                  type="time"
                  value={block.start}
                  aria-invalid={validation.errors.some(i => i.key === block.key && i.field === 'start')}
                  aria-describedby={describe('start')}
                  onChange={e => updateBlock(block.key, 'start', e.target.value)}
                  aria-label={`Block ${index + 1} start`}
                />
                <span className="block-row__sep">to</span>
                <input
                  type="time"
                  value={block.end}
                  aria-invalid={validation.errors.some(i => i.key === block.key && i.field === 'end')}
                  aria-describedby={describe('end')}
                  onChange={e => updateBlock(block.key, 'end', e.target.value)}
                  aria-label={`Block ${index + 1} end`}
                />
                <input
                  type="text"
                  className="block-row__task"
                  value={block.task}
                  onChange={e => updateBlock(block.key, 'task', e.target.value)}
                  placeholder="What you'll do"
                  aria-label={`Block ${index + 1} focus`}
                />
                <select
                  className="block-row__goal"
                  value={block.goalKey}
                  onChange={e => updateBlock(block.key, 'goalKey', e.target.value)}
                  aria-label={`Block ${index + 1} goal`}
                >
                  <option value="">No goal</option>
                  {goalOptions.map(goal => (
                    <option key={goal.key} value={goal.key}>
                      {goal.text}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="ghost block-row__remove"
                  onClick={() => removeBlock(block.key)}
                  aria-label={`Remove block ${index + 1}`}
                >
                  Remove
                </button>
                {issues.length ? (
                  <ul className="block-row__issues" id={issuesId}>
                    {issues.map(issue => (
                      <li
                        key={issue.message}
                        className={
                          validation.errors.includes(issue) ? 'issue issue--error' : 'issue issue--warning'
                        }
                      >
                        {issue.message}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </li>
            );
          })}
        </ul>
      </div>

      {globalIssues.length ? (
        <ul className="plan-issues" role={validation.errors.length ? 'alert' : undefined}>
          {globalIssues.map(issue => (
            <li
              key={issue.message}
              className={validation.errors.includes(issue) ? 'issue issue--error' : 'issue issue--warning'}
            >
              {issue.message}
            </li>
          ))}
        </ul>
      ) : null}

      {serverError ? (
        <p className="issue issue--error" role="alert">
          {serverError}
        </p>
      ) : null}

      <div className="plan-editor__actions row">
        <button type="button" onClick={save} disabled={saving || validation.errors.length > 0}>
          {saving ? 'Saving…' : 'Save plan'}
        </button>
        <span className={`save-status save-status--${draft.status}`} role="status">
          {validation.errors.length
            ? `${validation.errors.length} problem${validation.errors.length === 1 ? '' : 's'} to fix`
            : SAVE_LABEL[draft.status]}
        </span>
      </div>
    </div>
  );
}
