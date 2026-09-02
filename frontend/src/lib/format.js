export function isUrl(value) {
  return /^https?:\/\//i.test(String(value || '').trim());
}

/** Host + path snippet for display; unwraps common safelink wrappers. */
export function prettyUrl(url, maxLen = 52) {
  const raw = String(url || '').trim();
  if (!raw) return '';

  try {
    const u = new URL(raw);
    const host = u.hostname.replace(/^www\./, '');

    if (host.includes('safelinks.protection.outlook.com')) {
      const wrapped = u.searchParams.get('url');
      if (wrapped) return prettyUrl(decodeURIComponent(wrapped), maxLen);
    }

    const path = u.pathname === '/' ? '' : u.pathname.replace(/\/$/, '');
    let out = host + path;
    if (u.search && u.search.length <= 24) out += u.search;
    if (out.length > maxLen) return `${out.slice(0, maxLen - 1)}…`;
    return out;
  } catch {
    return raw.length > maxLen ? `${raw.slice(0, maxLen - 1)}…` : raw;
  }
}

export async function copyText(text) {
  const value = String(text || '');
  if (!value) return false;
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return true;
  }
  const el = document.createElement('textarea');
  el.value = value;
  el.setAttribute('readonly', '');
  el.style.position = 'fixed';
  el.style.left = '-9999px';
  document.body.appendChild(el);
  el.select();
  const ok = document.execCommand('copy');
  document.body.removeChild(el);
  return ok;
}

/** How approval / event fields should render in the UI. */
export function formatFieldValue(label, value) {
  const text = String(value ?? '');
  const labelLower = String(label || '').toLowerCase();
  const urlLike =
    isUrl(text) ||
    labelLower.includes('url') ||
    labelLower === 'posting' ||
    labelLower === 'target' ||
    labelLower === 'link';

  if (urlLike && isUrl(text)) {
    return { text: prettyUrl(text), href: text, isUrl: true };
  }

  const max = 220;
  const display = text.length > max ? `${text.slice(0, max - 1)}…` : text;
  return { text: display, href: null, isUrl: false };
}
