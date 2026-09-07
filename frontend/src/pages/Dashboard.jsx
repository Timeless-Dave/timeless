import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import BentoAnalytics from '@/components/BentoAnalytics';
import Cubes from '@/components/Cubes';
import DashboardBackground from '@/components/DashboardBackground';
import EffectsShell from '@/components/EffectsShell';
import InfiniteSpiral from '@/components/InfiniteSpiral';
import NowPanel from '@/components/NowPanel';
import PlanEditor from '@/components/PlanEditor';
import PillNav from '@/components/PillNav';
import SideRays from '@/components/SideRays';
import { ChatProvider } from '@/components/ChatSidebar';
import { useToday } from '@/context/today-context';
import { useGpuBudget } from '@/hooks/useGpuBudget';
import { setEffectsMode } from '@/lib/gpu-budget';
import { useBreakpoint, useReducedMotion, useViewportSize } from '@/hooks/useReducedMotion';
import { useThemeControls } from '@/hooks/useThemeControls';
import { api } from '@/lib/api';
import { alignmentHeadline, bucketLabel, bucketTone, confidenceNote, coverageNote, evidenceRows, freshnessNote } from '@/lib/evidence';
import { goalProgressLabel } from '@/lib/goals';
import { TODAY_NAV, navClickHandler, scrollToHash } from '@/lib/nav';
import { heatTile, streakGrid } from '@/lib/tiles';
import {
  approvalsSummary,
  eventsSummary,
  focusLabel,
  formatPageDate,
  mailSummary,
  programSummary,
  sensorSummary,
} from '@/lib/summary';

const LOGO = '/favicon.svg';

