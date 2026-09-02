import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ChartLineUp,
  EnvelopeSimple,
  FileText,
  Heart,
  Pulse,
  Sparkle,
} from '@phosphor-icons/react';
import CommandBlock from '@/components/CommandBlock';
import BentoAnalytics from '@/components/BentoAnalytics';
import Cubes from '@/components/Cubes';
import DashboardBackground from '@/components/DashboardBackground';
import EffectsShell from '@/components/EffectsShell';
import GlassJumper from '@/components/GlassJumper';
import InfiniteSpiral from '@/components/InfiniteSpiral';
import PlanEditor from '@/components/PlanEditor';
import {
  ApprovalsSection,
  EventsSection,
  MailSection,
  ProgramsSection,
  RitualsSection,
} from '@/components/OpsSections';
import ParticleText from '@/components/ParticleText';
import PillNav from '@/components/PillNav';
import SideRays from '@/components/SideRays';
import TextType from '@/components/TextType';
import TrueFocus from '@/components/TrueFocus';
import { ChatProvider } from '@/components/ChatSidebar';
import { useToday } from '@/context/TodayContext';
import { useBreakpoint, useIsMobile, useReducedMotion, useViewportSize } from '@/hooks/useReducedMotion';
import { useThemeControls } from '@/hooks/useThemeControls';
import { api } from '@/lib/api';
import { heatTile, streakGrid } from '@/lib/tiles';
import {
  approvalsSummary,
  eventsSummary,
  focusLabel,
  formatPageDate,
  mailSummary,
  nextMeeting,
  planBlocks,
  programSummary,
  relTime,
  ritualsSummary,
  sensorSummary,
} from '@/lib/summary';

const LOGO = '/favicon.svg';

const NAV_ITEMS = [
  { label: 'Today', href: '#overview' },
  { label: 'Plan', href: '#panel-plan' },
  { label: 'Events', href: '#panel-events' },
  { label: 'Programs', href: '#panel-programs' },
  { label: 'Mail', href: '#panel-mail' },
  { label: 'Signals', href: '#dark-sensors' },
];

