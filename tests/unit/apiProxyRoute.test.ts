import assert from 'node:assert/strict';
import test from 'node:test';

import { DELETE, GET, POST } from '../../app/api/proxy/[[...path]]/route';

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

async function assertSafeProxyError(response: Response, expectedCode: string) {
  const payload = (await response.json()) as {
    error?: {
      code?: unknown;
      message?: unknown;
      customer_action?: unknown;
      retryable?: unknown;
      support_id?: unknown;
      field_errors?: unknown;
    };
  };
  assert.equal(payload.error?.code, expectedCode);
  assert.equal(typeof payload.error?.message, 'string');
  assert.equal(typeof payload.error?.customer_action, 'string');
  assert.equal(typeof payload.error?.retryable, 'boolean');
  assert.match(String(payload.error?.support_id), /^proxy_[a-f0-9]{16}$/);
  assert.deepEqual(payload.error?.field_errors, {});
  return payload;
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

test('runtime proxy grants unrestricted access only to a valid platform Host authority', async () => {
  process.env.BACKEND_SERVICE_URL = 'http://backend-prod:8000';
  let calls = 0;
  globalThis.fetch = (async () => {
    calls += 1;
    return new Response('must not be reached');
  }) as typeof fetch;

  const invalidHosts: Array<string | null> = [
    null,
    'thespecialwedding.io, studio.example.com',
    'thespecialwedding.io:invalid',
    'thespecialwedding.io:70000',
    'studio.example.com:',
    'https://thespecialwedding.io',
  ];

  for (const host of invalidHosts) {
    const headers = new Headers({ 'content-type': 'application/json' });
    if (host !== null) {
      headers.set('host', host);
    }
    const response = await POST(
      new Request('https://thespecialwedding.io/api/proxy/admin/token/login', {
        method: 'POST',
        headers,
        body: '{}',
      }),
      proxyContext(['admin', 'token', 'login']),
    );

    assert.equal(response.status, 404, String(host));
  }
  assert.equal(calls, 0);

  let captured: CapturedFetch | null = null;
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    captured = { input, init };
    return new Response('platform request', { status: 200 });
  }) as typeof fetch;
  const platformResponse = await POST(
    new Request('https://thespecialwedding.io/api/proxy/admin/token/login', {
      method: 'POST',
      headers: {
        host: 'thespecialwedding.io:443',
        'content-type': 'application/json',
      },
      body: '{}',
    }),
    proxyContext(['admin', 'token', 'login']),
  );

  assert.equal(platformResponse.status, 200);
  const platformFetch = captured as CapturedFetch | null;
  assert.ok(platformFetch);
  assert.equal(String(platformFetch.input), 'http://backend-prod:8000/admin/token/login');
});

test('custom storefront hosts reject arbitrary, cross-host, and non-POST proxy requests', async () => {
  process.env.BACKEND_SERVICE_URL = 'http://backend-prod:8000';
  let calls = 0;
  globalThis.fetch = (async () => {
    calls += 1;
    return new Response('must not be reached');
  }) as typeof fetch;

  const arbitrary = await POST(
    new Request('https://studio.example.com/api/proxy/admin/token/login', {
      method: 'POST',
      headers: { host: 'studio.example.com' },
      body: '{}',
    }),
    proxyContext(['admin', 'token', 'login']),
  );
  const crossHost = await POST(
    new Request(
      'https://studio.example.com/api/proxy/api/storefront/other.example.com/inquiries',
      {
        method: 'POST',
        headers: { host: 'studio.example.com' },
        body: '{}',
      },
    ),
    proxyContext(['api', 'storefront', 'other.example.com', 'inquiries']),
  );
  const wrongMethod = await GET(
    new Request(
      'https://studio.example.com/api/proxy/api/storefront/studio.example.com/inquiries',
      { headers: { host: 'studio.example.com' } },
    ),
    proxyContext(['api', 'storefront', 'studio.example.com', 'inquiries']),
  );
  const queryVariant = await POST(
    new Request(
      'https://studio.example.com/api/proxy/api/storefront/studio.example.com/inquiries?preview=1',
      {
        method: 'POST',
        headers: { host: 'studio.example.com' },
        body: '{}',
      },
    ),
    proxyContext(['api', 'storefront', 'studio.example.com', 'inquiries']),
  );

  assert.equal(arbitrary.status, 404);
  assert.equal(crossHost.status, 404);
  assert.equal(wrongMethod.status, 404);
  assert.equal(queryVariant.status, 404);
  assert.equal(calls, 0);
});

test('custom storefront host forwards only its exact inquiry POST contract', async () => {
  process.env.BACKEND_SERVICE_URL = 'http://backend-prod:8000';
  let captured: CapturedFetch | null = null;
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    captured = { input, init };
    return new Response(
      JSON.stringify({ success: true, inquiry_id: 'inquiry-1' }),
      { status: 201, headers: { 'content-type': 'application/json' } },
    );
  }) as typeof fetch;

  const response = await POST(
    new Request(
      'https://studio.example.com/api/proxy/api/storefront/studio.example.com/inquiries',
      {
        method: 'POST',
        headers: {
          host: 'studio.example.com',
          'content-type': 'application/json',
        },
        body: JSON.stringify({ name: 'Ada', email: 'ada@example.test', message: 'Hello' }),
      },
    ),
    proxyContext(['api', 'storefront', 'studio.example.com', 'inquiries']),
  );

  assert.equal(response.status, 201);
  const seen = captured as CapturedFetch | null;
  assert.ok(seen);
  assert.equal(
    String(seen.input),
    'http://backend-prod:8000/api/storefront/studio.example.com/inquiries',
  );
  assert.equal(new Headers(seen.init?.headers).get('x-forwarded-host'), 'studio.example.com');
});

