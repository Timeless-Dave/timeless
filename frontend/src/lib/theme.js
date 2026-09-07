const DEFAULT = [208, 135, 38];

function hex(r, g, b) {
  return '#' + [r, g, b].map(n => Number(n).toString(16).padStart(2, '0')).join('');
}

function relativeLuminance(r, g, b) {
  const channel = c => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrastRatio(l1, l2) {
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

/** Pick accent variants that stay visible on light surfaces and for focus rings. */
export function readableAccent(rgb, background = [255, 255, 255], minRatio = 3) {
  const [r, g, b] = rgb;
  const bgLum = relativeLuminance(...background);
  let cr = r;
  let cg = g;
  let cb = b;
  if (contrastRatio(bgLum, relativeLuminance(cr, cg, cb)) >= minRatio) {
    return { accent: hex(cr, cg, cb), readable: hex(cr, cg, cb), focus: hex(cr, cg, cb) };
  }
  for (let step = 0; step < 14; step += 1) {
    cr = Math.max(0, Math.round(cr * 0.86));
    cg = Math.max(0, Math.round(cg * 0.86));
    cb = Math.max(0, Math.round(cb * 0.86));
    const lum = relativeLuminance(cr, cg, cb);
    if (contrastRatio(bgLum, lum) >= minRatio) {
      return { accent: hex(r, g, b), readable: hex(cr, cg, cb), focus: hex(cr, cg, cb) };
    }
  }
  const fallback = '#383838';
  return { accent: hex(r, g, b), readable: fallback, focus: fallback };
}

export function loadTheme() {
  const raw = (localStorage.getItem('timeless_rgb') || '').split(',').map(n => parseInt(n, 10));
  const rgb = raw.length === 3 && raw.every(n => n >= 0 && n <= 255) ? raw : DEFAULT.slice();
  applyTheme(rgb[0], rgb[1], rgb[2]);
  return rgb;
}

export function applyTheme(r, g, b) {
  const tones = readableAccent([r, g, b]);
  document.documentElement.style.setProperty('--accent', tones.accent);
  document.documentElement.style.setProperty('--accent-readable', tones.readable);
  document.documentElement.style.setProperty('--focus-ring', tones.focus);
  document.documentElement.style.setProperty('--accent-rgb', `${r}, ${g}, ${b}`);
}

export function resetTheme() {
  localStorage.removeItem('timeless_rgb');
  applyTheme(DEFAULT[0], DEFAULT[1], DEFAULT[2]);
  return DEFAULT.slice();
}

export function saveTheme(rgb) {
  localStorage.setItem('timeless_rgb', rgb.join(','));
  applyTheme(rgb[0], rgb[1], rgb[2]);
}

export { DEFAULT as DEFAULT_THEME_RGB };
