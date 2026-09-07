#!/usr/bin/env node
/**
 * Keep the dashboard open in Chromium for a thermal run.
 * Usage: pnpm exec node scripts/thermal-browser.mjs quiet|auto|full [minutes]
 */
import { chromium } from '@playwright/test';

const MODE = process.argv[2];
const MINUTES = Number(process.argv[3] || 10);
const URL = process.env.THERMAL_URL || 'http://127.0.0.1:8787/';

if (!['quiet', 'auto', 'full'].includes(MODE)) {
  console.error('Usage: pnpm exec node scripts/thermal-browser.mjs quiet|auto|full [minutes]');
  process.exit(1);
}

const browser = await chromium.launch({
  headless: false,
  args: ['--window-size=1280,900'],
});
const context = await browser.newContext();
await context.addInitScript(mode => {
  const key = 'timeless_effects_mode';
  if (mode === 'auto') localStorage.removeItem(key);
  else localStorage.setItem(key, mode);
}, MODE);

const page = await context.newPage();
console.log(`Opening ${URL} with effects mode: ${MODE} for ${MINUTES} minutes…`);
await page.goto(URL, { waitUntil: 'networkidle' });
await page.waitForTimeout(MINUTES * 60 * 1000);
await browser.close();
console.log('Browser session finished.');
