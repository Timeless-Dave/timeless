import { useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { minuteSplit } from '@/lib/evidence';
import './BentoAnalytics.css';

const COLORS = ['#d08726', '#5c8d89', '#cf6f68', '#7294c2', '#9178b8'];

function BarChart({ days }) {
  const [hovered, setHovered] = useState(null);
  const max = Math.max(1, ...days.map(day => day.value));
  return (
    <article className="analytics-tile analytics-bars">
      <h3>Activity rhythm</h3>
      <div className="analytics-bars__plot">
        {days.map((day, index) => (
          <div className="analytics-bar__slot" key={day.label}>
            <motion.button
              type="button"
              className="analytics-bar"
              aria-label={`${day.label}: ${day.value} activities`}
              initial={{ scaleY: 0 }}
              animate={{ scaleY: Math.max(0.08, day.value / max) }}
              transition={{ type: 'spring', stiffness: 180, damping: 20, delay: index * 0.05 }}
              whileHover={{ scaleX: 1.08 }}
              onHoverStart={() => setHovered(index)}
              onHoverEnd={() => setHovered(null)}
            />
            <span>{day.label}</span>
            <AnimatePresence>
              {hovered === index ? (
                <motion.output initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                  {day.value}
                </motion.output>
              ) : null}
            </AnimatePresence>
          </div>
        ))}
      </div>
    </article>
  );
}

function point(value, index, count, radius = 78) {
  const angle = (Math.PI * 2 * index) / count - Math.PI / 2;
  const r = (Math.max(0, Math.min(100, value)) / 100) * radius;
  return [100 + Math.cos(angle) * r, 100 + Math.sin(angle) * r];
}

function RadarChart({ metrics }) {
  // A dimension with no measurement is left out of the shape entirely: plotting
  // it as zero would draw absent data as a measured failure.
  const measured = metrics.filter(metric => metric.value != null);
  const missing = metrics.filter(metric => metric.value == null);
  if (measured.length < 3) {
    return (
      <article className="analytics-tile analytics-radar">
        <h3>Alignment profile</h3>
        <p className="empty-note">
          Not enough measured dimensions yet.{' '}
          {missing.length ? `Waiting on: ${missing.map(metric => metric.label.toLowerCase()).join(', ')}.` : ''}
        </p>
      </article>
    );
  }
  const path = measured.map((metric, index) => point(metric.value, index, measured.length).join(',')).join(' ');
  return (
    <article className="analytics-tile analytics-radar">
      <h3>Alignment profile</h3>
      <div className="analytics-radar__body">
        <svg viewBox="0 0 200 200" role="img" aria-label={`Radar chart of ${measured.map(metric => metric.label).join(', ')}`}>
          {[25, 50, 75, 100].map(level => (
            <polygon key={level} points={measured.map((_, index) => point(level, index, measured.length).join(',')).join(' ')} className="radar-grid" />
          ))}
          {measured.map((_, index) => {
            const [x, y] = point(100, index, measured.length);
            return <line key={index} x1="100" y1="100" x2={x} y2={y} className="radar-axis" />;
          })}
          <motion.polygon
            points={path}
            className="radar-shape"
            initial={{ opacity: 0, scale: 0 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ type: 'spring', stiffness: 150, damping: 18 }}
            style={{ transformOrigin: 'center' }}
          />
        </svg>
        <div className="radar-legend">
          {measured.map((metric, index) => (
            <div key={metric.label} title={metric.hint}>
              <i style={{ background: COLORS[index] }} /><span>{metric.label}</span><strong>{metric.value}%</strong>
            </div>
          ))}
          {missing.map(metric => (
            <div key={metric.label} className="radar-legend__missing">
              <i /><span>{metric.label}</span><strong>Not measured</strong>
            </div>
          ))}
        </div>
      </div>
    </article>
  );
}

function DonutChart({ slices }) {
  const [hovered, setHovered] = useState(null);
  if (!slices.length) {
    return (
      <article className="analytics-tile analytics-donut">
        <h3>Where the day went</h3>
        <p className="empty-note">No activity has been observed for this day yet.</p>
      </article>
    );
  }
  const total = Math.max(1, slices.reduce((sum, slice) => sum + slice.value, 0));
  const gradient = slices.reduce(
    (result, slice, index) => ({
      cursor: result.cursor + slice.value,
      parts: [...result.parts, `${COLORS[index]} ${(result.cursor / total) * 100}% ${((result.cursor + slice.value) / total) * 100}%`],
    }),
    { cursor: 0, parts: [] },
  ).parts.join(', ');
  const current = hovered == null ? null : slices[hovered];
  return (
    <article className="analytics-tile analytics-donut">
      <h3>Where the day went</h3>
      <div className="analytics-donut__body">
        <motion.div className="donut" style={{ background: `conic-gradient(${gradient})` }} initial={{ rotate: -120, scale: 0 }} animate={{ rotate: 0, scale: 1 }} transition={{ type: 'spring', stiffness: 100, damping: 18 }}>
          <div><strong>{current ? current.value : total}</strong><span>{current ? current.label : 'minutes'}</span></div>
        </motion.div>
        <div className="donut-legend">
          {slices.map((slice, index) => (
            <button key={slice.label} type="button" onMouseEnter={() => setHovered(index)} onMouseLeave={() => setHovered(null)} onFocus={() => setHovered(index)} onBlur={() => setHovered(null)}>
              <i style={{ background: COLORS[index] }} /><span>{slice.label}</span>
              <strong>{slice.value}m <small>{Math.round((slice.value / total) * 100)}%</small></strong>
            </button>
          ))}
        </div>
      </div>
    </article>
  );
}

export default function BentoAnalytics({ today }) {
  const data = useMemo(() => {
    const heat = (today?.heatmap || []).slice(-7);
    const productivity = today?.productivity || {};
    const progress = today?.goal_progress || {};
    const minutes = productivity.minutes || {};
    const judged = productivity.judged_minutes || 0;
    const tracked = productivity.tracked_minutes || 0;
    const share = (value, total) => (total ? Math.round((100 * value) / total) : null);
    const days = heat.map(day => ({
      label: new Date(`${day.day}T12:00:00`).toLocaleDateString(undefined, { weekday: 'short' }).slice(0, 2),
      value: day.count || 0,
    }));
    return {
      days: days.length ? days : ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'].map(label => ({ label, value: 0 })),
      metrics: [
        {
          label: 'Goals completed',
          value: progress.percent ?? null,
          hint: 'Explicit outcomes you marked done or partly done.',
        },
        {
          label: 'On plan',
          value: share(minutes.aligned || 0, judged),
          hint: 'Estimated share of judged activity that matched the plan text.',
        },
        {
          label: 'Undistracted',
          value: judged ? 100 - share(minutes.distracting || 0, judged) : null,
          hint: 'Estimated share of judged activity that was not distraction.',
        },
        {
          label: 'Classified',
          value: tracked ? 100 - Math.round(100 * (productivity.unknown_share || 0)) : null,
          hint: 'Share of observed time the classifier could place at all.',
        },
      ],
      slices: minuteSplit(productivity),
    };
  }, [today]);

  return (
    <section className="analytics-bento" aria-label="Productivity analytics">
      <BarChart days={data.days} />
      <RadarChart metrics={data.metrics} />
      <DonutChart slices={data.slices} />
    </section>
  );
}
