import { useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
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
  const path = metrics.map((metric, index) => point(metric.value, index, metrics.length).join(',')).join(' ');
  return (
    <article className="analytics-tile analytics-radar">
      <h3>Alignment profile</h3>
      <div className="analytics-radar__body">
        <svg viewBox="0 0 200 200" role="img" aria-label="Goal alignment radar chart">
          {[25, 50, 75, 100].map(level => (
            <polygon key={level} points={metrics.map((_, index) => point(level, index, metrics.length).join(',')).join(' ')} className="radar-grid" />
          ))}
          {metrics.map((_, index) => {
            const [x, y] = point(100, index, metrics.length);
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
          {metrics.map((metric, index) => (
            <div key={metric.label}><i style={{ background: COLORS[index] }} /><span>{metric.label}</span><strong>{metric.value}%</strong></div>
          ))}
        </div>
      </div>
    </article>
  );
}

function DonutChart({ slices }) {
  const [hovered, setHovered] = useState(null);
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
    const activity = today?.activity_summary || {};
    const categoryEntries = Object.entries(activity.by_category || activity.categories || {}).slice(0, 5);
    const days = heat.map(day => ({ label: new Date(`${day.day}T12:00:00`).toLocaleDateString(undefined, { weekday: 'short' }).slice(0, 2), value: day.count || 0 }));
    return {
      days: days.length ? days : ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'].map(label => ({ label, value: 0 })),
      metrics: [
        { label: 'Intent', value: Math.round(productivity.alignment_score ?? productivity.score ?? 0) },
        { label: 'Focus', value: Math.round(productivity.focus_score ?? 0) },
        { label: 'Follow-through', value: Math.round(productivity.follow_through ?? productivity.completion_score ?? 0) },
        { label: 'Study', value: Math.round(productivity.study_score ?? 0) },
        { label: 'Balance', value: Math.round(productivity.balance_score ?? 0) },
      ],
      slices: categoryEntries.length ? categoryEntries.map(([label, value]) => ({ label, value: Math.round(Number(value) || 0) })) : [
        { label: 'Focused', value: Math.round(productivity.aligned_minutes || 0) },
        { label: 'Useful detour', value: Math.round(productivity.productive_other_minutes || 0) },
        { label: 'Distracted', value: Math.round(productivity.distracting_minutes || 0) },
      ],
    };
  }, [today]);

  return <section className="analytics-bento" aria-label="Productivity analytics"><BarChart days={data.days} /><RadarChart metrics={data.metrics} /><DonutChart slices={data.slices} /></section>;
}
