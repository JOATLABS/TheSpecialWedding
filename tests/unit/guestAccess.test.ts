import assert from 'node:assert/strict';
import { after, before, describe, it, mock } from 'node:test';

const originalFetch = globalThis.fetch;
const originalInternalApiBaseUrl = process.env.INTERNAL_API_BASE_URL;

let fetchGuestSessionAccess: typeof import('../../app/utils/guestAccess').fetchGuestSessionAccess;

describe('guest session access lookup', () => {
  before(async () => {
    process.env.INTERNAL_API_BASE_URL = 'http://guest-api.example.test/admin';
    ({ fetchGuestSessionAccess } = await import('../../app/utils/guestAccess'));
  });

  after(() => {
    globalThis.fetch = originalFetch;
    if (originalInternalApiBaseUrl === undefined) {
      delete process.env.INTERNAL_API_BASE_URL;
    } else {
      process.env.INTERNAL_API_BASE_URL = originalInternalApiBaseUrl;
    }
  });

  it('maps a missing-session 204 response to null', async () => {
    globalThis.fetch = mock.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      assert.equal(
        input.toString(),
        'http://guest-api.example.test/weddings/guest-access/session/maya-and-jordan',
      );
      assert.deepEqual(init, {
        credentials: 'include',
        cache: 'no-store',
      });
      return new Response(null, { status: 204 });
    }) as unknown as typeof fetch;

    const result = await fetchGuestSessionAccess('maya-and-jordan');

    assert.equal(result, null);
  });

  it('keeps authorization and not-found responses as empty session results', async () => {
    for (const status of [401, 403, 404]) {
      globalThis.fetch = mock.fn(async () => new Response(null, { status })) as unknown as typeof fetch;

      assert.equal(await fetchGuestSessionAccess('maya-and-jordan'), null);
    }
  });

  it('returns the verified guest session payload', async () => {
    const payload = {
      wedding: { id: 'w_123', slug: 'maya-and-jordan' },
      guest: { id: 'guest_123', name: 'Taylor Guest' },
      rsvp: { has_rsvp: false },
      auth_method: 'token',
      otp_verified: false,
    };
    globalThis.fetch = mock.fn(async () => new Response(JSON.stringify(payload), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })) as unknown as typeof fetch;

    assert.deepEqual(await fetchGuestSessionAccess('maya-and-jordan'), payload);
  });
});
