import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

import { getStorefrontData } from '../../app/storefront/storefrontData';

const responseBody = {
  slug: 'jane-events',
  storefront: {
    title: 'Jane Events',
    description: null,
    contact_email: 'hello@example.com',
    contact_phone: null,
    hero_image_url: null,
    about_image_url: null,
    theme_color: '#0f172a',
    packages_enabled: true,
    reviews_enabled: false,
  },
  planner: {
    company_name: 'Jane Events',
    first_name: 'Jane',
    profile_image_url: null,
  },
  packages: [
    {
      _id: 'package-1',
      name: 'Full Planning',
      description: null,
      total_amount: 5000,
      currency: 'USD',
      services: [{ name: 'Vendor sourcing', description: null }],
    },
  ],
  reviews: [],
};

describe('public storefront data contract', () => {
  it('fetches the published route with bounded revalidation', async () => {
    const calls: Array<{ url: string; init?: RequestInit & { next?: { revalidate?: number } } }> = [];
    const fetchImpl: typeof fetch = async (input, init) => {
      calls.push({
        url: String(input),
        init: init as RequestInit & { next?: { revalidate?: number } },
      });
      return { ok: true, status: 200, json: async () => responseBody } as Response;
    };

    const result = await getStorefrontData('jane events', {
      apiBaseUrl: 'http://backend:8000',
      fetchImpl,
    });

    assert.equal(result?.packages[0]?.total_amount, 5000);
    assert.equal(calls[0]?.url, 'http://backend:8000/api/storefront/jane%20events');
    assert.equal(calls[0]?.init?.next?.revalidate, 60);
    assert.equal(calls[0]?.init?.cache, undefined);
    assert.equal(calls[0]?.init?.headers, undefined);
  });

  it('forwards the owner cookie only to the private no-store preview route', async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    const fetchImpl: typeof fetch = async (input, init) => {
      calls.push({ url: String(input), init });
      return { ok: true, status: 200, json: async () => responseBody } as Response;
    };

    const result = await getStorefrontData('jane-events', {
      apiBaseUrl: 'http://backend:8000',
      preview: true,
      adminToken: 'owner-token',
      fetchImpl,
    });

    assert.equal(result?.slug, 'jane-events');
    assert.equal(
      calls[0]?.url,
      'http://backend:8000/admin/storefront/preview/jane-events',
    );
    assert.equal(calls[0]?.init?.cache, 'no-store');
    assert.deepEqual(calls[0]?.init?.headers, {
      Authorization: 'Bearer owner-token',
    });
    assert.equal(
      (calls[0]?.init as RequestInit & { next?: unknown })?.next,
      undefined,
    );
  });

  it('fails closed without fetching when preview authentication is absent', async () => {
    let calls = 0;
    const fetchImpl: typeof fetch = async () => {
      calls += 1;
      throw new Error('should not fetch');
    };

    assert.equal(
      await getStorefrontData('jane-events', {
        apiBaseUrl: 'http://backend:8000',
        preview: true,
        adminToken: null,
        fetchImpl,
      }),
      null,
    );
    assert.equal(calls, 0);
  });

  it('uses the shared renderer, exact DTO fields, owner cookie, and real inquiry form', () => {
    const source = readFileSync('app/storefront/[domain]/page.tsx', 'utf8');

    assert.match(source, /StorefrontView/);
    assert.match(source, /StorefrontInquiryForm/);
    assert.match(source, /cookies\(\)/);
    assert.match(source, /admin_token/);
    assert.match(source, /searchParams/);
    assert.match(source, /preview/);
    assert.doesNotMatch(source, /pkg\.price/);
    assert.doesNotMatch(source, /pkg\.features/);
  });
});
