const DEFAULT = [208, 135, 38];

function hex(r, g, b) {
  return '#' + [r, g, b].map(n => Number(n).toString(16).padStart(2, '0')).join('');
}

export function loadTheme() {
  const raw = (localStorage.getItem('timeless_rgb') || '').split(',').map(n => parseInt(n, 10));
  const rgb = raw.length === 3 && raw.every(n => n >= 0 && n <= 255) ? raw : DEFAULT.slice();
  applyTheme(rgb[0], rgb[1], rgb[2]);
  return rgb;
}

export function applyTheme(r, g, b) {
  document.documentElement.style.setProperty('--accent', hex(r, g, b));
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
