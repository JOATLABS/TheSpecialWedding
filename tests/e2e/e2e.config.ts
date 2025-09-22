import { defineConfig, devices } from '@playwright/test';

/**
 * E2E Tests Configuration
 * For testing email notifications and contact forms
 */
export default defineConfig({
  testDir: './',

  /* Run tests one at a time for better visibility during E2E tests */
  fullyParallel: false,

  /* Don't fail on test.only */
  forbidOnly: false,

  /* No retries for manual testing */
  retries: 0,

  /* Single worker for E2E tests */
  workers: 1,

  /* Use list reporter for better visibility */
  reporter: [
    ['list'],
    ['html', { outputFolder: '../results/e2e-report' }]
  ],

  /* Shared settings for all tests */
  use: {
    /* Base URL pointing to our running dev server */
    baseURL: process.env.FRONTEND_URL || 'http://localhost:3000',

    /* Collect full trace for debugging */
    trace: 'on',

    /* Take screenshots at each step */
    screenshot: 'on',

    /* Record videos */
    video: 'on',

    /* Set standard viewport */
    viewport: { width: 1280, height: 720 },

    /* Ignore HTTPS errors */
    ignoreHTTPSErrors: true,

    /* Increase action timeout for slower operations */
    actionTimeout: 30000,

    /* Navigation timeout */
    navigationTimeout: 30000,
  },

  /* Test timeout */
  timeout: 120000,

  /* Configure browser projects */
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        /* Run in headed mode to see what's happening */
        headless: false,
        /* Slow down actions for visibility */
        launchOptions: {
          slowMo: 500,
        },
      },
    },
  ],

  /* Output folder for test artifacts */
  outputDir: '../results/e2e-artifacts',

  /* Don't use webServer since we're running servers separately */
  webServer: undefined,
});