import { afterEach, before, beforeEach, describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';

process.env.NEXT_PUBLIC_API_BASE_URL = 'https://api.example.com/admin';
process.env.INTERNAL_API_BASE_URL = 'http://127.0.0.1:8000';
let fetchWeddingPrivacyInfo: typeof import('../../app/utils/weddingPrivacyInfo')['fetchWeddingPrivacyInfo'];

const originalFetch = globalThis.fetch;

describe('fetchWeddingPrivacyInfo', () => {
  before(async () => {
    ({ fetchWeddingPrivacyInfo } = await import('../../app/utils/weddingPrivacyInfo'));
  });

  beforeEach(() => {
    mock.restoreAll();
  });

  afterEach(() => {
    if (originalFetch) {
      globalThis.fetch = originalFetch;
    } else {
      Reflect.deleteProperty(
        globalThis as typeof globalThis & { fetch?: typeof fetch },
        'fetch'
      );
    }
  });

  it('treats a real 404 as not found', async () => {
    globalThis.fetch = mock.fn(async () => new Response('missing', { status: 404 })) as unknown as typeof fetch;

    const result = await fetchWeddingPrivacyInfo('missing-wedding');

    assert.deepEqual(result, { kind: 'not_found' });
  });

  it('preserves upstream rate-limit failures as errors', async () => {
    globalThis.fetch = mock.fn(async () => new Response('busy', { status: 429 })) as unknown as typeof fetch;

    const result = await fetchWeddingPrivacyInfo('rate-limited-wedding');

    assert.deepEqual(result, {
      kind: 'error',
      status: 429,
      message: 'Privacy bootstrap request failed with status 429',
    });
  });

  it('returns parsed privacy info for successful responses', async () => {
    const payload = {
      id: 'wed_123',
      couple_names: 'Jordan and Alex',
      privacy_mode: 'private',
      events: [],
    };

    globalThis.fetch = mock.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      assert.equal(
        input.toString(),
        'http://127.0.0.1:8000/weddings/privacy-info/jordan-and-alex',
      );
      assert.deepEqual(init, {
        cache: 'no-store',
      });
      return new Response(JSON.stringify(payload), { status: 200 });
    }) as unknown as typeof fetch;

    const result = await fetchWeddingPrivacyInfo('jordan-and-alex');

    assert.deepEqual(result, {
      kind: 'ok',
      privacyInfo: payload,
    });
  });
});
