/** Shared setup for the acceptance flows. */

export const TODAY = new Date();

/** Clears every day's plan and settles the outstanding recap.
 *
 * The app routes to /recap or /gate on load depending on server state, so each
 * test declares the state it needs rather than inheriting the previous one.
 */
export async function resetState(request, { settleRecap = true } = {}) {
  const today = (await (await request.get('/api/today')).json());
  for (const day of [today.day, today.recap_day]) {
    const goals = (await (await request.get(`/api/goals?day=${day}`)).json()).goals || [];
    for (const goal of goals) {
      await request.patch(`/api/goals/${goal.id}`, { data: { status: 'dropped', note: '' } });
    }
  }
  if (settleRecap && today.needs_recap) {
    await request.post('/api/recap/generate', { data: { skip_phone: true } });
    const after = await (await request.get('/api/today')).json();
    const stale = (await (await request.get(`/api/goals?day=${after.recap_day}`)).json()).goals || [];
    for (const goal of stale) {
      await request.patch(`/api/goals/${goal.id}`, { data: { status: 'dropped', note: '' } });
    }
    await request.post('/api/recap/ack', { data: {} });
  }
  return today.day;
}

export async function seedPlan(request, { day, goals, timeline = [] }) {
  const response = await request.post('/api/plan', { data: { goals, timeline, day } });
  return response.json();
}

const hhmm = d => `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;

/**
 * A block window covering the real current minute, which is what the server
 * reads when deciding what is scheduled now. Clamped so it cannot run past
 * midnight and be read as an earlier block on the same day.
 */
export function windowAroundNow(offsetMinutes = -5, lengthMinutes = 60) {
  const now = new Date();
  const start = new Date(now.getTime() + offsetMinutes * 60000);
  if (start.getDate() !== now.getDate()) start.setTime(now.getTime());
  const endOfDay = new Date(now);
  endOfDay.setHours(23, 59, 0, 0);
  const end = new Date(Math.min(start.getTime() + lengthMinutes * 60000, endOfDay.getTime()));
  return { start: hhmm(start), end: hhmm(end) };
}

/** A window earlier in the day, for "already finished" scenarios. */
export function windowEarlier() {
  const now = new Date();
  const start = new Date(now);
  start.setHours(Math.max(0, now.getHours() - 3), 0, 0, 0);
  const end = new Date(start.getTime() + 60 * 60000);
  return { start: hhmm(start), end: hhmm(end) };
}
