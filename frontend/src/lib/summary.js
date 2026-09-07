export function parseTs(iso) {
  if (!iso) return NaN;
  return Date.parse(iso.endsWith('Z') ? iso : iso + 'Z');
}

export function relTime(iso, now) {
  const t = parseTs(iso);
  if (Number.isNaN(t)) return iso || '';
  const n = now != null ? now : Date.now();
  const s = Math.round((t - n) / 1000);
  const abs = Math.abs(s);
  const d = new Date(t);
  const fmt = opts => d.toLocaleString(undefined, opts);
  if (abs < 60) return s <= 0 ? 'just now' : 'in a moment';
  if (abs < 3600) {
    const m = Math.round(abs / 60);
    return s > 0 ? 'in ' + m + 'm' : m + 'm ago';
  }
  if (abs < 86400) {
    const h = Math.round(abs / 3600);
    return s > 0 ? 'in ' + h + 'h' : h + 'h ago';
  }
  const tomorrow = new Date(n);
  tomorrow.setDate(tomorrow.getDate() + 1);
  if (s > 0 && d.toDateString() === tomorrow.toDateString()) {
    return 'tomorrow at ' + fmt({ hour: 'numeric', minute: '2-digit' });
  }
  // Day-count only past this point (no clock time) — when() already shows the exact
  // time next to this, so repeating it here would just print the same string twice.
  const days = Math.round(abs / 86400);
  return s > 0 ? 'in ' + days + 'd' : days + 'd ago';
}

