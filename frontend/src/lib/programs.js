const RE_PREFIX = /^(re|fwd):\s*/i;

const ISO_DATE = /\b(20\d{2}-\d{2}-\d{2})\b/;
const NAMED_DATE =
  /\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2})(?:,?\s*(20\d{2}))?\b/i;

const MONTHS = {
  jan: 0,
  january: 0,
  feb: 1,
  february: 1,
  mar: 2,
  march: 2,
  apr: 3,
  april: 3,
  may: 4,
  jun: 5,
  june: 5,
  jul: 6,
  july: 6,
  aug: 7,
  august: 7,
  sep: 8,
  sept: 8,
  september: 8,
  oct: 9,
  october: 9,
  nov: 10,
  november: 10,
  dec: 11,
  december: 11,
};

function cleanSubject(subject) {
  return String(subject || '')
    .replace(RE_PREFIX, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function hostParts(url) {
  try {
    if (!url?.startsWith('http')) return null;
    const u = new URL(url);
    return {
      host: u.hostname.replace(/^www\./, ''),
      path: u.pathname,
    };
  } catch {
    return null;
  }
}

function titleCase(word) {
  if (!word) return '';
  return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
}

function companyFromHost(host, path = '') {
  if (!host) return '';

  if (host.endsWith('greenhouse.io')) {
    const board = path.split('/').filter(Boolean)[0];
    if (board && board !== 'embed') return titleCase(board.replace(/-/g, ' '));
    return 'Greenhouse posting';
  }
  if (host.endsWith('lever.co')) {
    const board = path.split('/').filter(Boolean)[0];
    if (board) return titleCase(board.replace(/-/g, ' '));
    return 'Lever posting';
  }
  if (host.includes('workday')) return 'Workday posting';
  if (host.includes('linkedin.com')) return 'LinkedIn';
  if (host.includes('myworkdayjobs.com')) {
    const seg = path.split('/').filter(Boolean)[0];
    return seg ? titleCase(seg.replace(/-/g, ' ')) : 'Workday';
  }
  if (host.includes('jobs.')) {
    const base = host.replace(/^jobs\./, '').split('.')[0];
    return titleCase(base);
  }

  const parts = host.split('.');
  const base = parts.length >= 2 ? parts[parts.length - 2] : parts[0];
  if (['com', 'io', 'co', 'org', 'net'].includes(base)) return titleCase(parts[0]);
  return titleCase(base);
}

function roleFromSubject(subject) {
  const s = cleanSubject(subject);
  if (!s) return '';

  const atMatch = s.match(/^(.+?)\s+at\s+(.+?)(?:\s*[-–|]|$)/i);
  if (atMatch) return atMatch[1].trim();

  const appMatch = s.match(/(?:application for|applied to|opportunity:?)\s+(.+?)(?:\s*[-–|]|$)/i);
  if (appMatch) return appMatch[1].trim();

  const roleMatch = s.match(
    /\b((?:software|backend|frontend|full[- ]?stack|data|ml|product|design|engineering|intern|analyst)[^,.|]{0,60})/i
  );
  if (roleMatch) return roleMatch[1].trim();

  if (s.length <= 72) return s;
  return `${s.slice(0, 69)}…`;
}

function deadlineFromText(...parts) {
  const blob = parts.filter(Boolean).join(' ');
  const iso = blob.match(ISO_DATE);
  if (iso) return iso[1];

  const named = blob.match(NAMED_DATE);
  if (!named) return '';

  const key = named[1].toLowerCase();
  const month = MONTHS[key] ?? MONTHS[key.slice(0, 3)];
  if (month == null) return '';

  const year = named[3] ? Number(named[3]) : new Date().getFullYear();
  const day = Number(named[2]);
  const d = new Date(year, month, day);
  if (Number.isNaN(d.getTime())) return '';
  return d.toISOString().slice(0, 10);
}

/** Fill gaps for mail/calendar rows where company and deadline were never parsed. */
export function inferProgram(opp) {
  const storedCompany = String(opp?.company || '').trim();
  const storedRole = String(opp?.role || '').trim();
  const storedDeadline = String(opp?.deadline_at || '').slice(0, 10);
  const url = String(opp?.url || '').trim();

  const hp = hostParts(url);
  const inferredCompany = hp ? companyFromHost(hp.host, hp.path) : '';
  const parsedRole = storedRole ? roleFromSubject(storedRole) || storedRole : '';
  const inferredRole = parsedRole || roleFromSubject(opp?.notes || '');
  const inferredDeadline = deadlineFromText(storedRole, opp?.notes, url);

  return {
    company: storedCompany || inferredCompany,
    role: inferredRole,
    deadline: storedDeadline || inferredDeadline,
    companyIsInferred: !storedCompany && Boolean(inferredCompany),
    roleIsInferred: !storedRole && Boolean(inferredRole),
    deadlineIsInferred: !storedDeadline && Boolean(inferredDeadline),
  };
}

export function programFolderLabel(opp) {
  const { company, role } = inferProgram(opp);
  if (role && company && !role.toLowerCase().includes(company.toLowerCase())) {
    return `${role} · ${company}`;
  }
  return role || company || 'Untitled posting';
}
