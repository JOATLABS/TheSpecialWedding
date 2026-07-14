import { after, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';

const originalFetch = globalThis.fetch;
const originalInternalApiBaseUrl = process.env.INTERNAL_API_BASE_URL;

let fetchPublicGalleryPage: typeof import('../../app/utils/publicGallery').fetchPublicGalleryPage;

function galleryResponse(): Response {
  return new Response(JSON.stringify({
    items: [],
    next_cursor: null,
    has_more: false,
  }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('public gallery request cancellation', () => {
  before(async () => {
    process.env.INTERNAL_API_BASE_URL = 'http://gallery-api.example.test/admin';
    ({ fetchPublicGalleryPage } = await import('../../app/utils/publicGallery'));
  });

  after(() => {
    globalThis.fetch = originalFetch;
    if (originalInternalApiBaseUrl === undefined) {
      delete process.env.INTERNAL_API_BASE_URL;
    } else {
      process.env.INTERNAL_API_BASE_URL = originalInternalApiBaseUrl;
    }
  });

  it('forwards the caller AbortSignal to a public gallery request', async () => {
    const controller = new AbortController();
    let observedInit: RequestInit | undefined;

    globalThis.fetch = (async (_input: RequestInfo | URL, init?: RequestInit) => {
      observedInit = init;
      return galleryResponse();
    }) as typeof fetch;

    await fetchPublicGalleryPage({
      slug: 'sofia-and-daniel',
      privacyMode: 'public',
      signal: controller.signal,
    });

    assert.equal(observedInit?.signal, controller.signal);
  });

  it('forwards the caller AbortSignal to a verified gallery request', async () => {
    const controller = new AbortController();
    let observedInit: RequestInit | undefined;

    globalThis.fetch = (async (_input: RequestInfo | URL, init?: RequestInit) => {
      observedInit = init;
      return galleryResponse();
    }) as typeof fetch;

    await fetchPublicGalleryPage({
      slug: 'sofia-and-daniel',
      privacyMode: 'verified',
      access: { session: true },
      signal: controller.signal,
    });

    assert.equal(observedInit?.method, 'POST');
    assert.equal(observedInit?.signal, controller.signal);
  });

  it('preserves privacy-safe fixture presentation metadata for public rendering', async () => {
    globalThis.fetch = (async () => new Response(JSON.stringify({
      items: [{
        key: 'gallery/sofia-and-daniel/terrace.webp',
        url: '/demo-gallery/sofia-daniel-terrace.webp',
        display_name: 'Garden terrace portrait',
        alt: 'Fictional newlyweds on the glasshouse garden terrace',
        credit: 'Fictional capture fixture generated for The Special Wedding',
      }],
      next_cursor: null,
      has_more: false,
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })) as typeof fetch;

    const page = await fetchPublicGalleryPage({
      slug: 'sofia-and-daniel',
      privacyMode: 'public',
    });

    assert.deepEqual(page.items, [{
      key: 'gallery/sofia-and-daniel/terrace.webp',
      url: '/demo-gallery/sofia-daniel-terrace.webp',
      displayName: 'Garden terrace portrait',
      alt: 'Fictional newlyweds on the glasshouse garden terrace',
      credit: 'Fictional capture fixture generated for The Special Wedding',
    }]);
  });
});
