import { defineConfig, devices } from '@playwright/test';

// Each invocation gets its own port and database so a run always starts from a
// clean server. Acknowledging a recap is permanent, so that flow cannot be
// replayed against a database another project already settled.
const PORT = Number(process.env.E2E_PORT || 8799);
const DB = process.env.E2E_DB || '/tmp/timeless-e2e.db';

/**
 * Drives the real stack: built SPA served by FastAPI over HTTP against a real
 * SQLite file. The jsdom component tests cover pieces; these cover the seams
 * between React, routing, HTTP and the database that no unit test can see.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  // Bounded so a stalled step fails fast instead of hanging a run.
  timeout: 20000,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    // A narrow viewport standing in for the phone the dashboard is read on.
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
  ],
  webServer: {
    command: `rm -f ${DB} && cd .. && TIMELESS_DB=${DB} .venv/bin/python -m uvicorn --factory timeless.app:create_app --host 127.0.0.1 --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}/api/today`,
    reuseExistingServer: false,
    timeout: 30000,
  },
});