export default function Dashboard({ showToast }) {
  const { today, academics, error, refresh } = useToday();
  const navigate = useNavigate();
  const reduce = useReducedMotion();
  const gpu = useGpuBudget();
  const quietGpu = gpu.quiet;
  const breakpoint = useBreakpoint();
  const { width: viewportWidth } = useViewportSize();
  const theme = useThemeControls();
  const [activeNav, setActiveNav] = useState('#now');
  // The editor shows today unless a different date is chosen, so the selection
  // is derived rather than synchronised into state by an effect.
  const [chosenDay, setChosenDay] = useState('');
  const [viewPlan, setViewPlan] = useState(null);
  const [focusOpen, setFocusOpen] = useState(false);
  const [notifyOpen, setNotifyOpen] = useState(false);
  const [themeOpen, setThemeOpen] = useState(false);
  const [focusLevel, setFocusLevel] = useState('quiet');
  const [focusMin, setFocusMin] = useState(60);
  const [refreshing, setRefreshing] = useState(false);
  const [showAnalytics, setShowAnalytics] = useState(false);
  const [planOpen, setPlanOpen] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [rhythmOpen, setRhythmOpen] = useState(false);
  const planRequest = useRef(0);

  const isMobile = breakpoint === 'mobile';

  const statusTrigger = useRef(null);
  const focusTrigger = useRef(null);
  const themeTrigger = useRef(null);

  const closePops = useCallback(() => {
    setNotifyOpen(false);
    setFocusOpen(false);
    setThemeOpen(false);
  }, []);

  // Escape returns focus to whichever trigger opened the popover.
  const dismissPops = useCallback(() => {
    const open = [
      [notifyOpen, statusTrigger],
      [focusOpen, focusTrigger],
      [themeOpen, themeTrigger],
    ].find(([isOpen]) => isOpen);
    closePops();
    open?.[1].current?.focus();
  }, [closePops, notifyOpen, focusOpen, themeOpen]);

  useEffect(() => {
    const onKey = e => {
      if (e.key === 'Escape') dismissPops();
    };
    const onPointerDown = e => {
      if (!e.target.closest('.pop-wrap')) closePops();
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('pointerdown', onPointerDown);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('pointerdown', onPointerDown);
    };
  }, [closePops, dismissPops]);

  useEffect(() => {
    const sections = TODAY_NAV.filter(item => item.href.startsWith('#'))
      .map(item => document.getElementById(item.href.slice(1)))
      .filter(Boolean);
    if (!sections.length) return undefined;
    const observer = new IntersectionObserver(
      entries => {
        const visible = entries
          .filter(entry => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (visible) setActiveNav(`#${visible.target.id}`);
      },
      { rootMargin: '-20% 0px -70% 0px' }
    );
    sections.forEach(section => observer.observe(section));
    return () => observer.disconnect();
  }, [today]);

  const planDay = chosenDay || today?.day || '';

  const plan = useMemo(() => {
    if (!today) return null;
    if (planDay === today.day) return today.plan;
    return viewPlan;
  }, [today, planDay, viewPlan]);

  const loadPlanDay = useCallback(
    async day => {
      setChosenDay(day);
      // Flipping through dates fires overlapping requests; only the newest wins.
      const request = ++planRequest.current;
      if (day !== today?.day) {
        const p = await api('/api/plan?day=' + encodeURIComponent(day));
        if (request === planRequest.current) setViewPlan(p);
      } else setViewPlan(null);
    },
    [today?.day]
  );

  const navKey = `${breakpoint}-${Math.round(viewportWidth / 120)}`;

  const heatMax = useMemo(() => Math.max(1, ...(today?.heatmap || []).map(d => d.count || 0)), [today]);

  const streak = useMemo(() => streakGrid(today?.heatmap, 7, heatMax), [today, heatMax]);

  const heatSpiralItems = useMemo(
    () =>
      (today?.heatmap || []).slice(-7).map(d => ({
        src: heatTile(d, heatMax),
        alt: `${d.day}: ${d.count || 0} events`,
      })),
    [today, heatMax]
  );

  if (!today && !error) {
    return (
      <EffectsShell>
        <div className="app-shell">
          <div className="shell-card">
            <div className="shell-content" style={{ alignItems: 'center', justifyContent: 'center' }}>
              <p>Loading Timeless…</p>
            </div>
          </div>
        </div>
      </EffectsShell>
    );
  }

  const productivity = today?.productivity || {};
  const progress = today?.goal_progress || {};
  const evidenceItems = evidenceRows(productivity);
  const goalCount = progress.counted || 0;
  const meetingCount = today?.meetings?.length || 0;
  const approvalCount = today?.approvals?.length || 0;
  const hasAlignment = productivity.score != null;
  const showEvidence = evidenceItems.length > 0 || hasAlignment;
  const summaryBits = [
    goalCount ? `${progress.done || 0}/${goalCount} goals` : null,
    meetingCount ? `${meetingCount} event${meetingCount === 1 ? '' : 's'}` : null,
    approvalCount ? `${approvalCount} approval${approvalCount === 1 ? '' : 's'}` : null,
    hasAlignment ? `~${productivity.score}% aligned` : null,
  ].filter(Boolean);

  const openPlan = () => {
    setPlanOpen(true);
    scrollToHash('#panel-plan');
  };

  return (
    <ChatProvider onRefresh={refresh}>
    <EffectsShell>
      <DashboardBackground />
      <div className="app-shell">
        <div className="shell-card">
          <div className="shell-content">
          <div
            className="pill-nav-slot"
            onClick={navClickHandler(navigate, setActiveNav)}
          >
            <PillNav
              key={navKey}
              logo={LOGO}
              logoAlt="Timeless"
              items={TODAY_NAV}
              activeHref={activeNav}
              baseColor="#303030"
              pillColor="#ffffff"
              pillTextColor="#303030"
              hoveredPillTextColor="#ffffff"
              initialLoadAnimation={!reduce}
            />
          </div>

          <div className="page-wrap">
            <header className="page-head">
              <div>
                <h1 className="page-title">Day overview</h1>
                <p className="page-date">{today ? formatPageDate(today.day) : '…'}</p>
              </div>
              <div className="head-tools">
                <button
                  type="button"
                  className="ghost"
                  disabled={refreshing}
                  onClick={async () => {
                    setRefreshing(true);
                    try {
                      await refresh({ force: true });
                      showToast('Dashboard refreshed.', 'mint');
                    } catch (err) {
                      showToast(err.message);
                    } finally {
                      setRefreshing(false);
                    }
                  }}
                >
                  Refresh
                </button>
                <div className="pop-wrap">
                  <button
                    type="button"
                    className="ghost"
                    aria-expanded={notifyOpen}
                    aria-controls="pop-status"
                    ref={statusTrigger}
                    onClick={() => {
                      const next = !notifyOpen;
                      closePops();
                      setNotifyOpen(next);
                    }}
                  >
                    Status
                  </button>
                  <div id="pop-status" className={`pop${notifyOpen ? ' open' : ''}`} hidden={!notifyOpen}>
                    <p className="pop__title">System status</p>
                    <p className="pop__value">{sensorSummary(today?.heartbeats)}</p>
                    <p className="pop__value">{freshnessNote(productivity)}</p>
                    <p className="pop__label">
                      {today ? `${today.day}, ${today.tz}` : 'Offline'}
                    </p>
                  </div>
                </div>
                <div className="pop-wrap">
                  <button
                    type="button"
                    className="ghost"
                    aria-expanded={focusOpen}
                    aria-controls="pop-focus"
                    ref={focusTrigger}
                    onClick={() => {
                      const next = !focusOpen;
                      closePops();
                      setFocusOpen(next);
                    }}
                  >
                    Focus
                  </button>
                  <div id="pop-focus" className={`pop${focusOpen ? ' open' : ''}`} hidden={!focusOpen}>
                    <p className="pop__title">Start a focus session</p>
                    <p className="pop__help">Quiet mutes nudges, mild lets urgent ones through, dormant silences everything.</p>
                    <span className="pop__label">Duration</span>
                    <div className="choice-row">
                      {[30, 60, 90].map(m => (
                        <button
                          key={m}
                          type="button"
                          className={`ghost${focusMin === m ? ' on' : ''}`}
                          onClick={() => setFocusMin(m)}
                        >
                          {m}m
                        </button>
                      ))}
                    </div>
                    <span className="pop__label">Quiet level</span>
                    <div className="choice-row">
                      {['quiet', 'mild', 'dormant'].map(l => (
                        <button
                          key={l}
                          type="button"
                          className={`ghost${focusLevel === l ? ' on' : ''}`}
                          onClick={() => setFocusLevel(l)}
                        >
                          {l}
                        </button>
                      ))}
                    </div>
                    <button
                      type="button"
                      className="pop__primary"
                      onClick={async () => {
                        try {
                          await api('/api/quiet', {
                            method: 'POST',
                            body: JSON.stringify({ level: focusLevel, minutes: focusMin }),
                          });
                          setFocusOpen(false);
                          showToast('Focus started.', 'mint');
                          await refresh({ force: true });
                        } catch (err) {
                          showToast(err.message);
                        }
                      }}
                    >
                      Start focus
                    </button>
                  </div>
                </div>
                <div className="pop-wrap">
                  <button
                    type="button"
                    className="ghost"
                    aria-expanded={themeOpen}
                    aria-controls="pop-theme"
                    ref={themeTrigger}
                    onClick={() => {
                      const next = !themeOpen;
                      closePops();
                      setThemeOpen(next);
                    }}
                  >
                    Theme
                  </button>
                  <div id="pop-theme" className={`pop${themeOpen ? ' open' : ''}`} hidden={!themeOpen}>
                    <p className="pop__title" id="effects-mode-label">
                      Visual effects
                    </p>
                    <div className="choice-row" role="radiogroup" aria-labelledby="effects-mode-label">
                      {[
                        ['auto', 'Auto'],
                        ['full', 'Full'],
                        ['quiet', 'Quiet'],
                      ].map(([value, label]) => (
                        <button
                          key={value}
                          type="button"
                          role="radio"
                          aria-checked={gpu.mode === value}
                          className={`ghost${gpu.mode === value ? ' on' : ''}`}
                          onClick={() => setEffectsMode(value)}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                    <p className="pop__help">
                      {gpu.reason ||
                        'Effects are running. Auto turns them down on battery, with data saver, or when frames start dropping.'}
                      {gpu.mode === 'full' && gpu.quiet
                        ? ' Reduced motion is an accessibility setting, so Full does not override it.'
                        : ''}
                    </p>
                    <p className="pop__title">Accent color</p>
                    <div className="pop__swatch-row">
                      <span className="pop__swatch" style={{ background: theme.hex }} />
                      <span className="pop__value">{theme.hex}</span>
                    </div>
                    {theme.rgb.map((v, i) => (
                      <label key={i} className="pop__slider-row">
                        <span className="pop__label">{['R', 'G', 'B'][i]}</span>
                        <input
                          type="range"
                          min={0}
                          max={255}
                          value={v}
                          onChange={e => theme.setChannel(i, parseInt(e.target.value, 10))}
                        />
                      </label>
                    ))}
                    <button type="button" className="ghost pop__primary" onClick={theme.reset}>
                      Reset accent
                    </button>
                  </div>
                </div>
              </div>
            </header>

            {error ? (
              <div className="connection-banner">
                <span>
                  <strong>Connection lost.</strong> {error.message}
                </span>
                <button type="button" className="ghost" onClick={() => refresh({ force: true })}>
                  Retry
                </button>
              </div>
            ) : null}

            <div className="page-body">
              <div className="main-col">
                <NowPanel
                  today={today}
                  plan={today?.plan}
                  onRefresh={refresh}
                  showToast={showToast}
                  onOpenPlan={openPlan}
                />

                {summaryBits.length ? (
                  <section
                    id="overview-metrics"
                    aria-label="Day at a glance"
                    className={isMobile ? 'day-summary' : undefined}
                  >
                    {isMobile ? (
                      <p className="day-summary__line">{summaryBits.join(' · ')}</p>
                    ) : (
                      <div className="metric-row">
                        {goalCount ? (
                          <article className="card metric-card span-3">
                            <p className="card-lead">Goals done</p>
                            <div className="metric-value">{`${progress.done || 0}/${goalCount}`}</div>
                            <p className="metric-note">{goalProgressLabel(progress)}</p>
                          </article>
                        ) : null}
                        {meetingCount ? (
                          <article className="card metric-card span-3">
                            <p className="card-lead">Events</p>
                            <div className="metric-value">{meetingCount}</div>
                            <p className="metric-note">{eventsSummary(today?.meetings)}</p>
                          </article>
                        ) : null}
                        {approvalCount ? (
                          <article className="card metric-card span-3">
                            <p className="card-lead">Approvals</p>
                            <div className="metric-value">{approvalCount}</div>
                            <p className="metric-note">{approvalsSummary(today?.approvals)}</p>
                          </article>
                        ) : null}
                        {hasAlignment ? (
                          <article className="card metric-card span-3">
                            <p className="card-lead">Est. alignment</p>
                            <div className="metric-value">~{productivity.score}%</div>
                            <p className="metric-note">{coverageNote(productivity)}</p>
                          </article>
                        ) : null}
                      </div>
                    )}
                  </section>
                ) : null}

                {showEvidence ? (
                  <section className="card evidence-card" id="panel-evidence" aria-labelledby="evidence-title">
                    {isMobile ? (
                      <button
                        type="button"
                        className="panel-disclosure__trigger"
                        aria-expanded={evidenceOpen}
                        aria-controls="evidence-body"
                        onClick={() => setEvidenceOpen(open => !open)}
                      >
                        <span>Activity evidence</span>
                        <span className="panel-disclosure__meta">{alignmentHeadline(productivity)}</span>
                      </button>
                    ) : (
                      <div className="card-head">
                        <h2 id="evidence-title">Activity evidence</h2>
                        <span className={`chip ${productivity.confidence === 'high' ? 'mint' : productivity.confidence === 'medium' ? 'cyan' : 'neutral'}`}>
                          {productivity.confidence ? `${productivity.confidence} confidence` : 'no estimate'}
                        </span>
                      </div>
                    )}
                    <div id="evidence-body" hidden={isMobile && !evidenceOpen}>
                      {!isMobile ? null : <h2 id="evidence-title" className="visually-hidden">Activity evidence</h2>}
                      <p className="card-lead">{alignmentHeadline(productivity)}</p>
                      <p className="evidence-card__basis">
                        {coverageNote(productivity)} · {freshnessNote(productivity)}
                      </p>
                      {evidenceItems.length ? (
                        <>
                          <p className="evidence-card__caveat">
                            Estimated by {productivity.method || 'matching plan text against observed activity'}.{' '}
                            {confidenceNote(productivity)} Goal outcomes above are the record of what you actually finished.
                          </p>
                          <ul className="evidence-list">
                            {evidenceItems.map(row => (
                              <li key={`${row.title}-${row.bucket}`}>
                                <span className="evidence-list__title">{row.title}</span>
                                <span className={`chip ${bucketTone(row.bucket)}`}>{bucketLabel(row.bucket)}</span>
                                <span className="evidence-list__minutes">{row.minutes} min</span>
                              </li>
                            ))}
                          </ul>
                        </>
                      ) : null}
                    </div>
                  </section>
                ) : null}

                <section className="card panel" id="panel-plan">
                  {isMobile ? (
                    <button
                      type="button"
                      className="panel-disclosure__trigger"
                      aria-expanded={planOpen}
                      aria-controls="plan-body"
                      onClick={() => setPlanOpen(open => !open)}
                    >
                      <span>Plan</span>
                      <span className="panel-disclosure__meta">
                        {plan?.goals?.length
                          ? `${plan.goals.length} goal${plan.goals.length === 1 ? '' : 's'}`
                          : 'Set outcomes'}
                      </span>
                    </button>
                  ) : (
                    <p className="card-lead">
                      {plan?.goals?.length
                        ? `${plan.goals.length} goal${plan.goals.length === 1 ? '' : 's'} and ${(plan.timeline || []).length} block${(plan.timeline || []).length === 1 ? '' : 's'} for this day.`
                        : 'Set the outcomes that would make this day count.'}
                    </p>
                  )}
                  <div id="plan-body" hidden={isMobile && !planOpen}>
                    {!isMobile ? null : (
                      <p className="card-lead">
                        {plan?.goals?.length
                          ? `${plan.goals.length} goal${plan.goals.length === 1 ? '' : 's'} and ${(plan.timeline || []).length} block${(plan.timeline || []).length === 1 ? '' : 's'} for this day.`
                          : 'Set the outcomes that would make this day count.'}
                      </p>
                    )}
                    <PlanEditor
                      plan={plan}
                      planDay={planDay}
                      minDay={undefined}
                      academics={academics}
                      carryForward={planDay === today?.day ? today?.carry_forward : []}
                      meetings={planDay === today?.day ? today?.meetings : []}
                      onDayChange={loadPlanDay}
                      onSaved={() => refresh({ force: true })}
                      showToast={showToast}
                    />
                  </div>
                </section>

                <section className="ops-link card" aria-labelledby="ops-link-title">
                  <h2 id="ops-link-title">Operations</h2>
                  <p className="card-lead">
                    {eventsSummary(today?.meetings)} · {approvalsSummary(today?.approvals)}
                  </p>
                  <p className="card-lead">
                    {programSummary(today?.opportunities)} · {mailSummary(today?.mail)}
                  </p>
                  <Link className="button-link" to="/ops">
                    Open operations
                  </Link>
                </section>

                <section className="analytics-disclosure" id="panel-analytics">
                  <button
                    type="button"
                    className="ghost"
                    aria-expanded={showAnalytics}
                    aria-controls="analytics-body"
                    onClick={() => setShowAnalytics(open => !open)}
                  >
                    {showAnalytics ? 'Hide trends' : 'Show trends'}
                  </button>
                  <div id="analytics-body" hidden={!showAnalytics}>
                    {showAnalytics ? <BentoAnalytics today={today} /> : null}
                  </div>
                </section>

                {isMobile ? (
                  <section className="rhythm-disclosure">
                    <button
                      type="button"
                      className="ghost"
                      aria-expanded={rhythmOpen}
                      aria-controls="dark-rhythm"
                      onClick={() => setRhythmOpen(open => !open)}
                    >
                      {rhythmOpen ? 'Hide rhythm' : 'Rhythm & streak'}
                    </button>
                  </section>
                ) : null}
              </div>

              <aside
                className={`dark-panel${rhythmOpen ? ' dark-panel--open' : ''}`}
                id="dark-rhythm"
                hidden={isMobile && !rhythmOpen}
              >
                {!quietGpu ? (
                  <div className="side-rays-slot">
                    <SideRays speed={1.4} rayColor1="#d08726" rayColor2="#f8debd" intensity={1} origin="top-right" />
                  </div>
                ) : null}
                <div className="dark-panel__content">
                  <h2>Rhythm</h2>
                  <p className="sub-dark">{goalProgressLabel(progress)}</p>
                  <span className="chip neutral">{today ? focusLabel(today.quiet) : ''}</span>
                  {today?.quiet?.active ? (
                    <button
                      type="button"
                      className="ghost"
                      onClick={async () => {
                        try {
                          await api(`/api/quiet/${today.quiet.id}`, { method: 'DELETE' });
                          showToast('Focus ended.', 'mint');
                          await refresh({ force: true });
                        } catch (err) {
                          showToast(err.message);
                        }
                      }}
                    >
                      End focus
                    </button>
                  ) : null}
                  {heatSpiralItems.length ? (
                    <>
                      <h3 className="streak-title">Recent days</h3>
                      <div className="spiral-slot">
                        <InfiniteSpiral
                          items={heatSpiralItems}
                          animationMode={quietGpu ? 'none' : 'auto'}
                          speed={0.22}
                          radius={92}
                          cardWidth={68}
                          cardHeight={68}
                          verticalSpacing={48}
                          cardsPerTurn={heatSpiralItems.length || 7}
                          pauseOnHover
                        />
                      </div>
                    </>
                  ) : null}
                  <h3 className="streak-title">Streak</h3>
                  <div className="streak-slot">
                    <Cubes
                      gridSize={7}
                      faceColor="#3a3a3a"
                      rippleColor="#d08726"
                      autoAnimate={false}
                      rippleOnClick
                      colors={streak.colors}
                      titles={streak.titles}
                    />
                  </div>
                  <p className="sub-dark">{sensorSummary(today?.heartbeats)}</p>
                  <Link className="ghost button-link" to="/ops">
                    Sensor detail
                  </Link>
                </div>
              </aside>
            </div>
          </div>
          </div>
        </div>
      </div>
    </EffectsShell>
    </ChatProvider>
  );
}
