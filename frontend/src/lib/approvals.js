export function approvalFields(kind, payload = {}) {
  const p = payload || {};
  const line = (label, value, quote) =>
    value != null && value !== '' ? { label, value: String(value), quote } : null;
  const skip = new Set(['opportunity_id', 'prompt', 'risky', 'target']);
  switch (kind) {
    case 'mark_applied':
    case 'opportunity_applied':
      return {
        title: 'Mark as applied',
        lines: [line('Posting', p.url), line('Evidence', p.snippet, true)].filter(Boolean),
      };
    case 'opportunity_skip':
    case 'mark_skipped':
      return {
        title: 'Skip this posting',
        lines: [line('Posting', p.url), line('Reason', p.snippet, true)].filter(Boolean),
        hint: 'Skip stops reminders.',
      };
    case 'do_send':
      return {
        title: 'Blocked risky action',
        lines: [line('Action', p.label || p.action), line('Target', p.url)].filter(Boolean),
        hint: 'Accept records intent only.',
      };
    case 'pin_ritual':
      return {
        title: 'Pin ritual',
        lines: [line('Name', p.name), line('URL', p.launch_url)].filter(Boolean),
      };
    case 'keep_seen':
      return {
        title: 'Keep as seen',
        lines: [line('Posting', p.url), line('Note', p.snippet, true)].filter(Boolean),
      };
    default:
      return {
        title: kind.replace(/_/g, ' '),
        lines: Object.entries(p)
          .filter(([k, v]) => !skip.has(k) && v != null && v !== '')
          .slice(0, 4)
          .map(([k, v]) => line(k.replace(/_/g, ' '), v)),
      };
  }
}
