import assert from 'node:assert/strict';
import { afterEach, describe, it } from 'node:test';

import {
  buildVendorDirectoryItemList,
  buildVendorProfileJsonLd,
  fetchPublicVendorDirectory,
  fetchPublicVendorProfile,
} from '../../app/vendors/publicVendorData';
import type { PublicVendor } from '../../app/vendors/publicVendorShared';

const vendor: PublicVendor = {
  _id: '64f1f77bcf86cd7994390123',
  business_name: 'Aster Events',
  email: 'hello@example.com',
  phone: '+15555550123',
  website: 'https://example.com',
  address: '100 Main St',
  city: 'Austin',
  state: 'TX',
  country: 'US',
  service_category: 'planner',
  service_description: 'Wedding planning for design-forward celebrations.',
  portfolio_urls: ['https://example.com/portfolio'],
  logo_url: 'https://example.com/logo.png',
  typical_price_min: 2500,
  typical_price_max: 7000,
  currency: 'USD',
  service_radius_miles: 40,
  is_preferred: true,
  weddings_count: 12,
};

const originalFetch = globalThis.fetch;
const originalInternalApiBaseUrl = process.env.INTERNAL_API_BASE_URL;
const originalPublicApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
const originalFrontendUrl = process.env.FRONTEND_URL;

function restoreEnv() {
  if (originalInternalApiBaseUrl === undefined) {
    delete process.env.INTERNAL_API_BASE_URL;
  } else {
    process.env.INTERNAL_API_BASE_URL = originalInternalApiBaseUrl;
  }

  if (originalPublicApiBaseUrl === undefined) {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
  } else {
    process.env.NEXT_PUBLIC_API_BASE_URL = originalPublicApiBaseUrl;
  }

  if (originalFrontendUrl === undefined) {
    delete process.env.FRONTEND_URL;
  } else {
    process.env.FRONTEND_URL = originalFrontendUrl;
  }
}

describe('public vendor SEO schema', () => {
  afterEach(() => {
    globalThis.fetch = originalFetch;
    restoreEnv();
  });

  it('builds ItemList JSON-LD for the server-rendered directory vendors', () => {
    const schema = buildVendorDirectoryItemList([vendor]);

    assert.equal(schema['@type'], 'ItemList');
    assert.equal(schema.itemListElement.length, 1);
    assert.equal(schema.itemListElement[0].position, 1);
    assert.equal(schema.itemListElement[0].url, 'https://thespecialwedding.io/vendors/64f1f77bcf86cd7994390123');
    assert.equal(schema.itemListElement[0].item['@type'], 'ProfessionalService');
    assert.equal(schema.itemListElement[0].item.name, 'Aster Events');
  });

  it('builds public-safe vendor profile JSON-LD', () => {
    const schema = buildVendorProfileJsonLd(vendor);

    assert.equal(schema['@type'], 'ProfessionalService');
    assert.equal(schema['@id'], 'https://thespecialwedding.io/vendors/64f1f77bcf86cd7994390123#vendor');
    assert.equal(schema.name, 'Aster Events');
    assert.equal(schema.email, 'hello@example.com');
    assert.equal(schema.address?.addressLocality, 'Austin');
    assert.equal(schema.priceRange, 'USD 2500-7000');
    assert.deepEqual(schema.sameAs, ['https://example.com']);
    assert.equal('contact_name' in schema, false);
    assert.equal('weddings_count' in schema, false);
  });

  it('returns an empty directory model instead of crashing the public vendor page when the API is unavailable', async () => {
    process.env.INTERNAL_API_BASE_URL = 'https://api.example.com';
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    delete process.env.FRONTEND_URL;
    globalThis.fetch = (async () => new Response('unavailable', { status: 503 })) as typeof fetch;

    const directory = await fetchPublicVendorDirectory();

    assert.deepEqual(directory, {
      vendors: [],
      total: 0,
      categories: [],
      page: 1,
      page_size: 24,
    });
  });

  it('treats API 404s as missing public vendor profiles', async () => {
    process.env.INTERNAL_API_BASE_URL = 'https://api.example.com';
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    delete process.env.FRONTEND_URL;
    globalThis.fetch = (async () => new Response('not found', { status: 404 })) as typeof fetch;

    assert.equal(await fetchPublicVendorProfile('missing-vendor'), null);
  });
});
