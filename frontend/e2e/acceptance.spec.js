import { expect, test } from '@playwright/test';
import { resetState, seedPlan, windowAroundNow } from './helpers.js';

test.describe('acceptance flows', () => {
  let day;

  test.beforeEach(async ({ request }, testInfo) => {
    // The recap flow needs the day still unsettled; every other flow needs it
    // out of the way so the app routes straight to the dashboard.
    const settleRecap = !testInfo.title.includes('recap');
    day = await resetState(request, { settleRecap });
  });

  // Runs first: acknowledging a recap is permanent, so this flow has to be
  // exercised while the day is still open.
  test('will not close the recap while a goal is unjudged', async ({ page, request }) => {
    const today = await (await request.get('/api/today')).json();
    await seedPlan(request, {
      day: today.recap_day,
      goals: [{ text: 'Finished thing' }, { text: 'Never judged' }],
    });
    const goals = (await (await request.get(`/api/goals?day=${today.recap_day}`)).json()).goals;
    await request.patch(`/api/goals/${goals[0].id}`, { data: { status: 'done' } });
    await request.post('/api/recap/generate', { data: { skip_phone: true } });

    await page.goto('/recap');
    const ticket = page.locator('.recap-ticket');

    // A Mac-only recap always opens on the phone-sync step. Waited for rather
    // than polled once: `goto` resolves before React has mounted.
    const skip = ticket.getByRole('button', { name: 'Skip' });
    await expect(skip).toBeVisible();
    await skip.click();
    await expect(ticket.getByText('Step 1 of', { exact: false })).toBeVisible();

    for (let i = 0; i < 10; i += 1) {
      const next = ticket.getByRole('button', { name: 'Next' });
      if (!(await next.isVisible())) break;
      await next.click();
    }

    await expect(ticket.getByText(/still needs? an outcome/)).toBeVisible();
    await expect(ticket.getByRole('button', { name: 'Close the day' })).toBeDisabled();

    await ticket.getByRole('button', { name: /Defer the rest/ }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('textbox').fill('ran out of day');
    await dialog.getByRole('button', { name: 'Defer them' }).click();

    const close = ticket.getByRole('button', { name: 'Close the day' });
    await expect(close).toBeEnabled();
    await close.click();
    // Closing yesterday hands you straight to today's gate, which has no plan yet.
    await expect(page).toHaveURL(/\/gate$/);
  });

  test('creates a plan at the gate and lands on Now', async ({ page, request }) => {
    await page.goto('/');
    // With no plan for today the app routes to the gate.
    await expect(page).toHaveURL(/\/gate/);

    await page.getByLabel('Goal 1 outcome', { exact: true }).fill('Ship the acceptance pass');
    await page.getByRole('button', { name: '+ Goal' }).click();
    await page.getByLabel('Goal 2 outcome', { exact: true }).fill('Read the arXiv paper');

    const { start, end } = windowAroundNow();
    await page.getByLabel('Block 1 start').fill(start);
    await page.getByLabel('Block 1 end').fill(end);
    await page.getByLabel('Block 1 focus').fill('acceptance work');
    await page.getByLabel('Block 1 goal').selectOption({ label: 'Ship the acceptance pass' });

    await expect(page.locator('.plan-editor .save-status')).toHaveText('Unsaved changes');
    await page.getByRole('button', { name: 'Save plan' }).click();

    await expect(page).toHaveURL(/\/$/);
    const now = page.locator('#now');
    await expect(now.getByText('Ship the acceptance pass').first()).toBeVisible();

    // The plan really reached the database.
    const stored = await (await request.get(`/api/plan?day=${day}`)).json();
    expect(stored.goals.map(g => g.text)).toEqual([
      'Ship the acceptance pass',
      'Read the arXiv paper',
    ]);
  });

  test('refuses an impossible schedule before saving', async ({ page }) => {
    await page.goto('/gate');
    await page.getByLabel('Goal 1 outcome', { exact: true }).fill('Something');
    await page.getByLabel('Block 1 start').fill('14:00');
    await page.getByLabel('Block 1 end').fill('13:00');
    await page.getByLabel('Block 1 focus').fill('backwards');

    await expect(page.getByText('Block 1 ends before it starts.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Save plan' })).toBeDisabled();
  });

  test('starts work and switches goals without leaving a contradiction', async ({ page, request }) => {
    const { start, end } = windowAroundNow();
    await seedPlan(request, {
      day,
      goals: [{ text: 'Goal A' }, { text: 'Goal B' }],
      timeline: [{ start, end, task: 'on A', goal_index: 0 }],
    });

    await page.goto('/');
    const now = page.locator('#now');
    await expect(now.getByRole('heading', { name: 'Now' })).toBeVisible();

    await now.locator('.now-panel__focus').getByRole('button', { name: 'Start', exact: true }).click();
    await expect(now.locator('.now-panel__kicker')).toHaveText('Working on');
    await expect(now.getByRole('button', { name: 'Stop work' })).toBeVisible();

    // Switch to the other goal from its row in the goal list.
    const goalB = now.locator('.now-goal', { hasText: 'Goal B' });
    await goalB.getByRole('button', { name: 'Start' }).click();

    await expect(now.locator('.now-panel__goal')).toHaveText('Goal B');
    const work = await (await request.get('/api/work')).json();
    expect(work.goal.text).toBe('Goal B');
    expect(work.conflicts.map(c => c.kind)).not.toContain('focus_mismatch');
    expect(work.next_action.text).not.toBe('on A');
  });

  test('runs a block through pause and finish', async ({ page, request }) => {
    const { start, end } = windowAroundNow();
    await seedPlan(request, {
      day,
      goals: [{ text: 'Focused work' }],
      timeline: [{ start, end, task: 'the block', goal_index: 0 }],
    });

    await page.goto('/');
    const facts = page.locator('.now-panel__facts');
    await expect(facts.getByText('the block')).toBeVisible();

    await facts.getByRole('button', { name: 'Start block' }).click();
    await expect(facts.getByRole('button', { name: 'Pause' })).toBeVisible();

    await facts.getByRole('button', { name: 'Pause' }).click();
    await expect(facts.getByRole('button', { name: 'Resume' })).toBeVisible();

    await facts.getByRole('button', { name: 'Finish' }).click();
    await expect(facts.getByText('Finished')).toBeVisible();

    const plan = await (await request.get(`/api/plan?day=${day}`)).json();
    const blockId = plan.timeline[0].block_id;
    expect(plan.block_runs.find(run => run.block_id === blockId).state).toBe('done');
  });

  test('archives a goal on removal and restores it', async ({ page, request }) => {
    // Archived rows accumulate across flows in the shared database and there is
    // no API to delete a plan, so this fixture names itself uniquely rather
    // than depending on a reset that cannot fully clean up.
    const label = `Worked on ${Date.now()}`;
    const plan = await seedPlan(request, { day, goals: [{ text: label }, { text: 'Other' }] });
    await request.patch(`/api/goals/${plan.goals[0].id}`, {
      data: { status: 'partial', note: 'half of it' },
    });

    await page.goto('/');
    // The app routes on load; wait until it has settled on the dashboard.
    await expect(page.locator('#now')).toBeVisible();
    const planTrigger = page.locator('#panel-plan').getByRole('button', { name: /^Plan\b/ });
    if (await planTrigger.isVisible()) await planTrigger.click();
    const editor = page.locator('.plan-editor');
    await expect(editor).toBeVisible();

    await editor.getByRole('button', { name: 'Remove goal 1' }).click();
    await expect(editor.getByText(/Its history is kept/)).toBeVisible();
    await editor.getByRole('button', { name: 'Save plan' }).click();

    await expect(editor.getByRole('button', { name: /Show removed goals/ })).toBeVisible();
    await editor.getByRole('button', { name: /Show removed goals/ }).click();
    const archived = page.locator('.archived-goals');
    const archivedRow = archived.locator('li', { hasText: label }).first();
    await expect(archivedRow).toBeVisible();
    await expect(archivedRow.getByText('half of it')).toBeVisible();

    await archivedRow.getByRole('button', { name: 'Restore' }).click();
    await expect(page.locator('#now').getByText(label).first()).toBeVisible();

    const goals = (await (await request.get(`/api/goals?day=${day}`)).json()).goals;
    expect(goals.find(g => g.text === label).status).toBe('partial');
  });


});
