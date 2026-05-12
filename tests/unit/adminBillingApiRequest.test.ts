import { afterEach, before, describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

process.env.NEXT_PUBLIC_API_BASE_URL = 'https://api.example.com';

type AdminApiRequest = <T = unknown>(
  path: string,
  method?: string,
  body?: unknown,
) => Promise<T | undefined>;

let behavioralApi: typeof import('../../app/services/behavioralAnalyticsApi');
let campaignApi: typeof import('../../app/services/campaignAdvertisingApi');

const originalFetch = globalThis.fetch;

function installFailingFetch() {
  const fetchMock = mock.fn(async () => {
    throw new Error('raw fetch should not be used for AdminContext-protected calls');
  });
  globalThis.fetch = fetchMock as unknown as typeof fetch;
  return fetchMock;
}

function createApiRequest(result: unknown) {
  const calls: Array<{ path: string; method?: string; body?: unknown }> = [];
  const apiRequest: AdminApiRequest = async <T = unknown>(
    path: string,
    method?: string,
    body?: unknown,
  ) => {
    calls.push({ path, method, body });
    return result as T | undefined;
  };
  return { apiRequest, calls };
}

describe('AdminContext-bound billing handling for analytics and advertising services', () => {
  before(async () => {
    behavioralApi = await import('../../app/services/behavioralAnalyticsApi');
    campaignApi = await import('../../app/services/campaignAdvertisingApi');
  });

  afterEach(() => {
    mock.restoreAll();
    if (originalFetch) {
      globalThis.fetch = originalFetch;
    } else {
      Reflect.deleteProperty(
        globalThis as typeof globalThis & { fetch?: typeof fetch },
        'fetch',
      );
    }
  });

  it('routes planner engagement-signal requests through apiRequest and treats undefined as auth handled', async () => {
    const fetchMock = installFailingFetch();
    const { apiRequest, calls } = createApiRequest(undefined);

    const result = await behavioralApi.fetchEngagementSignals(apiRequest);

    assert.equal(result, undefined);
    assert.equal(fetchMock.mock.callCount(), 0);
    assert.deepEqual(calls, [{ path: '/admin/engagement-signals', method: undefined, body: undefined }]);
  });

  it('lets the apiRequest team-member 402 branch handle engagement-signal blocks without generic errors', async () => {
    const fetchMock = installFailingFetch();
    let simulatedTeamMemberLogout = false;
    const apiRequest: AdminApiRequest = async (path) => {
      assert.equal(path, '/admin/engagement-signals');
      simulatedTeamMemberLogout = true;
      return undefined;
    };

    const result = await behavioralApi.fetchEngagementSignals(apiRequest);

    assert.equal(result, undefined);
    assert.equal(simulatedTeamMemberLogout, true);
    assert.equal(fetchMock.mock.callCount(), 0);
  });

  it('routes admin campaign review, revenue, and config reads through apiRequest', async () => {
    const fetchMock = installFailingFetch();
    const { apiRequest, calls } = createApiRequest(undefined);

    const review = await campaignApi.getAdminReviewQueue(apiRequest);
    const revenue = await campaignApi.getAdminRevenue(apiRequest, 30);
    const config = await campaignApi.getAdminConfig(apiRequest);

    assert.equal(review, undefined);
    assert.equal(revenue, undefined);
    assert.equal(config, undefined);
    assert.equal(fetchMock.mock.callCount(), 0);
    assert.deepEqual(calls, [
      {
        path: '/admin/ads/campaigns/review?status=pending_review',
        method: undefined,
        body: undefined,
      },
      {
        path: '/admin/ads/campaigns/revenue?days=30',
        method: undefined,
        body: undefined,
      },
      { path: '/admin/ads/config', method: undefined, body: undefined },
    ]);
  });

  it('keeps non-402 admin errors surfaced by apiRequest', async () => {
    const fetchMock = installFailingFetch();
    const apiRequest: AdminApiRequest = async () => {
      throw new Error('Revenue service unavailable');
    };

    await assert.rejects(
      campaignApi.getAdminRevenue(apiRequest, 7),
      /Revenue service unavailable/,
    );
    assert.equal(fetchMock.mock.callCount(), 0);
  });

  it('keeps vendor portal advertising calls on vendor auth rather than AdminContext', async () => {
    const fetchMock = mock.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      assert.equal(
        input.toString(),
        'https://api.example.com/portal/ads/campaigns?limit=10',
      );
      const headers = init?.headers as Record<string, string> | undefined;
      assert.equal(headers?.Authorization ?? headers?.authorization, 'Bearer vendor-token');
      return new Response(JSON.stringify([]), { status: 200 });
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await campaignApi.listVendorCampaigns('vendor-token', { limit: 10 });

    assert.deepEqual(result, []);
    assert.equal(fetchMock.mock.callCount(), 1);
  });

  it('does not import planner-only redirect helpers in analytics or campaign services', () => {
    const behavioralSource = readFileSync(
      join(process.cwd(), 'app/services/behavioralAnalyticsApi.ts'),
      'utf8',
    );
    const campaignSource = readFileSync(
      join(process.cwd(), 'app/services/campaignAdvertisingApi.ts'),
      'utf8',
    );

    assert.doesNotMatch(behavioralSource, /redirectOnBillingBlock/);
    assert.doesNotMatch(campaignSource, /redirectOnBillingBlock/);
  });
});
