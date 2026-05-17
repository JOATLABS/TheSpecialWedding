import assert from 'node:assert/strict';
import { afterEach, describe, it } from 'node:test';

import { GET } from '../../app/api/health-ssr/route';

const originalFetch = globalThis.fetch;
const originalEnvironment = process.env.ENVIRONMENT;
const originalInternalApiBaseUrl = process.env.INTERNAL_API_BASE_URL;
const originalToken = process.env.SSR_HEALTHCHECK_TOKEN;

function restoreEnv() {
  if (originalEnvironment === undefined) delete process.env.ENVIRONMENT;
  else process.env.ENVIRONMENT = originalEnvironment;
  if (originalInternalApiBaseUrl === undefined) delete process.env.INTERNAL_API_BASE_URL;
  else process.env.INTERNAL_API_BASE_URL = originalInternalApiBaseUrl;
  if (originalToken === undefined) delete process.env.SSR_HEALTHCHECK_TOKEN;
  else process.env.SSR_HEALTHCHECK_TOKEN = originalToken;
}

describe('SSR health diagnostic route', () => {
  afterEach(() => {
    globalThis.fetch = originalFetch;
    restoreEnv();
  });

  it('redacts backend topology in production without the diagnostic token', async () => {
    process.env.ENVIRONMENT = 'production';
    process.env.INTERNAL_API_BASE_URL = 'http://backend-prod:8000';
    delete process.env.SSR_HEALTHCHECK_TOKEN;
    globalThis.fetch = (async () => new Response('ok', { status: 200 })) as typeof fetch;

    const response = await GET(new Request('https://thespecialwedding.io/api/health-ssr'));
    const payload = await response.json();

    assert.equal(response.status, 200);
    assert.deepEqual(payload, { status: 'ok', api_base: 'redacted' });
  });

  it('returns detailed diagnostics only with the production token', async () => {
    process.env.ENVIRONMENT = 'production';
    process.env.INTERNAL_API_BASE_URL = 'http://backend-prod:8000';
    process.env.SSR_HEALTHCHECK_TOKEN = 'deploy-secret';
    globalThis.fetch = (async () => new Response('ok', { status: 200 })) as typeof fetch;

    const response = await GET(new Request('https://thespecialwedding.io/api/health-ssr', {
      headers: { 'X-SSR-Health-Token': 'deploy-secret' },
    }));
    const payload = await response.json();

    assert.equal(response.status, 200);
    assert.deepEqual(payload, { status: 'ok', api_base: 'http://backend-prod:8000' });
  });
});