export function when(iso) {
  const t = parseTs(iso);
  if (Number.isNaN(t)) return iso || '';
  return new Date(t).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

const STATE_LABELS = {
  seen: 'Not applied yet',
  applied: 'Applied',
  shortlisted: 'Shortlisted',
  interview: 'Interview stage',
  waiting: 'Waiting on reply',
  offer: 'Offer received',
  rejected: 'Rejected',
  skipped: 'Skipped',
  ignored: 'Ignored',
};

export function stateLabel(state) {
  return STATE_LABELS[state] || String(state || '').replace(/_/g, ' ');
}

const MAIL_LABELS = {
  apply: 'Apply soon',
  follow_up: 'Follow up',
  interview: 'Interview mail',
  offer: 'Offer mail',
  rejection: 'Rejection',
  other: 'Other mail',
};

export function mailLabel(classification) {
  return MAIL_LABELS[classification] || String(classification || 'Mail').replace(/_/g, ' ');
}

const SUBJECT_PATTERNS = [
  [/^security alert\b/i, 'Security alert'],
  [/^google:?\s*security/i, 'Security alert'],
  [/password reset|reset your password/i, 'Password reset'],
  [/verify|verification|confirm your/i, 'Verification'],
  [/new (sign-?in|app|device)/i, 'Account activity'],
  [/\bsale\b|% off|deal|discount/i, 'Promotion'],
  [/subscription|renew|billing|receipt|invoice/i, 'Billing'],
  [/invite|invitation|let'?s (hack|meet|chat|talk)/i, 'Invite'],
  [/newsletter|digest|weekly|new releases/i, 'Newsletter'],
];

/** A more specific label than the raw classification, read from the subject line —
 * most of this inbox is classified "other", so without this every row reads "Other mail". */
export function mailTypeLabel(mail) {
  const subject = mail?.subject || '';
  const match = SUBJECT_PATTERNS.find(([pattern]) => pattern.test(subject));
  return match ? match[1] : mailLabel(mail?.classification);
}

const MAIL_CHIP_TONES = {
  'Security alert': 'rose',
  'Password reset': 'rose',
  Rejection: 'rose',
  Verification: 'cyan',
  'Account activity': 'cyan',
  'Follow up': 'cyan',
  'Apply soon': 'amber',
  Promotion: 'amber',
  'Offer mail': 'mint',
  Invite: 'mint',
};

export function mailChipTone(label) {
  return MAIL_CHIP_TONES[label] || 'amber';
}

export function planBlocks(plan) {
  return ((plan && plan.timeline) || []).filter(b => (b.task || '').trim()).length;
}

export function planStatus(plan, heatmap, day) {
  const blocks = planBlocks(plan);
  const todayRow = (heatmap || []).find(h => h.day === day);
  const events = todayRow ? todayRow.count || 0 : 0;
  let pct = 0;
  if (blocks > 0) pct = Math.min(100, Math.round((events / blocks) * 100));
  else if (events > 0) pct = 100;
  let label = 'Clear day';
  let tone = 'mint';
  if (blocks === 0 && events === 0) {
    label = 'Nothing planned yet';
    tone = 'neutral';
  } else if (blocks > 0 && events >= blocks) {
    label = 'On track';
    tone = 'mint';
  } else if (blocks > 0 && events > 0) {
    label = 'Partway there';
    tone = 'cyan';
  } else if (blocks > 0) {
    label = 'Behind plan';
    tone = 'rose';
  }
  return { value: pct, label, tone, blocks, events };
}

export function programSummary(opps) {
  const list = opps || [];
  if (!list.length) return 'No postings tracked yet.';
  const open = list.filter(o => !['rejected', 'skipped', 'ignored', 'offer'].includes(o.state)).length;
  const waiting = list.filter(o => o.state === 'waiting').length;
  const interview = list.filter(o => o.state === 'interview' || o.state === 'shortlisted').length;
  const parts = [`${open} open`];
  if (waiting) parts.push(`${waiting} waiting on a reply`);
  if (interview) parts.push(`${interview} in interview pipeline`);
  return parts.join(', ');
}

export function sensorSummary(heartbeats, now) {
  const list = heartbeats || [];
  if (!list.length) return 'No sensors reporting yet.';
  const n = now != null ? now : Date.now();
  const fresh = list.filter(h => n - parseTs(h.last_seen) < 30 * 60 * 1000).length;
  if (fresh === list.length) return `All ${list.length} sensors checked in recently.`;
  if (fresh === 0) return `${list.length} sensors, none in the last 30 minutes.`;
  return `${fresh} of ${list.length} sensors active in the last 30 minutes.`;
}

export function eventsSummary(meetings, now) {
  const list = (meetings || []).filter(m => parseTs(m.end_at) > (now != null ? now : Date.now()));
  if (!list.length) return 'No upcoming events on the calendar.';
  const next = list.sort((a, b) => parseTs(a.start_at) - parseTs(b.start_at))[0];
  return `Next: ${next.title}, ${relTime(next.start_at, now)}`;
}

export function approvalsSummary(approvals) {
  const n = (approvals || []).length;
  if (!n) return 'Nothing waiting for your OK.';
  if (n === 1) return '1 item needs a quick decision.';
  return `${n} items need a quick decision.`;
}

export function mailSummary(mail) {
  const list = mail || [];
  if (!list.length) return 'Inbox is clear of action items.';
  return `${list.length} mail item${list.length === 1 ? '' : 's'} need attention.`;
}

export function ritualsSummary(rituals) {
  const n = (rituals || []).length;
  if (!n) return 'No rituals pinned.';
  return `${n} ritual${n === 1 ? '' : 's'} ready to run.`;
}

export function focusLabel(quiet) {
  if (!quiet || !quiet.active) return 'Normal mode';
  const mins = Math.max(1, Math.round((quiet.seconds_left || 0) / 60));
  const level = { quiet: 'Focus', mild: 'Mild focus', dormant: 'Do not disturb' }[quiet.level] || quiet.level;
  return `${level}, ${mins}m left`;
}

export function formatPageDate(day) {
  try {
    const d = new Date(day + 'T12:00:00');
    return d.toLocaleDateString(undefined, {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return day;
  }
}

export function nextMeeting(meetings) {
  const now = Date.now();
  return (
    (meetings || [])
      .filter(m => !m.ack && parseTs(m.end_at) > now)
      .sort((a, b) => parseTs(a.start_at) - parseTs(b.start_at))[0] || null
  );
}

function minutesOfDay(hhmm) {
  const match = /^(\d{1,2}):(\d{2})$/.exec(String(hhmm || ''));
  if (!match) return null;
  return Number(match[1]) * 60 + Number(match[2]);
}

/** The time block covering the current minute, plus whatever comes next. */
export function currentBlocks(timeline, clock) {
  const date = clock ? new Date(clock) : new Date();
  const minute = date.getHours() * 60 + date.getMinutes();
  const rows = (timeline || [])
    .map(block => ({ ...block, from: minutesOfDay(block.start), to: minutesOfDay(block.end) }))
    .filter(block => block.from != null && block.to != null && (block.task || '').trim())
    .sort((a, b) => a.from - b.from);
  const active = rows.find(block => block.from <= minute && minute < block.to) || null;
  const next = rows.find(block => block.from > minute) || null;
  return { active, next, remaining: active ? active.to - minute : null };
}

/** Whether a sensor has gone quiet. Wall-clock by nature: the dashboard polls
 * every minute, so this is re-evaluated on each refresh. */
export function sensorStale(heartbeat, now) {
  const seen = parseTs(heartbeat?.last_seen);
  if (Number.isNaN(seen)) return true;
  return (now != null ? now : Date.now()) - seen > 30 * 60 * 1000;
}

export function freshSensorCount(heartbeats, now) {
  return (heartbeats || []).filter(h => !sensorStale(h, now)).length;
}
