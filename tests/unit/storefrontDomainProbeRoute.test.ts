import assert from 'node:assert/strict';
import test from 'node:test';

import { GET } from '../../app/.well-known/tsw-storefront-verification/route';

const originalFetch = globalThis.fetch;
const originalEnv = {
  INTERNAL_API_BASE_URL: process.env.INTERNAL_API_BASE_URL,
  FRONTEND_URL: process.env.FRONTEND_URL,
  STOREFRONT_PLATFORM_DOMAINS: process.env.STOREFRONT_PLATFORM_DOMAINS,
  STOREFRONT_CNAME_TARGET: process.env.STOREFRONT_CNAME_TARGET,
};
const challenge = `v1.fixed-probe-nonce.${'a'.repeat(64)}`;

function restoreEnvironment(): void {
  globalThis.fetch = originalFetch;
  for (const [key, value] of Object.entries(originalEnv)) {
    if (value === undefined) {
      delete process.env[key];
    } else {
      process.env[key] = value;
    }
  }
}

test('custom-host probe forwards only the bounded challenge and actual Host to the backend', async () => {
  process.env.INTERNAL_API_BASE_URL = 'http://backend.internal:8000';
  process.env.FRONTEND_URL = 'https://thespecialwedding.io';
  process.env.STOREFRONT_PLATFORM_DOMAINS = 'thespecialwedding.io,thespecialwedding.com';
  process.env.STOREFRONT_CNAME_TARGET = 'domains.thespecialwedding.com';
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    calls.push({ url: String(input), init });
    return new Response(JSON.stringify({ version: '1', proof: 'opaque' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  }) as typeof fetch;

  try {
    const response = await GET(
      new Request('https://events.customer.example/.well-known/tsw-storefront-verification', {
        headers: {
          host: 'events.customer.example',
          'x-tsw-storefront-probe': challenge,
          'x-tsw-storefront-host': 'attacker.example',
        },
      }),
    );

    assert.equal(response.status, 200);
    assert.equal(calls.length, 1);
    assert.equal(
      calls[0].url,
      'http://backend.internal:8000/api/storefront/domain-verification-probe',
    );
    const headers = new Headers(calls[0].init?.headers);
    assert.equal(headers.get('x-tsw-storefront-probe'), challenge);
    assert.equal(headers.get('x-tsw-storefront-host'), 'events.customer.example');
    assert.equal(calls[0].init?.redirect, 'manual');
  } finally {
    restoreEnvironment();
  }
});

test('probe route rejects platform hosts, query strings, malformed proofs, and oversized upstreams', async () => {
  process.env.INTERNAL_API_BASE_URL = 'http://backend.internal:8000';
  process.env.FRONTEND_URL = 'https://thespecialwedding.io';
  process.env.STOREFRONT_PLATFORM_DOMAINS = 'thespecialwedding.io,thespecialwedding.com';
  let calls = 0;
  globalThis.fetch = (async () => {
    calls += 1;
    return new Response(new Uint8Array(8 * 1024 + 1), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  }) as typeof fetch;

  try {
    for (const request of [
      new Request('https://thespecialwedding.io/.well-known/tsw-storefront-verification', {
        headers: { host: 'thespecialwedding.io', 'x-tsw-storefront-probe': challenge },
      }),
      new Request('https://events.customer.example/.well-known/tsw-storefront-verification?debug=1', {
        headers: { host: 'events.customer.example', 'x-tsw-storefront-probe': challenge },
      }),
      new Request('https://events.customer.example/.well-known/tsw-storefront-verification', {
        headers: { host: 'events.customer.example', 'x-tsw-storefront-probe': 'not-a-proof' },
      }),
    ]) {
      assert.equal((await GET(request)).status, 404);
    }
    assert.equal(calls, 0);

    const oversized = await GET(
      new Request('https://events.customer.example/.well-known/tsw-storefront-verification', {
        headers: { host: 'events.customer.example', 'x-tsw-storefront-probe': challenge },
      }),
    );
    assert.equal(oversized.status, 404);
    assert.equal(calls, 1);
  } finally {
    restoreEnvironment();
  }
});
