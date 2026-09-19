import { defineConfig } from '@playwright/test';

/**
 * End-to-end tests for Kumaran Crackers Admin.
 *
 * Two suites with different jobs:
 *  - `electron.spec.ts` launches the real Electron binary and audits the
 *    security posture of the renderer it creates.
 *  - `admin-flow.spec.ts` drives the built renderer in Chromium against a
 *    live FastAPI backend, exercising the screens end to end.
 *
 * Both need the backend running on 127.0.0.1:8000.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:4173',
    // Use the Chromium already present in the environment rather than
    // downloading a second copy. CHROMIUM_PATH overrides it where the browser
    // lives somewhere else.
    launchOptions: {
      executablePath:
        process.env.CHROMIUM_PATH ?? '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
      args: ['--no-sandbox'],
    },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: 'npm run preview',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
