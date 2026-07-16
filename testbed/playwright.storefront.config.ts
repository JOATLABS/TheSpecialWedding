import fs from 'node:fs';
import path from 'node:path';

import { defineConfig, devices } from '@playwright/test';

type StorefrontRunManifest = {
  run_id: string;
  frontend_url: string;
  artifact_dir: string;
  provider_mode: 'deterministic' | 'live';
};

function loadRunManifest(): StorefrontRunManifest {
  const manifestPath = process.env.STOREFRONT_TESTBED_RUN_MANIFEST;
  if (!manifestPath) {
    throw new Error('STOREFRONT_TESTBED_RUN_MANIFEST is required');
  }
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8')) as StorefrontRunManifest;
  const frontend = new URL(manifest.frontend_url);
  if (!['127.0.0.1', 'localhost', '::1'].includes(frontend.hostname)) {
    throw new Error('Storefront Playwright runs require a loopback frontend');
  }
  if (!manifest.run_id || !manifest.artifact_dir) {
    throw new Error('Storefront run manifest is incomplete');
  }
  return manifest;
}

const manifest = loadRunManifest();
const playwrightArtifactDir = path.join(manifest.artifact_dir, 'playwright');

export default defineConfig({
  testDir: '.',
  testMatch: 'storefront_frontend_lifecycle.spec.ts',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  outputDir: path.join(playwrightArtifactDir, 'test-results'),
  reporter: [
    ['list'],
    ['json', { outputFile: path.join(playwrightArtifactDir, 'results.json') }],
    ['junit', { outputFile: path.join(playwrightArtifactDir, 'results.xml') }],
    ['html', { outputFolder: path.join(playwrightArtifactDir, 'html'), open: 'never' }],
  ],
  use: {
    baseURL: manifest.frontend_url,
    trace: 'on',
    screenshot: 'on',
    video: 'on',
    serviceWorkers: 'block',
    ignoreHTTPSErrors: manifest.provider_mode === 'deterministic',
  },
  projects: [
    {
      name: 'chromium-desktop-light',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
        colorScheme: 'light',
      },
    },
    {
      name: 'chromium-desktop-dark',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
        colorScheme: 'dark',
      },
    },
    {
      name: 'chromium-mobile-320-light',
      use: {
        ...devices['Pixel 5'],
        viewport: { width: 320, height: 568 },
        colorScheme: 'light',
      },
    },
    {
      name: 'chromium-mobile-320-dark',
      use: {
        ...devices['Pixel 5'],
        viewport: { width: 320, height: 568 },
        colorScheme: 'dark',
      },
    },
    {
      name: 'chromium-mobile-375-light',
      use: {
        ...devices['Pixel 5'],
        viewport: { width: 375, height: 667 },
        colorScheme: 'light',
      },
    },
    {
      name: 'chromium-mobile-375-dark',
      use: {
        ...devices['Pixel 5'],
        viewport: { width: 375, height: 667 },
        colorScheme: 'dark',
      },
    },
    {
      name: 'chromium-mobile-390-light',
      use: {
        ...devices['Pixel 5'],
        viewport: { width: 390, height: 844 },
        colorScheme: 'light',
      },
    },
    {
      name: 'chromium-mobile-390-dark',
      use: {
        ...devices['Pixel 5'],
        viewport: { width: 390, height: 844 },
        colorScheme: 'dark',
      },
    },
  ],
  webServer: undefined,
});
