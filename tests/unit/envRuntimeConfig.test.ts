import assert from 'node:assert/strict';
import test from 'node:test';

import { getApiBaseUrl, getServerApiBaseUrl } from '../../app/utils/env';

const originalWindow = globalThis.window;
const originalNavigator = globalThis.navigator;
const originalInternalApiBaseUrl = process.env.INTERNAL_API_BASE_URL;
const originalPublicApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
const originalFrontendUrl = process.env.FRONTEND_URL;
const originalNodeEnv = process.env.NODE_ENV;
const mutableEnv = process.env as NodeJS.ProcessEnv & { NODE_ENV?: string };

function setBrowserLocation(url: string) {
  const parsed = new URL(url);

  Object.defineProperty(globalThis, 'window', {
    value: {
      location: {
        hostname: parsed.hostname,
        protocol: parsed.protocol,
      },
    },
    configurable: true,
  });

  Object.defineProperty(globalThis, 'navigator', {
    value: {
      userAgent: 'tsx-test',
      sendBeacon: () => true,
    },
    configurable: true,
  });
}

function resetEnvironment() {
  if (originalWindow === undefined) {
    // @ts-expect-error test-only cleanup
    delete globalThis.window;
  } else {
    Object.defineProperty(globalThis, 'window', { value: originalWindow, configurable: true });
  }

  if (originalNavigator === undefined) {
    // @ts-expect-error test-only cleanup
    delete globalThis.navigator;
  } else {
    Object.defineProperty(globalThis, 'navigator', { value: originalNavigator, configurable: true });
  }

  process.env.INTERNAL_API_BASE_URL = originalInternalApiBaseUrl;
  process.env.NEXT_PUBLIC_API_BASE_URL = originalPublicApiBaseUrl;
  process.env.FRONTEND_URL = originalFrontendUrl;
  if (originalNodeEnv === undefined) {
    Reflect.deleteProperty(mutableEnv, 'NODE_ENV');
  } else {
    mutableEnv.NODE_ENV = originalNodeEnv;
  }
}

test.afterEach(() => {
  resetEnvironment();
});

test('browser runtime derives staging API host from the current origin', () => {
  process.env.NEXT_PUBLIC_API_BASE_URL = 'https://api.thespecialwedding.io';
  setBrowserLocation('https://staging.thespecialwedding.io');

  assert.equal(getApiBaseUrl(), 'https://api.staging.thespecialwedding.io');
});

test('browser runtime derives production API host from the current origin', () => {
  setBrowserLocation('https://thespecialwedding.io');

  assert.equal(getApiBaseUrl(), 'https://api.thespecialwedding.io');
});

test('server runtime prefers INTERNAL_API_BASE_URL when configured', () => {
  process.env.INTERNAL_API_BASE_URL = 'http://backend.internal:8000/';
  process.env.FRONTEND_URL = 'https://staging.thespecialwedding.io';

  assert.equal(getServerApiBaseUrl(), 'http://backend.internal:8000');
  assert.equal(getApiBaseUrl(), 'http://backend.internal:8000');
});

test('server runtime derives API host from FRONTEND_URL when public env is not baked', () => {
  mutableEnv.NODE_ENV = 'production';
  delete process.env.INTERNAL_API_BASE_URL;
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
  process.env.FRONTEND_URL = 'https://staging.thespecialwedding.io';

  assert.equal(getServerApiBaseUrl(), 'https://api.staging.thespecialwedding.io');
  assert.equal(getApiBaseUrl(), 'https://api.staging.thespecialwedding.io');
});
