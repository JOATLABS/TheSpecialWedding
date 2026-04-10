import fs from 'node:fs';
import path from 'node:path';
import { defineConfig, devices } from '@playwright/test';

const frontendPort = process.env.PLAYWRIGHT_FRONTEND_PORT ?? '3000';
const backendPort = process.env.PLAYWRIGHT_BACKEND_PORT ?? '8000';
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? `http://localhost:${frontendPort}`;
const backendHealthUrl = process.env.PLAYWRIGHT_BACKEND_URL ?? `http://localhost:${backendPort}`;
const localVenvPython = path.join(
  process.cwd(),
  '.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
);
const backendPython = process.env.PLAYWRIGHT_BACKEND_PYTHON
  ?? (fs.existsSync(localVenvPython) ? localVenvPython : 'python3');

/**
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  testDir: './tests',
  /* Run tests in files in parallel */
  fullyParallel: true,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  /* Opt out of parallel tests on CI. */
  workers: process.env.CI ? 1 : undefined,
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: 'html',
  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    /* Base URL to use in actions like `await page.goto('/')`. */
    baseURL,

    /* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
    trace: 'on-first-retry',

    /* Take screenshot on failure */
    screenshot: 'only-on-failure',

    /* Record video on failure */
    video: 'retain-on-failure',
  },

  /* Configure projects for major browsers */
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },

    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },

    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },

    /* Test against mobile viewports. */
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
    },
    {
      name: 'Mobile Safari',
      use: { ...devices['iPhone 12'] },
    },

    /* Test against branded browsers. */
    {
      name: 'Microsoft Edge',
      use: { ...devices['Desktop Edge'], channel: 'msedge' },
    },
    {
      name: 'Google Chrome',
      use: { ...devices['Desktop Chrome'], channel: 'chrome' },
    },
  ],

  /* Run your local dev server before starting the tests */
  webServer: [
    {
      command: `npm run dev -- --port ${frontendPort}`,
      url: baseURL,
      reuseExistingServer: !process.env.CI,
    },
    {
      command: `${backendPython} -m uvicorn app.main:app --host 0.0.0.0 --port ${backendPort}`,
      url: `${backendHealthUrl}/health`,
      reuseExistingServer: !process.env.CI,
    }
  ],
});
