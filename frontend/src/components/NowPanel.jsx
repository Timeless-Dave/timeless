import { useMemo, useState } from 'react';
import GoalActions from '@/components/GoalActions';
import MenuButton from '@/components/MenuButton';
import NoteDialog from '@/components/NoteDialog';
import { useChatPanel } from '@/components/chat-context';
import { useNotePrompt } from '@/hooks/useNotePrompt';
import { api } from '@/lib/api';
import {
  STATUS_HELP,
  deferredLabel,
  goalActions,
  goalProgressLabel,
  statusLabel,
  statusTone,
} from '@/lib/goals';
import { alignmentHeadline, confidenceNote, coverageNote, freshnessNote } from '@/lib/evidence';
import { currentBlocks, nextMeeting, relTime } from '@/lib/summary';
import { formatDuration } from '@/lib/plan-validation';

function runOf(runs, blockId) {
  return (runs || []).find(run => run.block_id === blockId) || null;
}

function GoalRow({ goal, busy, onStatus, minutes }) {
  const carried = deferredLabel(goal.deferred_count);
  return (
    <li className={`now-goal now-goal--${goal.status}`}>
      <div className="now-goal__body">
        <span className="now-goal__text">{goal.text}</span>
        <span className="now-goal__meta">
          <span className={`chip ${statusTone(goal.status)}`} title={STATUS_HELP[goal.status]}>
            {statusLabel(goal.status)}
          </span>
          {minutes ? <span className="now-goal__minutes">{formatDuration(minutes)} observed</span> : null}
          {carried ? <span className="now-goal__carried">{carried}</span> : null}
          {goal.note ? <span className="now-goal__note">{goal.note}</span> : null}
        </span>
      </div>
      <GoalActions goal={goal} busy={busy} onStatus={onStatus} />
    </li>
  );
}

