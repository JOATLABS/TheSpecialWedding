import assert from 'node:assert/strict';
import test from 'node:test';

import {
  getApiBaseUrl,
  getBrowserOrigin,
  getProxyBackendBaseUrl,
  getServerApiBaseUrl,
  resolveBrowserUrl,
} from '../../app/utils/env';

const originalWindow = globalThis.window;
const originalNavigator = globalThis.navigator;
const originalBackendServiceUrl = process.env.BACKEND_SERVICE_URL;
const originalInternalApiBaseUrl = process.env.INTERNAL_API_BASE_URL;
const originalPublicApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
const originalFrontendUrl = process.env.FRONTEND_URL;
const originalNodeEnv = process.env.NODE_ENV;
const mutableEnv = process.env as NodeJS.ProcessEnv & { NODE_ENV?: string };

function restoreEnvVar(name: string, value: string | undefined) {
  if (value === undefined) {
    delete process.env[name];
  } else {
    process.env[name] = value;
  }
}

function setBrowserLocation(url: string) {
  const parsed = new URL(url);

  Object.defineProperty(globalThis, 'window', {
    value: {
      location: {
        origin: parsed.origin,
        host: parsed.host,
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

  restoreEnvVar('BACKEND_SERVICE_URL', originalBackendServiceUrl);
  restoreEnvVar('INTERNAL_API_BASE_URL', originalInternalApiBaseUrl);
  restoreEnvVar('NEXT_PUBLIC_API_BASE_URL', originalPublicApiBaseUrl);
  restoreEnvVar('FRONTEND_URL', originalFrontendUrl);
  if (originalNodeEnv === undefined) {
    Reflect.deleteProperty(mutableEnv, 'NODE_ENV');
  } else {
    mutableEnv.NODE_ENV = originalNodeEnv;
  }
}

test.afterEach(() => {
  resetEnvironment();
});

test('browser runtime always returns /api/proxy on staging origin', () => {
  process.env.NEXT_PUBLIC_API_BASE_URL = 'https://api.thespecialwedding.io';
  setBrowserLocation('https://staging.thespecialwedding.io');

  assert.equal(getApiBaseUrl(), '/api/proxy');
});

test('browser runtime always returns /api/proxy on production origin', () => {
  setBrowserLocation('https://thespecialwedding.io');

  assert.equal(getApiBaseUrl(), '/api/proxy');
});

test('browser runtime always returns /api/proxy on localhost', () => {
  setBrowserLocation('http://localhost:3000');

  assert.equal(getApiBaseUrl(), '/api/proxy');
});

test('browser runtime always returns /api/proxy regardless of NEXT_PUBLIC_API_BASE_URL value', () => {
  process.env.NEXT_PUBLIC_API_BASE_URL = 'https://api.example.com';
  setBrowserLocation('https://example.com');

  // The env var must never influence the browser-side return value — the API
  // subdomain must stay invisible to crawlers and out of the client bundle.
  assert.equal(getApiBaseUrl(), '/api/proxy');
});

test('server runtime prefers INTERNAL_API_BASE_URL when configured', () => {
  process.env.INTERNAL_API_BASE_URL = 'http://backend.internal:8000/';
  process.env.FRONTEND_URL = 'https://staging.thespecialwedding.io';

  assert.equal(getServerApiBaseUrl(), 'http://backend.internal:8000');
  assert.equal(getApiBaseUrl(), 'http://backend.internal:8000');
});

test('proxy runtime prefers BACKEND_SERVICE_URL over server API fallbacks', () => {
  process.env.BACKEND_SERVICE_URL = 'http://backend-prod:8000/';
  process.env.INTERNAL_API_BASE_URL = 'https://api.thespecialwedding.io';
  process.env.FRONTEND_URL = 'https://thespecialwedding.io';

  assert.equal(getProxyBackendBaseUrl('https://thespecialwedding.io'), 'http://backend-prod:8000');
});

test('proxy runtime falls back to INTERNAL_API_BASE_URL', () => {
  delete process.env.BACKEND_SERVICE_URL;
  process.env.INTERNAL_API_BASE_URL = 'http://backend-prod:8000/';
  process.env.FRONTEND_URL = 'https://thespecialwedding.io';

  assert.equal(getProxyBackendBaseUrl('https://thespecialwedding.io'), 'http://backend-prod:8000');
});

test('proxy runtime falls back to NEXT_PUBLIC_API_BASE_URL when internal URL is absent', () => {
  delete process.env.BACKEND_SERVICE_URL;
  delete process.env.INTERNAL_API_BASE_URL;
  process.env.NEXT_PUBLIC_API_BASE_URL = 'https://api.thespecialwedding.io/';
  process.env.FRONTEND_URL = 'https://thespecialwedding.io';

  assert.equal(getProxyBackendBaseUrl('https://thespecialwedding.io'), 'https://api.thespecialwedding.io');
});

test('proxy runtime derives backend URL from FRONTEND_URL as the last fallback', () => {
  delete process.env.BACKEND_SERVICE_URL;
  delete process.env.INTERNAL_API_BASE_URL;
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
  process.env.FRONTEND_URL = 'https://staging.thespecialwedding.io';

  assert.equal(
    getProxyBackendBaseUrl('https://staging.thespecialwedding.io'),
    'https://api.staging.thespecialwedding.io',
  );
});

test('proxy runtime rejects a backend target that points at the frontend origin', () => {
  process.env.BACKEND_SERVICE_URL = 'https://thespecialwedding.io/';
  process.env.FRONTEND_URL = 'https://thespecialwedding.io';

  assert.throws(
    () => getProxyBackendBaseUrl('https://thespecialwedding.io'),
    /Proxy backend URL must not point at the frontend origin/,
  );
});

test('proxy runtime rejects backend targets with unsupported schemes', () => {
  process.env.BACKEND_SERVICE_URL = 'ftp://backend.internal:8000';

  assert.throws(
    () => getProxyBackendBaseUrl('https://thespecialwedding.io'),
    /Proxy backend URL must use http or https/,
  );
});

test('server runtime derives API host from FRONTEND_URL when public env is not baked', () => {
  mutableEnv.NODE_ENV = 'production';
  delete process.env.BACKEND_SERVICE_URL;
  delete process.env.INTERNAL_API_BASE_URL;
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
  process.env.FRONTEND_URL = 'https://staging.thespecialwedding.io';

  assert.equal(getServerApiBaseUrl(), 'https://api.staging.thespecialwedding.io');
  assert.equal(getApiBaseUrl(), 'https://api.staging.thespecialwedding.io');
});

test('server runtime fails loudly when no API base URL can be resolved', () => {
  delete process.env.BACKEND_SERVICE_URL;
  delete process.env.INTERNAL_API_BASE_URL;
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
  delete process.env.FRONTEND_URL;
  mutableEnv.NODE_ENV = 'development';

  assert.throws(
    () => getServerApiBaseUrl(),
    /Could not resolve API base URL/,
  );
  assert.throws(
    () => getApiBaseUrl(),
    /Could not resolve API base URL/,
  );
});

test('browser runtime resolves current-origin URLs without hardcoded fallbacks', () => {
  setBrowserLocation('https://staging.thespecialwedding.io');

  assert.equal(getBrowserOrigin(), 'https://staging.thespecialwedding.io');
  assert.equal(resolveBrowserUrl('/forms/form_123'), 'https://staging.thespecialwedding.io/forms/form_123');
});

test('browser URL resolution fails loudly outside the browser runtime', () => {
  assert.throws(() => getBrowserOrigin(), /Unable to determine this app URL outside the browser\./);
  assert.throws(() => resolveBrowserUrl('/forms/form_123'), /Unable to determine this app URL outside the browser\./);
});
