import assert from 'node:assert/strict';
import test from 'node:test';

import { GET, POST } from '../../app/api/proxy/[[...path]]/route';

const originalFetch = globalThis.fetch;
const originalBackendServiceUrl = process.env.BACKEND_SERVICE_URL;
const originalInternalApiBaseUrl = process.env.INTERNAL_API_BASE_URL;
const originalPublicApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
const originalFrontendUrl = process.env.FRONTEND_URL;

type CapturedFetch = {
  input: RequestInfo | URL;
  init?: RequestInit & { duplex?: 'half' };
};

function restoreEnvVar(name: string, value: string | undefined) {
  if (value === undefined) {
    delete process.env[name];
  } else {
    process.env[name] = value;
  }
}

function resetEnvironment() {
  globalThis.fetch = originalFetch;
  restoreEnvVar('BACKEND_SERVICE_URL', originalBackendServiceUrl);
  restoreEnvVar('INTERNAL_API_BASE_URL', originalInternalApiBaseUrl);
  restoreEnvVar('NEXT_PUBLIC_API_BASE_URL', originalPublicApiBaseUrl);
  restoreEnvVar('FRONTEND_URL', originalFrontendUrl);
}

function proxyContext(path: string[]) {
  return {
    params: Promise.resolve({ path }),
  };
}

test.afterEach(() => {
  resetEnvironment();
});

test('runtime proxy forwards method path query headers cookies and body to the backend', async () => {
  process.env.BACKEND_SERVICE_URL = 'http://backend-prod:8000';
  let captured: CapturedFetch | null = null;

  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    captured = { input, init };
    return new Response(JSON.stringify({ access_token: 'fresh-token' }), {
      status: 201,
      headers: {
        'content-type': 'application/json',
        'x-upstream': 'backend',
      },
    });
  }) as typeof fetch;

  const response = await POST(
    new Request('https://thespecialwedding.io/api/proxy/admin/token/login?next=/admin', {
      method: 'POST',
      headers: {
        cookie: 'admin_refresh=refresh-cookie',
        'content-type': 'application/json',
        host: 'thespecialwedding.io',
        'x-forwarded-for': '203.0.113.10',
      },
      body: JSON.stringify({ email: 'thedeveloper@thespecialwedding.io' }),
    }),
    proxyContext(['admin', 'token', 'login']),
  );

  assert.equal(response.status, 201);
  assert.equal(response.headers.get('x-upstream'), 'backend');
  assert.deepEqual(await response.json(), { access_token: 'fresh-token' });
  const seen = captured as CapturedFetch | null;
  assert.ok(seen);
  assert.equal(String(seen.input), 'http://backend-prod:8000/admin/token/login?next=/admin');
  assert.equal(seen.init?.method, 'POST');

  const forwardedHeaders = new Headers(seen.init?.headers);
  assert.equal(forwardedHeaders.get('cookie'), 'admin_refresh=refresh-cookie');
  assert.equal(forwardedHeaders.get('content-type'), 'application/json');
  assert.equal(forwardedHeaders.get('host'), null);
  assert.equal(forwardedHeaders.get('content-length'), null);
  assert.equal(forwardedHeaders.get('x-forwarded-for'), null);
  assert.equal(seen.init?.duplex, 'half');

  const forwardedBody = seen.init?.body;
  assert.ok(forwardedBody instanceof ReadableStream);
  assert.equal(
    await new Response(forwardedBody).text(),
    JSON.stringify({ email: 'thedeveloper@thespecialwedding.io' }),
  );
});

test('runtime proxy supports the bare /api/proxy path', async () => {
  process.env.BACKEND_SERVICE_URL = 'http://backend-prod:8000';
  let captured: CapturedFetch | null = null;

  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    captured = { input, init };
    return new Response('alive', { status: 200 });
  }) as typeof fetch;

  const response = await GET(
    new Request('https://thespecialwedding.io/api/proxy?health=1'),
    proxyContext([]),
  );

  assert.equal(await response.text(), 'alive');
  const seen = captured as CapturedFetch | null;
  assert.ok(seen);
  assert.equal(String(seen.input), 'http://backend-prod:8000/?health=1');
});

test('runtime proxy preserves multiple Set-Cookie headers from the backend', async () => {
  process.env.INTERNAL_API_BASE_URL = 'http://backend-prod:8000';

  globalThis.fetch = (async () => {
    const headers = new Headers({ 'content-type': 'text/plain' });
    headers.append('set-cookie', 'admin_token=access; Path=/; HttpOnly; Secure; SameSite=None');
    headers.append('set-cookie', 'admin_refresh=refresh; Path=/; HttpOnly; Secure; SameSite=None');
    return new Response('ok', { status: 200, headers });
  }) as typeof fetch;

  const response = await GET(
    new Request('https://thespecialwedding.io/api/proxy/admin/token/refresh', {
      headers: {
        cookie: 'admin_refresh=old-refresh',
      },
    }),
    proxyContext(['admin', 'token', 'refresh']),
  );

  assert.equal(await response.text(), 'ok');
  assert.deepEqual(response.headers.getSetCookie(), [
    'admin_token=access; Path=/; HttpOnly; Secure; SameSite=None',
    'admin_refresh=refresh; Path=/; HttpOnly; Secure; SameSite=None',
  ]);
});

test('runtime proxy fails closed when target origin equals frontend origin', async () => {
  process.env.BACKEND_SERVICE_URL = 'https://thespecialwedding.io';
  let called = false;
  globalThis.fetch = (async () => {
    called = true;
    return new Response('should not call backend');
  }) as typeof fetch;

  const response = await GET(
    new Request('https://thespecialwedding.io/api/proxy/health/livez'),
    proxyContext(['health', 'livez']),
  );

  assert.equal(response.status, 503);
  assert.match(await response.text(), /Proxy backend URL must not point at the frontend origin/);
  assert.equal(called, false);
});

test('runtime proxy fails closed when no backend target can be resolved', async () => {
  delete process.env.BACKEND_SERVICE_URL;
  delete process.env.INTERNAL_API_BASE_URL;
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
  delete process.env.FRONTEND_URL;

  let called = false;
  globalThis.fetch = (async () => {
    called = true;
    return new Response('should not call backend');
  }) as typeof fetch;

  const response = await GET(
    new Request('https://thespecialwedding.io/api/proxy/admin/token/refresh'),
    proxyContext(['admin', 'token', 'refresh']),
  );

  assert.equal(response.status, 503);
  assert.match(await response.text(), /Could not resolve API base URL/);
  assert.equal(called, false);
});

test('runtime proxy fails closed when backend target uses an unsupported scheme', async () => {
  process.env.BACKEND_SERVICE_URL = 'ftp://backend-prod:8000';
  let called = false;
  globalThis.fetch = (async () => {
    called = true;
    return new Response('should not call backend');
  }) as typeof fetch;

  const response = await GET(
    new Request('https://thespecialwedding.io/api/proxy/health/livez'),
    proxyContext(['health', 'livez']),
  );

  assert.equal(response.status, 503);
  assert.match(await response.text(), /Proxy backend URL must use http or https/);
  assert.equal(called, false);
});
