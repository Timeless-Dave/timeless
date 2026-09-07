import { expect, test } from '@playwright/test';
import { resetState, seedPlan, windowAroundNow } from './helpers.js';

test.describe('keyboard and narrow screens', () => {
  let day;

  test.beforeEach(async ({ request }) => {
    day = await resetState(request);
  });

  test('plans a day using only the keyboard', async ({ page, request }) => {
    await page.goto('/gate');
    await expect(page.getByLabel('Goal 1', { exact: true })).toBeVisible();

    // Reach the first goal field by tabbing, never by clicking.
    let tabs = 0;
    for (; tabs < 40; tabs += 1) {
      if (await page.getByLabel('Goal 1', { exact: true }).evaluate(el => el === document.activeElement)) break;
      await page.keyboard.press('Tab');
    }
    // Recorded rather than assumed: this is how far a keyboard user travels
    // before they can type the first goal of the day.
    expect(tabs, `tab stops before the first goal field: ${tabs}`).toBeLessThan(40);
    await expect(page.getByLabel('Goal 1', { exact: true })).toBeFocused();
    await page.keyboard.type('Typed with no mouse');

    const { start, end } = windowAroundNow();
    await page.getByLabel('Block 1 start').fill(start);
    await page.getByLabel('Block 1 end').fill(end);
    await page.getByLabel('Block 1 focus').fill('keyboard block');

    const save = page.getByRole('button', { name: 'Save plan' });
    await save.focus();
    await page.keyboard.press('Enter');

    await expect(page).toHaveURL(/\/$/);
    const stored = await (await request.get(`/api/plan?day=${day}`)).json();
    expect(stored.goals[0].text).toBe('Typed with no mouse');
  });

  test('judges a goal through the menu with arrow keys and a keyboard dialog', async ({ page, request }) => {
    await seedPlan(request, { day, goals: [{ text: 'Judge me' }] });
    await page.goto('/');
    const now = page.locator('#now');
    await expect(now).toBeVisible();

    const row = now.locator('.now-goal', { hasText: 'Judge me' });
    await row.getByRole('button', { name: 'More' }).focus();
    await page.keyboard.press('ArrowDown');

    const menu = row.getByRole('menu');
    await expect(menu.getByRole('menuitem').first()).toBeFocused();
    await page.keyboard.press('End');
    await expect(menu.getByRole('menuitem', { name: 'Drop' })).toBeFocused();
    await page.keyboard.press('Home');
    await expect(menu.getByRole('menuitem', { name: 'Done' })).toBeFocused();
    // Defer is the item that asks for a reason.
    await page.keyboard.press('ArrowDown');
    await expect(menu.getByRole('menuitem', { name: 'Defer' })).toBeFocused();
    await page.keyboard.press('Enter');

    // Deferring asks for a reason in a real dialog, focused on open.
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole('textbox')).toBeFocused();
    await page.keyboard.type('not today');
    await dialog.getByRole('button', { name: 'Defer' }).click();

    await expect(page.getByRole('dialog')).toBeHidden();
    const goals = (await (await request.get(`/api/goals?day=${day}`)).json()).goals;
    expect(goals[0].status).toBe('deferred');
    expect(goals[0].note).toBe('not today');
  });

  test('escape closes the menu and returns focus to its trigger', async ({ page, request }) => {
    await seedPlan(request, { day, goals: [{ text: 'A goal' }] });
    await page.goto('/');
    const row = page.locator('#now').locator('.now-goal', { hasText: 'A goal' });
    const trigger = row.getByRole('button', { name: 'More' });

    await trigger.click();
    await expect(row.getByRole('menuitem').first()).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(trigger).toBeFocused();
    await expect(trigger).toHaveAttribute('aria-expanded', 'false');
  });

  test('a closed menu does not swallow clicks beneath it', async ({ page, request }) => {
    // Regression: .menu-pop set display:flex, which beat the [hidden] rule, so
    // the invisible menu box intercepted presses on the controls under it.
    const { start, end } = windowAroundNow();
    await seedPlan(request, {
      day,
      goals: [{ text: 'Clickable' }],
      timeline: [{ start, end, task: 'the block', goal_index: 0 }],
    });
    await page.goto('/');
    const facts = page.locator('.now-panel__facts');
    await facts.getByRole('button', { name: 'Start block' }).click({ timeout: 5000 });
    await expect(facts.getByRole('button', { name: 'Pause' })).toBeVisible();
  });
});

test.describe('narrow viewport', () => {
  test.skip(({ isMobile }) => !isMobile, 'phone-width checks');

  test('the day fits the phone without sideways scrolling', async ({ page, request }) => {
    const day = await resetState(request);
    const { start, end } = windowAroundNow();
    await seedPlan(request, {
      day,
      goals: [{ text: 'A goal with a reasonably long name to wrap' }, { text: 'Second' }],
      timeline: [{ start, end, task: 'a block with a long task name', goal_index: 0 }],
    });

    await page.goto('/');
    await expect(page.locator('#now')).toBeVisible();

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    expect(overflow, 'no horizontal overflow').toBeLessThanOrEqual(1);

    // Touch targets on the primary action meet the project's 44px rule.
    const box = await page.locator('#now .now-panel__actions button').first().boundingBox();
    expect(box.height).toBeGreaterThanOrEqual(44);
  });

  test('the note dialog fits and is usable on a phone', async ({ page, request }) => {
    const day = await resetState(request);
    await seedPlan(request, { day, goals: [{ text: 'Defer me' }] });
    await page.goto('/');

    const row = page.locator('#now').locator('.now-goal', { hasText: 'Defer me' });
    await row.getByRole('button', { name: 'More' }).click();
    await row.getByRole('menuitem', { name: 'Defer' }).click();

    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    const box = await dialog.boundingBox();
    const viewport = page.viewportSize();
    expect(box.width).toBeLessThanOrEqual(viewport.width);
    expect(box.x).toBeGreaterThanOrEqual(0);

    await dialog.getByRole('textbox').fill('not today');
    await dialog.getByRole('button', { name: 'Defer' }).click();
    await expect(page.getByRole('dialog')).toBeHidden();
  });
});
