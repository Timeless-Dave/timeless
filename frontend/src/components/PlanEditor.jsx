import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '@/lib/api';
import {
  blocksFromTimeline,
  goalsFromOutcomes,
  newGoalId,
  outcomesFromGoals,
  timelineFromBlocks,
} from '@/lib/plan-form';

export default function PlanEditor({
  plan,
  planDay,
  minDay,
  academics,
  onDayChange,
  onSaved,
  showToast,
  showCalendarSync = true,
  compact = false,
}) {
  const [goals, setGoals] = useState(() => goalsFromOutcomes(plan?.outcomes));
  const [blocks, setBlocks] = useState(() => blocksFromTimeline(plan?.timeline));
  const [saving, setSaving] = useState(false);
  const loadedDay = useRef('');

  useEffect(() => {
    if (loadedDay.current === planDay && plan == null) return;
    loadedDay.current = planDay;
    setGoals(goalsFromOutcomes(plan?.outcomes));
    setBlocks(blocksFromTimeline(plan?.timeline));
  }, [planDay, plan]);

  const presetActive = useMemo(() => {
    const texts = new Set(
      goals.map(g => g.text.trim().toLowerCase()).filter(Boolean)
    );
    return new Set((academics?.presets || []).filter(p => texts.has(p.toLowerCase())));
  }, [goals, academics?.presets]);

  const togglePreset = preset => {
    const lower = preset.toLowerCase();
    const has = goals.some(g => g.text.trim().toLowerCase() === lower);
    if (has) {
      setGoals(prev => prev.filter(g => g.text.trim().toLowerCase() !== lower));
      return;
    }
    setGoals(prev => {
      const trimmed = prev.filter(g => g.text.trim());
      if (trimmed.some(g => g.text.trim().toLowerCase() === lower)) return prev;
      return [...trimmed, { id: newGoalId(), text: preset }];
    });
  };

  const updateGoal = (id, text) => {
    setGoals(prev => prev.map(g => (g.id === id ? { ...g, text } : g)));
  };

  const removeGoal = id => {
    setGoals(prev => {
      const next = prev.filter(g => g.id !== id);
      return next.length ? next : [{ id: newGoalId(), text: '' }];
    });
  };

  const addGoal = () => {
    setGoals(prev => [...prev, { id: newGoalId(), text: '' }]);
  };

  const updateBlock = (id, field, value) => {
    setBlocks(prev => prev.map(b => (b.id === id ? { ...b, [field]: value } : b)));
  };

  const removeBlock = id => {
    setBlocks(prev => {
      const next = prev.filter(b => b.id !== id);
      return next.length ? next : [{ id: newGoalId(), start: '09:00', end: '10:00', task: '' }];
    });
  };

  const addBlock = () => {
    setBlocks(prev => [...prev, { id: newGoalId(), start: '09:00', end: '10:00', task: '' }]);
  };

  const save = async () => {
    setSaving(true);
    try {
      const outcomes = outcomesFromGoals(goals);
      const timeline = timelineFromBlocks(blocks);
      await api('/api/plan', {
        method: 'POST',
        body: JSON.stringify({ outcomes, timeline, day: planDay }),
      });
      showToast?.('Plan saved.', 'mint');
      await onSaved?.();
    } catch (err) {
      showToast?.(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={`plan-editor${compact ? ' plan-editor--compact' : ''}`}>
      {!compact ? (
        <div className="card-head">
          <h2>Today</h2>
          <input type="date" value={planDay} min={minDay} onChange={e => onDayChange?.(e.target.value)} />
        </div>
      ) : (
        <label className="plan-editor__day">
          <span>Day</span>
          <input type="date" value={planDay} min={minDay} onChange={e => onDayChange?.(e.target.value)} />
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

      <div className="goal-section">
        <div className="goal-section__head">
          <div>
            <strong className="goal-section__title">Today&apos;s wins</strong>
            <p className="goal-section__hint">One line per outcome. Tap a preset or type your own.</p>
          </div>
          <button type="button" className="ghost small-btn" onClick={addGoal}>
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
            <li key={goal.id} className="goal-row">
              <span className="goal-row__index" aria-hidden="true">
                {index + 1}
              </span>
              <input
                type="text"
                value={goal.text}
                onChange={e => updateGoal(goal.id, e.target.value)}
                placeholder="Concrete win for today"
                aria-label={`Goal ${index + 1}`}
              />
              <button
                type="button"
                className="ghost goal-row__remove"
                onClick={() => removeGoal(goal.id)}
                aria-label={`Remove goal ${index + 1}`}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="block-section">
        <div className="goal-section__head">
          <div>
            <strong className="goal-section__title">Time blocks</strong>
            <p className="goal-section__hint">Shape the day in focused chunks.</p>
          </div>
          <button type="button" className="ghost small-btn" onClick={addBlock}>
            + Block
          </button>
        </div>
        <ul className="block-list">
          {blocks.map((block, index) => (
            <li key={block.id} className="block-row">
              <span className="block-row__index" aria-hidden="true">
                {index + 1}
              </span>
              <input
                type="time"
                value={block.start}
                onChange={e => updateBlock(block.id, 'start', e.target.value)}
                aria-label={`Block ${index + 1} start`}
              />
              <span className="block-row__sep">to</span>
              <input
                type="time"
                value={block.end}
                onChange={e => updateBlock(block.id, 'end', e.target.value)}
                aria-label={`Block ${index + 1} end`}
              />
              <input
                type="text"
                className="block-row__task"
                value={block.task}
                onChange={e => updateBlock(block.id, 'task', e.target.value)}
                placeholder="What you'll do"
                aria-label={`Block ${index + 1} focus`}
              />
              <button
                type="button"
                className="ghost block-row__remove"
                onClick={() => removeBlock(block.id)}
                aria-label={`Remove block ${index + 1}`}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="plan-editor__actions row">
        <button type="button" onClick={save} disabled={saving}>
          {saving ? 'Saving…' : compact ? 'Lock plan' : 'Save plan'}
        </button>
      </div>
    </div>
  );
}