test('custom storefront ports and IDNA hosts retain the exact inquiry-only contract', async () => {
  process.env.BACKEND_SERVICE_URL = 'http://backend-prod:8000';
  const targets: string[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    targets.push(String(input));
    return new Response('accepted', { status: 202 });
  }) as typeof fetch;

  const portResponse = await POST(
    new Request(
      'https://studio.example.com/api/proxy/api/storefront/studio.example.com/inquiries',
      {
        method: 'POST',
        headers: { host: 'studio.example.com:443' },
        body: '{}',
      },
    ),
    proxyContext(['api', 'storefront', 'studio.example.com', 'inquiries']),
  );
  const idnaResponse = await POST(
    new Request(
      'https://xn--mnchen-3ya.example/api/proxy/api/storefront/xn--mnchen-3ya.example/inquiries',
      {
        method: 'POST',
        headers: { host: 'xn--mnchen-3ya.example' },
        body: '{}',
      },
    ),
    proxyContext(['api', 'storefront', 'xn--mnchen-3ya.example', 'inquiries']),
  );

  assert.equal(portResponse.status, 202);
  assert.equal(idnaResponse.status, 202);
  assert.deepEqual(targets, [
    'http://backend-prod:8000/api/storefront/studio.example.com/inquiries',
    'http://backend-prod:8000/api/storefront/xn--mnchen-3ya.example/inquiries',
  ]);
});

test('runtime proxy supports the bare /api/proxy path', async () => {
  process.env.BACKEND_SERVICE_URL = 'http://backend-prod:8000';
  let captured: CapturedFetch | null = null;

  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    captured = { input, init };
    return new Response('alive', { status: 200 });
  }) as typeof fetch;

  const response = await GET(
    new Request('https://thespecialwedding.io/api/proxy?health=1', {
      headers: { host: 'thespecialwedding.io' },
    }),
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
        host: 'thespecialwedding.io',
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

test('runtime proxy normalizes bodyless upstream responses', async () => {
  process.env.BACKEND_SERVICE_URL = 'http://backend-prod:8000';

  globalThis.fetch = (async () => new Response(null, { status: 204 })) as typeof fetch;

  const response = await DELETE(
    new Request(
      'https://thespecialwedding.io/api/proxy/admin/storefront/custom-domain',
      {
        method: 'DELETE',
        headers: { host: 'thespecialwedding.io' },
      },
    ),
    proxyContext(['admin', 'storefront', 'custom-domain']),
  );

  assert.equal(response.status, 204);
  assert.equal(response.body, null);
  assert.equal(await response.text(), '');
});

test('runtime proxy fails closed when target origin equals frontend origin', async () => {
  process.env.BACKEND_SERVICE_URL = 'https://thespecialwedding.io';
  let called = false;
  globalThis.fetch = (async () => {
    called = true;
    return new Response('should not call backend');
  }) as typeof fetch;

  const response = await GET(
    new Request('https://thespecialwedding.io/api/proxy/health/livez', {
      headers: { host: 'thespecialwedding.io' },
    }),
    proxyContext(['health', 'livez']),
  );

  assert.equal(response.status, 503);
  const payload = await assertSafeProxyError(
    response,
    'proxy_configuration_unavailable',
  );
  assert.doesNotMatch(
    JSON.stringify(payload),
    /Proxy backend URL must not point|thespecialwedding\.io/i,
  );
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
    new Request('https://thespecialwedding.io/api/proxy/admin/token/refresh', {
      headers: { host: 'thespecialwedding.io' },
    }),
    proxyContext(['admin', 'token', 'refresh']),
  );

  assert.equal(response.status, 503);
  const payload = await assertSafeProxyError(
    response,
    'proxy_configuration_unavailable',
  );
  assert.doesNotMatch(JSON.stringify(payload), /Could not resolve API base URL/i);
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
    new Request('https://thespecialwedding.io/api/proxy/health/livez', {
      headers: { host: 'thespecialwedding.io' },
    }),
    proxyContext(['health', 'livez']),
  );

  assert.equal(response.status, 503);
  const payload = await assertSafeProxyError(
    response,
    'proxy_configuration_unavailable',
  );
  assert.doesNotMatch(JSON.stringify(payload), /ftp|backend-prod|must use http/i);
  assert.equal(called, false);
});

test('runtime proxy keeps backend network failures out of the browser response', async () => {
  process.env.BACKEND_SERVICE_URL = 'http://backend-prod:8000';
  const originalConsoleError = console.error;
  const logEvents: unknown[][] = [];
  console.error = (...args: unknown[]) => {
    logEvents.push(args);
  };
  globalThis.fetch = (async () => {
    throw new Error('connect ECONNREFUSED 10.23.45.67:8000 secret-upstream');
  }) as typeof fetch;

  try {
    const response = await GET(
      new Request('https://thespecialwedding.io/api/proxy/health/livez?token=secret', {
        headers: { host: 'thespecialwedding.io' },
      }),
      proxyContext(['health', 'livez']),
    );

    assert.equal(response.status, 502);
    const payload = await assertSafeProxyError(response, 'proxy_backend_unreachable');
    assert.doesNotMatch(
      JSON.stringify(payload),
      /10\.23\.45\.67|backend-prod|secret-upstream|token=secret|ECONNREFUSED/i,
    );
    assert.equal(logEvents.length, 1);
    assert.doesNotMatch(
      JSON.stringify(logEvents),
      /10\.23\.45\.67|backend-prod|secret-upstream|token=secret|ECONNREFUSED/i,
    );
  } finally {
    console.error = originalConsoleError;
  }
});