export default function NowPanel({ today, plan, onRefresh, showToast, onOpenPlan }) {
  const { openChat } = useChatPanel();
  const { ask, dialogProps } = useNotePrompt();
  const [busyGoal, setBusyGoal] = useState(null);
  const [busyBlock, setBusyBlock] = useState(null);
  const [busyWork, setBusyWork] = useState(false);
  const goals = useMemo(() => plan?.goals || [], [plan]);
  const progress = today?.goal_progress || plan?.goal_progress || {};
  const productivity = today?.productivity || {};
  const goalMinutes = productivity.goal_minutes || {};
  const work = today?.active_work || {};
  // The server reconciles goal, block and focus; recomputing either here is what
  // let the headline and the action beneath it describe different work.
  const focus = work.goal || null;
  const nextAction = work.next_action || null;
  const { active: activeBlock, next: nextBlock, remaining } = useMemo(
    () => currentBlocks(plan?.timeline),
    [plan]
  );
  const meeting = today ? nextMeeting(today.meetings) : null;
  const runs = plan?.block_runs || [];
  const activeRun = activeBlock ? runOf(runs, activeBlock.block_id) : null;
  const day = today?.day;
  const isWorkingOnFocus = !!work.running_block && work.goal?.id === focus?.id;
  const showExplicitStart = focus && ['planned', 'deferred'].includes(focus.status || 'planned');
  const focusMoreActions = focus ? goalActions(focus).more : [];

  /** Goal, block and focus are set in one move so they cannot drift apart.
   * An existing focus session follows the work rather than being re-requested. */
  const startWork = async (goal, { focusMinutes } = {}) => {
    setBusyWork(true);
    try {
      await api('/api/work/start', {
        method: 'POST',
        body: JSON.stringify({
          day,
          goal_id: goal?.id ?? undefined,
          focus_minutes: focusMinutes,
        }),
      });
      await onRefresh?.({ force: true });
      showToast?.(`Working on “${goal.text}”.`, 'mint');
    } catch (err) {
      showToast?.(err.message);
    } finally {
      setBusyWork(false);
    }
  };

  const setStatus = async (goal, action) => {
    // Making a goal active is an execution change, not just a status change:
    // routing it through the same reconciliation as "Start work" is what stops
    // another goal's block from carrying on underneath it.
    if (action.status === 'active') {
      await startWork(goal);
      return;
    }
    let note = action.note;
    if (action.needsNote) {
      note = await ask({
        title: `${action.label}: ${goal.text}`,
        hint: 'A sentence here is what makes the day reviewable later.',
        confirmLabel: action.label,
        initialValue: goal.note || '',
      });
      if (note === null) return;
    }
    setBusyGoal(goal.id);
    try {
      await api(`/api/goals/${goal.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: action.status, note }),
      });
      await onRefresh?.({ force: true });
      showToast?.(`${goal.text} — ${statusLabel(action.status).toLowerCase()}.`, 'mint');
    } catch (err) {
      showToast?.(err.message);
    } finally {
      setBusyGoal(null);
    }
  };

  const blockAction = async (block, action) => {
    if (!block?.block_id) return;
    setBusyBlock(block.block_id);
    try {
      await api(`/api/blocks/${encodeURIComponent(block.block_id)}/${action}`, {
        method: 'POST',
        body: JSON.stringify({ day, goal_id: block.goal_id ?? undefined }),
      });
      await onRefresh?.({ force: true });
    } catch (err) {
      showToast?.(err.message);
    } finally {
      setBusyBlock(null);
    }
  };

  const stopWork = async () => {
    setBusyWork(true);
    try {
      await api('/api/work/stop', { method: 'POST', body: JSON.stringify({ day }) });
      await onRefresh?.({ force: true });
      showToast?.('Work stopped. Nothing was judged.', 'mint');
    } catch (err) {
      showToast?.(err.message);
    } finally {
      setBusyWork(false);
    }
  };

  const resolveConflict = async conflict => {
    setBusyWork(true);
    try {
      if (conflict.action === 'finish_block') {
        await api(`/api/blocks/${encodeURIComponent(conflict.block_id)}/finish`, {
          method: 'POST',
          body: JSON.stringify({ day }),
        });
      } else {
        await api('/api/work/start', {
          method: 'POST',
          body: JSON.stringify({
            day,
            goal_id: conflict.goal_id ?? undefined,
            block_id: conflict.block_id ?? undefined,
          }),
        });
      }
      await onRefresh?.({ force: true });
    } catch (err) {
      showToast?.(err.message);
    } finally {
      setBusyWork(false);
    }
  };

  if (!plan) {
    return (
      <section className="now-panel" id="now" aria-labelledby="now-title">
        <div className="now-panel__head">
          <h2 id="now-title">Now</h2>
        </div>
        <p className="now-panel__empty">
          No plan for this day yet. Set the outcomes that would make today count.
        </p>
        <button type="button" onClick={onOpenPlan}>
          Plan this day
        </button>
        {dialogProps.open ? <NoteDialog key={dialogProps.requestId} {...dialogProps} /> : null}
      </section>
    );
  }

  return (
    <section className="now-panel" id="now" aria-labelledby="now-title">
      <div className="now-panel__head">
        <h2 id="now-title">Now</h2>
        <span className="now-panel__progress">{goalProgressLabel(progress)}</span>
      </div>

      <div className="now-panel__focus">
        {focus ? (
          <>
            <p className="now-panel__kicker">
              {focus.status === 'active' ? 'Working on' : 'Next goal'}
            </p>
            <p className="now-panel__goal">{focus.text}</p>
            {nextAction ? (
              <p className="now-panel__next">
                Next action: {nextAction.text}
                {nextAction.source === 'goal' && focus?.text === nextAction.text ? (
                  <span className="now-panel__dim"> · add a next step in your plan</span>
                ) : null}
                {nextAction.minutes_left != null ? (
                  <span className="now-panel__dim"> · {nextAction.minutes_left} min left</span>
                ) : null}
                {nextAction.starts_at ? (
                  <span className="now-panel__dim"> · from {nextAction.starts_at}</span>
                ) : null}
              </p>
            ) : null}
            <div className="now-panel__actions">
              {isWorkingOnFocus ? (
                <>
                  <GoalActions goal={focus} busy={busyGoal === focus.id} onStatus={setStatus} size="large" />
                  <button type="button" className="ghost" disabled={busyWork} onClick={stopWork}>
                    Stop work
                  </button>
                </>
              ) : showExplicitStart ? (
                <>
                  <button type="button" disabled={busyWork} onClick={() => startWork(focus)}>
                    Start
                  </button>
                  <MenuButton label="More" disabled={busyWork || busyGoal === focus.id}>
                    <button
                      type="button"
                      role="menuitem"
                      tabIndex={-1}
                      className="menu-item"
                      onClick={() => startWork(focus, { focusMinutes: 60 })}
                    >
                      Start with 60m focus
                    </button>
                    {focusMoreActions.map(action => (
                      <button
                        key={action.status}
                        type="button"
                        role="menuitem"
                        tabIndex={-1}
                        className="menu-item"
                        onClick={() => setStatus(focus, action)}
                      >
                        {action.label}
                      </button>
                    ))}
                  </MenuButton>
                </>
              ) : (
                <GoalActions goal={focus} busy={busyGoal === focus.id} onStatus={setStatus} size="large" />
              )}
            </div>
          </>
        ) : (
          <>
            <p className="now-panel__kicker">All goals settled</p>
            <p className="now-panel__goal">Every goal for today has an outcome.</p>
          </>
        )}
      </div>

      {work.conflicts?.length ? (
        <ul className="work-conflicts" aria-label="Work state needs attention">
          {work.conflicts.map(conflict => (
            <li key={`${conflict.kind}-${conflict.block_id ?? conflict.goal_id}`}>
              <span>{conflict.message}</span>
              <button
                type="button"
                className="ghost small-btn"
                disabled={busyWork}
                onClick={() => resolveConflict(conflict)}
              >
                {conflict.action === 'finish_block' ? 'Finish it' : 'Switch to it'}
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <dl className="now-panel__facts">
        <div>
          <dt>Time block</dt>
          <dd>
            {activeBlock ? (
              <>
                <span>
                  {activeBlock.task} · {remaining} min left
                </span>
                {activeRun?.elapsed_seconds ? (
                  <span className="now-panel__dim">
                    {formatDuration(Math.round(activeRun.elapsed_seconds / 60))} tracked
                  </span>
                ) : null}
                <span className="now-panel__block-actions">
                  {activeRun?.state === 'running' ? (
                    <button
                      type="button"
                      className="ghost small-btn"
                      disabled={busyBlock === activeBlock.block_id}
                      onClick={() => blockAction(activeBlock, 'pause')}
                    >
                      Pause
                    </button>
                  ) : activeRun?.state === 'done' ? (
                    <span className="chip mint">Finished</span>
                  ) : (
                    <button
                      type="button"
                      className="ghost small-btn"
                      disabled={busyBlock === activeBlock.block_id}
                      onClick={() => blockAction(activeBlock, 'start')}
                    >
                      {activeRun ? 'Resume' : 'Start block'}
                    </button>
                  )}
                  {activeRun?.state !== 'done' ? (
                    <button
                      type="button"
                      className="ghost small-btn"
                      disabled={busyBlock === activeBlock.block_id}
                      onClick={() => blockAction(activeBlock, 'finish')}
                    >
                      Finish
                    </button>
                  ) : null}
                </span>
              </>
            ) : nextBlock ? (
              <span>
                Next: {nextBlock.task} at {nextBlock.start}
              </span>
            ) : (
              <span>No block scheduled for now</span>
            )}

          </dd>
        </div>
        <div>
          <dt>Next event</dt>
          <dd>
            {meeting ? (
              <>
                <span>{meeting.title}</span>
                <span className="now-panel__dim">{relTime(meeting.start_at)}</span>
                {meeting.join_url ? (
                  <button
                    type="button"
                    className="ghost small-btn"
                    onClick={async () => {
                      try {
                        await api(`/api/meetings/${meeting.id}/join`, { method: 'POST', body: '{}' });
                        await onRefresh?.({ force: true });
                      } catch (err) {
                        showToast?.(err.message);
                      }
                    }}
                  >
                    Join
                  </button>
                ) : (
                  <span className="now-panel__dim">{meeting.location || 'No join link'}</span>
                )}
              </>
            ) : (
              <span>Nothing scheduled</span>
            )}
          </dd>
        </div>
        <div>
          <dt>Activity evidence</dt>
          <dd>
            <span className="now-panel__dim">{freshnessNote(productivity)}</span>
          </dd>
        </div>
      </dl>

      {goals.length ? (
        <>
          <h3 className="now-panel__subhead">Today&apos;s goals</h3>
          <ul className="now-goals">
            {goals.map(goal => (
              <GoalRow
                key={goal.id}
                goal={goal}
                busy={busyGoal === goal.id}
                onStatus={setStatus}
                minutes={goalMinutes[String(goal.id)] || 0}
              />
            ))}
          </ul>
        </>
      ) : null}

      <div className="now-panel__foot">
        <button type="button" className="ghost small-btn" onClick={onOpenPlan}>
          Edit plan
        </button>
        <button type="button" className="ghost small-btn" onClick={openChat}>
          Ask Timeless
        </button>
        <span className="now-panel__estimate" title={confidenceNote(productivity)}>
          {alignmentHeadline(productivity)} · {coverageNote(productivity)}
        </span>
      </div>

      {dialogProps.open ? <NoteDialog key={dialogProps.requestId} {...dialogProps} /> : null}
    </section>
  );
}
