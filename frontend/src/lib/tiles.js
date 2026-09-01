import { mailTypeLabel } from '@/lib/summary';

const escapeXml = str =>
  String(str).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c]));

// Base64 (not encodeURIComponent) because callers set this as an unquoted CSS url(...) —
// an encoded SVG containing its own literal "(" / ")" (e.g. a gradient's url(#g) reference)
// closes the outer url() early and silently drops the image.
const svgToDataUri = svg => `data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(svg)))}`;

const MAIL_TILE_COLORS = {
  'Apply soon': '#d08726',
  'Follow up': '#7294c2',
  'Interview mail': '#9178b8',
  'Offer mail': '#5c8d89',
  Rejection: '#cf6f68',
  'Security alert': '#cf6f68',
  'Password reset': '#cf6f68',
  Verification: '#7294c2',
  'Account activity': '#7294c2',
  Promotion: '#d08726',
  Billing: '#9178b8',
  Invite: '#5c8d89',
  Newsletter: '#8a8a8a',
};

/** A color-coded card standing in for a mail item: its specific type (subject-derived where the
 * classification is generic) + color, no fake imagery. Text sits dead-center — Masonry renders
 * tiles at whatever aspect ratio their column gives them and covers this square into it, so
 * anything off-center risks being cropped away. */
export function mailTile(mail) {
  const label = mailTypeLabel(mail);
  const color = MAIL_TILE_COLORS[label] || '#6a6969';
  const safeLabel = escapeXml(label.toUpperCase());
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="320" height="320">
    <rect width="320" height="320" fill="${color}"/>
    <text x="160" y="166" text-anchor="middle" fill="rgba(255,255,255,.92)" font-family="Mulish, sans-serif" font-size="16" font-weight="800" letter-spacing="1">${safeLabel}</text>
  </svg>`;
  return svgToDataUri(svg);
}

const HEAT_LEVEL_COLORS = ['#4a4949', '#6a6969', '#8a8a8a', '#e0a862', '#d08726'];

/** Buckets a count relative to the busiest day in the set, so the scale (events, seconds, whatever) never matters. */
export function heatLevel(count, max) {
  if (!count) return 0;
  if (!max) return 1;
  const ratio = count / max;
  if (ratio < 0.12) return 1;
  if (ratio < 0.35) return 2;
  if (ratio < 0.65) return 3;
  return 4;
}

/** Colors + tooltips for a gridSize×gridSize streak grid (oldest first, reading left-to-right then
 * down), padded at the front with blank "before we had data" cells so the array always fills the grid. */
export function streakGrid(heatmap, gridSize, max) {
  const cellCount = gridSize * gridSize;
  const days = (heatmap || []).slice(-cellCount);
  const padCount = cellCount - days.length;
  const colors = [];
  const titles = [];
  for (let i = 0; i < padCount; i += 1) {
    colors.push(HEAT_LEVEL_COLORS[0]);
    titles.push('');
  }
  days.forEach(d => {
    colors.push(HEAT_LEVEL_COLORS[heatLevel(d.count || 0, max)]);
    titles.push(`${d.day}: ${d.count || 0}`);
  });
  return { colors, titles };
}

/** A day tile for the heat spiral: activity level color + weekday, replacing placeholder imagery. Raw counts are omitted — the unit isn't meaningful to glance at, the color already ranks the day. */
export function heatTile(day, max) {
  const level = heatLevel(day.count || 0, max);
  const color = HEAT_LEVEL_COLORS[level];
  const weekday = escapeXml(new Date(`${day.day}T12:00:00`).toLocaleDateString(undefined, { weekday: 'short' }));
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200">
    <rect width="200" height="200" rx="28" fill="${color}"/>
    <text x="100" y="112" text-anchor="middle" fill="rgba(255,255,255,.92)" font-family="Mulish, sans-serif" font-size="34" font-weight="700" letter-spacing="1">${weekday}</text>
  </svg>`;
  return svgToDataUri(svg);
}
