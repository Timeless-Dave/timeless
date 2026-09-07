import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import DashboardBackground from '@/components/DashboardBackground';
import EffectsShell from '@/components/EffectsShell';
import PillNav from '@/components/PillNav';
import SideRays from '@/components/SideRays';
import {
  ApprovalsSection,
  EventsSection,
  MailSection,
  ProgramsSection,
  RitualsSection,
} from '@/components/OpsSections';
import { useToday } from '@/context/today-context';
import { useGpuBudget } from '@/hooks/useGpuBudget';
import { useBreakpoint, useReducedMotion, useViewportSize } from '@/hooks/useReducedMotion';
import { api } from '@/lib/api';
import { OPS_NAV, navClickHandler } from '@/lib/nav';
import {
  approvalsSummary,
  eventsSummary,
  focusLabel,
  mailSummary,
  programSummary,
  relTime,
  ritualsSummary,
  sensorStale,
  sensorSummary,
} from '@/lib/summary';

const LOGO = '/favicon.svg';

/**
 * Everything that is not today's execution: calendar, programs, mail, rituals,
 * approvals and sensor health. Separated so the daily loop is not competing
 * with maintenance work on one long page.
 */
export default function OpsPage({ showToast }) {
  const { today, googleState, error, refresh } = useToday();
  const reduce = useReducedMotion();
  const { quiet: quietGpu } = useGpuBudget();
  const breakpoint = useBreakpoint();
  const { width: viewportWidth } = useViewportSize();
  const navigate = useNavigate();
  const [activeNav, setActiveNav] = useState('#panel-events');
  const navKey = `${breakpoint}-${Math.round(viewportWidth / 120)}`;
  const topPrograms = (today?.opportunities || []).slice(0, 3);

  return (
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
                items={OPS_NAV}
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
                  <h1 className="page-title">Operations</h1>
                  <p className="page-date">Calendar, programs, mail, rituals and approvals</p>
                </div>
                <div className="head-tools">
                  <Link className="ghost button-link" to="/">
                    Back to today
                  </Link>
                </div>
              </header>

              {error ? (
                <div className="connection-banner" role="alert">
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
                  <p className="card-lead panel-lead">{eventsSummary(today?.meetings)}</p>
                  <EventsSection meetings={today?.meetings} onRefresh={refresh} showToast={showToast} />

                  <p className="card-lead panel-lead">{programSummary(today?.opportunities)}</p>
                  <ProgramsSection
                    opportunities={today?.opportunities}
                    googleState={googleState}
                    onRefresh={refresh}
                    showToast={showToast}
                    topPrograms={topPrograms}
                  />

                  <p className="card-lead panel-lead">{mailSummary(today?.mail)}</p>
                  <MailSection mail={today?.mail} />

                  <p className="card-lead panel-lead">{ritualsSummary(today?.rituals)}</p>
                  <RitualsSection rituals={today?.rituals} onRefresh={refresh} showToast={showToast} />

                  <p className="card-lead panel-lead">{approvalsSummary(today?.approvals)}</p>
                  <ApprovalsSection approvals={today?.approvals} onRefresh={refresh} showToast={showToast} />
                </div>

                <aside className="dark-panel" id="dark-sensors">
                  {!quietGpu ? (
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
                    {today?.heartbeats?.length ? (
                      <div className="sensors">
                        {today.heartbeats.map(h => {
                          const stale = sensorStale(h);
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
                    ) : (
                      <p className="sub-dark">No sensors have reported yet.</p>
                    )}
                  </div>
                </aside>
              </div>
            </div>
          </div>
        </div>
      </div>
    </EffectsShell>
  );
}