function scrollToHash(hash) {
  const id = hash.replace('#', '');
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

export default function Dashboard({ showToast }) {
  const { today, academics, googleState, error, refresh } = useToday();
  const reduce = useReducedMotion();
  const mobile = useIsMobile();
  const breakpoint = useBreakpoint();
  const { width: viewportWidth } = useViewportSize();
  const theme = useThemeControls();
  const [activeNav, setActiveNav] = useState('#overview');
  const [searchQuery, setSearchQuery] = useState('');
  const [planDay, setPlanDay] = useState('');
  const [viewPlan, setViewPlan] = useState(null);
  const [focusOpen, setFocusOpen] = useState(false);
  const [notifyOpen, setNotifyOpen] = useState(false);
  const [themeOpen, setThemeOpen] = useState(false);
  const [focusLevel, setFocusLevel] = useState('quiet');
  const [focusMin, setFocusMin] = useState(60);
  const [refreshing, setRefreshing] = useState(false);

  const closePops = useCallback(() => {
    setNotifyOpen(false);
    setFocusOpen(false);
    setThemeOpen(false);
  }, []);

  useEffect(() => {
    const onKey = e => {
      if (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) {
        e.preventDefault();
        document.querySelector('.search')?.focus();
      }
      if (e.key === 'Escape' && document.activeElement?.classList?.contains('search')) {
        setSearchQuery('');
        document.activeElement?.blur();
      }
      if (e.key === 'Escape') closePops();
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
  }, [closePops]);

  const panelHidden = id => {
    const needle = searchQuery.trim().toLowerCase();
    if (!needle) return false;
    const el = document.getElementById(id);
    return el ? !el.textContent.toLowerCase().includes(needle) : false;
  };

  useEffect(() => {
    if (today?.day && !planDay) setPlanDay(today.day);
  }, [today, planDay]);

  const plan = useMemo(() => {
    if (!today) return null;
    if (planDay === today.day) return today.plan;
    return viewPlan;
  }, [today, planDay, viewPlan]);

  const loadPlanDay = useCallback(
    async day => {
      setPlanDay(day);
      if (day !== today?.day) {
        const p = await api('/api/plan?day=' + encodeURIComponent(day));
        setViewPlan(p);
      } else setViewPlan(null);
    },
    [today?.day]
  );

  const navKey = `${breakpoint}-${Math.round(viewportWidth / 120)}`;

  const actionTexts = useMemo(() => {
    if (!today) return ['Loading your day…'];
    if (today.needs_gate) return ['Lock today\'s plan first', 'Start at the gate'];
    const nm = nextMeeting(today.meetings);
    if (nm) return [`Join ${nm.title}`, `Next up ${relTime(nm.start_at)}`];
    if (today.approvals?.length) return [`Review ${today.approvals.length} approval(s)`, 'Decisions waiting'];
    return ['Your day is clear', 'Keep the plan aligned'];
  }, [today]);

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

  const topPrograms = (today?.opportunities || []).slice(0, 3);

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
  const blocks = planBlocks(plan);
  const nm = today ? nextMeeting(today.meetings) : null;

  return (
    <ChatProvider onRefresh={refresh}>
      {({ openChat }) => (
    <EffectsShell>
      <DashboardBackground />
      <div className="app-shell">
        <div className="shell-card">
          <div className="shell-content">
          <div
            className="pill-nav-slot"
            onClick={e => {
              const a = e.target.closest('a[href^="#"]');
              if (!a) return;
              e.preventDefault();
              const href = a.getAttribute('href');
              setActiveNav(href);
              scrollToHash(href);
            }}
          >
            <PillNav
              key={navKey}
              logo={LOGO}
              logoAlt="Timeless"
              items={NAV_ITEMS}
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
                <input
                  type="search"
                  className="search"
                  placeholder="Search dashboard…"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                />
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
                    onClick={() => {
                      const next = !notifyOpen;
                      closePops();
                      setNotifyOpen(next);
                    }}
                  >
                    Status
                  </button>
                  <div className={`pop${notifyOpen ? ' open' : ''}`}>
                    <p className="pop__title">Status</p>
                    <p className="pop__value">{today ? `${today.day}, ${today.tz}` : 'Offline'}</p>
                  </div>
                </div>
                <div className="pop-wrap">
                  <button
                    type="button"
                    className="ghost"
                    onClick={() => {
                      const next = !focusOpen;
                      closePops();
                      setFocusOpen(next);
                    }}
                  >
                    Focus
                  </button>
                  <div className={`pop${focusOpen ? ' open' : ''}`}>
                    <p className="pop__title">Start a focus session</p>
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
                        await api('/api/quiet', {
                          method: 'POST',
                          body: JSON.stringify({ level: focusLevel, minutes: focusMin }),
                        });
                        setFocusOpen(false);
                        showToast('Focus started.', 'mint');
                        await refresh({ force: true });
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
                    onClick={() => {
                      const next = !themeOpen;
                      closePops();
                      setThemeOpen(next);
                    }}
                  >
                    Theme
                  </button>
                  <div className={`pop${themeOpen ? ' open' : ''}`}>
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
                <section className="os-stage" id="overview">
                  <div className="get-started-hero">
                    <div className="get-started-hero__scrim" aria-hidden="true" />
                    <div className="get-started-hero__content">
                      {!reduce ? (
                        <div className="get-started-hero__particle">
                          <ParticleText
                            text="Timeless"
                            particleSize={2.4}
                            density={2}
                            color="#ffffff"
                            highlightColor="#d08726"
                            trigger="mount"
                            fontSize="clamp(2.75rem, 6vw, 4.5rem)"
                            fontWeight={800}
                            fontFamily="inherit"
                            idleDrift={0}
                          />
                        </div>
                      ) : (
                        <h2 className="get-started-hero__particle-fallback">Timeless</h2>
                      )}
                      <p className="os-stage__statement">Your intent, live activity, and next move in one field.</p>
                      <div className="get-started-hero__type"><TextType text={actionTexts[1] || actionTexts[0]} typingSpeed={42} showCursor={false} loop={false} /></div>
                      <div className="os-stage__actions">
                        <button type="button" onClick={() => scrollToHash('#panel-plan')}>Shape today</button>
                        <button type="button" className="ghost" onClick={openChat}>Ask Timeless</button>
                      </div>
                    </div>
                  </div>
                  <div className="os-stage__signal glass-surface">
                    <span>Live field</span>
                    <strong>{today?.heartbeats?.filter(h => Date.now() - (Date.parse(h.last_seen?.endsWith('Z') ? h.last_seen : `${h.last_seen}Z`) || 0) < 30 * 60 * 1000).length || 0} sensors</strong>
                    <p>{productivity.score == null ? 'Alignment forms as the day unfolds.' : `${productivity.score}% alignment with today's intent.`}</p>
                  </div>

                  <h2 className="os-stage__section-title">Act now</h2>
                  <div className="install-grid">
                    <CommandBlock title="Lock plan" command="timeless plan lock" onAction={() => scrollToHash('#panel-plan')} actionLabel="Open plan" />
                    <CommandBlock title="Join next" command={nm?.join_url || 'timeless join next'} onAction={async () => { if (nm) { await api(`/api/meetings/${nm.id}/join`, { method: 'POST', body: '{}' }); await refresh({ force: true }); } }} actionLabel="Join" />
                    <CommandBlock title="Ask Timeless" command='timeless chat "What matters now?"' onAction={openChat} actionLabel="Open chat" />
                  </div>

                  <GlassJumper
                    className="glass-jumper"
                    items={[
                      { icon: <FileText size={24} weight="bold" />, label: 'Plan', onClick: () => scrollToHash('#panel-plan') },
                      { icon: <ChartLineUp size={24} weight="bold" />, label: 'Programs', onClick: () => scrollToHash('#panel-programs') },
                      { icon: <Heart size={24} weight="bold" />, label: 'Rituals', onClick: () => scrollToHash('#panel-rituals') },
                      { icon: <Pulse size={24} weight="bold" />, label: 'Signals', onClick: () => scrollToHash('#dark-sensors') },
                      { icon: <EnvelopeSimple size={24} weight="bold" />, label: 'Mail', onClick: () => scrollToHash('#panel-mail') },
                      { icon: <Sparkle size={24} weight="bold" />, label: 'Alignment', onClick: () => scrollToHash('#panel-approvals') },
                    ]}
                  />
                </section>

                <section className="focus-interlude">
                  <div className="true-focus-wrap">
                    <span className="true-focus-wrap__label">Jump to</span>
                    <TrueFocus
                      sentence="Plan Events Signals"
                      manualMode
                      borderColor="#d08726"
                      glowColor="rgba(208, 135, 38, 0.55)"
                      animationDuration={0.4}
                      pauseBetweenAnimations={1.4}
                    />
                  </div>
                </section>

                <section id="overview-metrics">
                  <div className="metric-row">
                    <article className="card metric-card span-3"><p className="card-lead">Plan</p><div className="metric-value">{blocks}</div></article>
                    <article className="card metric-card span-3"><p className="card-lead">Events</p><div className="metric-value">{today?.meetings?.length || 0}</div></article>
                    <article className="card metric-card span-3"><p className="card-lead">Approvals</p><div className="metric-value">{today?.approvals?.length || 0}</div></article>
                    <article className="card metric-card span-3"><p className="card-lead">Score</p><div className="metric-value">{productivity.score ?? 'Pending'}</div></article>
                  </div>
                </section>

                <BentoAnalytics today={today} />

                <section className={`card panel${panelHidden('panel-plan') ? ' search-hide' : ''}`} id="panel-plan">
                  <p className="card-lead">
                    {blocks ? `${blocks} blocks locked in for this day.` : 'Add blocks so the day has a shape.'}
                  </p>
                  <PlanEditor
                    plan={plan}
                    planDay={planDay}
                    minDay={today?.day}
                    academics={academics}
                    onDayChange={loadPlanDay}
                    onSaved={() => refresh({ force: true })}
                    showToast={showToast}
                  />
                </section>

                <p className="card-lead panel-lead">{eventsSummary(today?.meetings)}</p>
                <EventsSection
                  meetings={today?.meetings}
                  onRefresh={refresh}
                  showToast={showToast}
                  searchHide={panelHidden('panel-events')}
                />

                <p className="card-lead panel-lead">{programSummary(today?.opportunities)}</p>
                <ProgramsSection
                  opportunities={today?.opportunities}
                  googleState={googleState}
                  onRefresh={refresh}
                  showToast={showToast}
                  searchHide={panelHidden('panel-programs')}
                  topPrograms={topPrograms}
                  reduce={reduce}
                />

                <p className="card-lead panel-lead">{mailSummary(today?.mail)}</p>
                <MailSection
                  mail={today?.mail}
                  searchHide={panelHidden('panel-mail')}
                />

                <p className="card-lead panel-lead">{ritualsSummary(today?.rituals)}</p>
                <RitualsSection
                  rituals={today?.rituals}
                  onRefresh={refresh}
                  showToast={showToast}
                  searchHide={panelHidden('panel-rituals')}
                />

                <p className="card-lead panel-lead">{approvalsSummary(today?.approvals)}</p>
                <ApprovalsSection
                  approvals={today?.approvals}
                  onRefresh={refresh}
                  showToast={showToast}
                  searchHide={panelHidden('panel-approvals')}
                />
              </div>

              <aside className="dark-panel" id="dark-sensors">
                {!reduce ? (
                  <div className="side-rays-slot">
                    <SideRays speed={1.4} rayColor1="#d08726" rayColor2="#f8debd" intensity={1} origin="top-right" />
                  </div>
                ) : null}
                <div className="dark-panel__content">
                  <h2>Signals</h2>
                  <p className="sub-dark">{sensorSummary(today?.heartbeats)}</p>
                  <span className="chip neutral">{today ? focusLabel(today.quiet) : ''}</span>
                  {today?.quiet?.active ? (
                    <button
                      type="button"
                      className="ghost"
                      onClick={async () => {
                        await api(`/api/quiet/${today.quiet.id}`, { method: 'DELETE' });
                        showToast('Focus ended.', 'mint');
                        await refresh({ force: true });
                      }}
                    >
                      End focus
                    </button>
                  ) : null}
                  {today?.heartbeats?.length ? (
                    <div className="sensors">
                      {today.heartbeats.map(h => {
                        const stale = Date.now() - (Date.parse(h.last_seen?.endsWith('Z') ? h.last_seen : h.last_seen + 'Z') || 0) > 30 * 60 * 1000;
                        return (
                          <div key={h.sensor} className="sensor">
                            <div className="sensor-top">
                              <span className="sensor-name">{h.sensor}</span>
                              <span className={`chip ${stale ? 'stale' : 'ok'}`}>{stale ? 'Quiet' : 'Live'}</span>
                            </div>
                            <p className="sensor-meta">Last seen {relTime(h.last_seen)}</p>
                          </div>
                        );
                      })}
                    </div>
                  ) : null}
                  {heatSpiralItems.length ? (
                    <>
                      <h3 className="streak-title">Recent days</h3>
                      <div className="spiral-slot">
                        <InfiniteSpiral
                          items={heatSpiralItems}
                          animationMode="none"
                          speed={0.3}
                          radius={92}
                          cardWidth={68}
                          cardHeight={68}
                          verticalSpacing={48}
                          cardsPerTurn={heatSpiralItems.length || 7}
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
                </div>
              </aside>
            </div>
          </div>
          </div>
        </div>
      </div>
    </EffectsShell>
      )}
    </ChatProvider>
  );
}
