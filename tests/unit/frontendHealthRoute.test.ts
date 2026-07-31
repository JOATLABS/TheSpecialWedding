/**
 * Container liveness route contract.
 *
 * Dockerfile.frontend's HEALTHCHECK probes /api/health from inside the
 * container with Host `localhost`. proxy.ts fails closed (404) for any
 * non-platform Host, which is why the probe must live under `api/`
 * (excluded from the proxy matcher), succeed without any Host or env
 * coupling, and never probe the backend (a backend outage must not cascade
 * into a frontend restart loop; backend reachability diagnostics live in
 * /api/health-ssr). Regression context: production incident 2026-07-31 —
 * healthy frontend marked unhealthy, Traefik served "no available server".
 */
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { NextRequest } from 'next/server';

import { GET } from '../../app/api/health/route';
import { proxy, config as proxyConfig } from '../../proxy';

describe('frontend container liveness contract', () => {
  it('GET /api/health returns 200 without host or env coupling', async () => {
    const response = GET();
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { status: 'ok' });
  });

  it('proxy matcher keeps api/ paths exempt so the localhost probe cannot be blocked', () => {
    assert.ok(
      proxyConfig.matcher.some((pattern: string) => pattern.includes('api/')),
      'proxy matcher must continue to exclude api/ routes',
    );
  });

  it('proxy still fails closed for / with Host localhost (authority guard unchanged)', () => {
    const request = new NextRequest('http://localhost:3000/', {
      headers: { host: 'localhost:3000' },
    });
    const response = proxy(request);
    assert.equal(response.status, 404);
  });
});
