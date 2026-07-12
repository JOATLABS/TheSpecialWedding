import assert from 'node:assert/strict';
import { describe, it, mock } from 'node:test';

import {
  MAX_STOREFRONT_IMAGE_BYTES,
  connectCustomDomain,
  deleteStorefrontUpload,
  getStorefrontAccess,
  getStorefrontPreviewData,
  getStorefrontPreviewUrl,
  getStorefrontSettings,
  refreshCustomDomain,
  removeCustomDomain,
  saveStorefrontSettings,
  uploadStorefrontImage,
  type StorefrontApiTransport,
} from '../../app/services/storefrontApi';

function recordingTransport(responses: unknown[] = []) {
  const calls: Array<{ path: string; method: string; body: unknown }> = [];
  const transport: StorefrontApiTransport = async <T>(
    path: string,
    method = 'GET',
    body?: unknown,
  ) => {
    calls.push({ path, method, body });
    return responses.shift() as T | undefined;
  };
  return { calls, transport };
}

describe('storefrontApi', () => {
  it('uses the canonical admin route family and exact response envelopes', async () => {
    const settings = {
      slug: 'jane-events',
      title: 'Jane Events',
      description: null,
      contact_email: null,
      contact_phone: null,
      hero_asset_id: null,
      about_asset_id: null,
      theme_color: '#0f172a',
      packages_enabled: true,
      reviews_enabled: true,
      is_published: false,
      published_at: null,
      created_at: null,
      updated_at: null,
      revision: 0,
      slug_editable: true,
      slug_persisted: true,
    };
    const domain = {
      hostname: 'events.example.com',
      status: 'pending',
      provider_status: 'pending',
      ssl_status: 'pending',
      ownership_verification: null,
      ownership_verification_http: null,
      ssl_validation_records: [],
      cname_target: 'storefronts.example.com',
      deletion_status: null,
      last_error: null,
    };
    const preview = {
      slug: settings.slug,
      storefront: {
        title: settings.title,
        description: null,
        contact_email: null,
        contact_phone: null,
        hero_image_url: null,
        about_image_url: null,
        theme_color: settings.theme_color,
        packages_enabled: true,
        reviews_enabled: true,
      },
      planner: { company_name: 'Jane Events', first_name: 'Jane', profile_image_url: null },
      packages: [],
      reviews: [],
    };
    const { calls, transport } = recordingTransport([
      { plan_id: 'signature', storefront_enabled: true, custom_domain_enabled: false },
      { settings },
      { status: 'success', settings },
      preview,
      domain,
      domain,
      undefined,
      { status: 'deleted', asset_id: 'asset-1' },
    ]);

    assert.equal((await getStorefrontAccess(transport)).storefront_enabled, true);
    assert.equal((await getStorefrontSettings(transport))?.slug, 'jane-events');
    assert.equal(
      (await saveStorefrontSettings({ title: 'Jane Events' }, transport)).slug,
      'jane-events',
    );
    assert.equal((await getStorefrontPreviewData('jane-events', transport)).slug, 'jane-events');
    assert.equal((await connectCustomDomain('events.example.com', transport)).hostname, 'events.example.com');
    assert.equal((await refreshCustomDomain(transport))?.status, 'pending');
    await removeCustomDomain(transport);
    assert.equal((await deleteStorefrontUpload('asset-1', transport)).asset_id, 'asset-1');

    assert.deepEqual(calls, [
      { path: '/admin/storefront/access', method: 'GET', body: undefined },
      { path: '/admin/storefront/settings', method: 'GET', body: undefined },
      {
        path: '/admin/storefront/settings',
        method: 'POST',
        body: { title: 'Jane Events' },
      },
      {
        path: '/admin/storefront/preview/jane-events',
        method: 'GET',
        body: undefined,
      },
      {
        path: '/admin/storefront/custom-domain',
        method: 'POST',
        body: { domain: 'events.example.com' },
      },
      {
        path: '/admin/storefront/custom-domain/status',
        method: 'GET',
        body: undefined,
      },
      {
        path: '/admin/storefront/custom-domain',
        method: 'DELETE',
        body: undefined,
      },
      {
        path: '/admin/storefront/upload?asset_id=asset-1',
        method: 'DELETE',
        body: undefined,
      },
    ]);
  });

  it('builds only the internal slug preview URL', () => {
    assert.equal(
      getStorefrontPreviewUrl('jane events'),
      '/storefront/jane%20events?preview=1',
    );
  });

  it('fails closed when a required JSON response is absent', async () => {
    const { transport } = recordingTransport([undefined]);
    await assert.rejects(getStorefrontAccess(transport), /empty response/i);
  });

  it('validates image type and size before reserving an upload', async () => {
    const { calls, transport } = recordingTransport();

    await assert.rejects(
      uploadStorefrontImage(
        new File(['hello'], 'hero.gif', { type: 'image/gif' }),
        'hero',
        transport,
      ),
      /JPEG, PNG, or WebP/i,
    );
    await assert.rejects(
      uploadStorefrontImage(
        new File([new Uint8Array(MAX_STOREFRONT_IMAGE_BYTES + 1)], 'hero.jpg', {
          type: 'image/jpeg',
        }),
        'hero',
        transport,
      ),
      /5 MB/i,
    );
    assert.equal(calls.length, 0);
  });

  it('reserves, uploads, and finalizes a storefront image in order', async () => {
    const asset = {
      asset_id: 'asset-1',
      slot: 'hero' as const,
      state: 'ready',
      key: 'storefront/owner/hero/asset-1.jpg',
      cdn_url: 'https://cdn.example.com/hero.jpg',
      content_type: 'image/jpeg' as const,
      size_bytes: 11,
    };
    const { calls, transport } = recordingTransport([
      {
        asset_id: 'asset-1',
        upload_url: 'https://r2.example/upload',
        cdn_url: asset.cdn_url,
        key: 'storefront/owner/_staging/hero/asset-1',
        max_size_bytes: MAX_STOREFRONT_IMAGE_BYTES,
      },
      asset,
    ]);
    const fetchCalls: Array<{ input: string; init?: RequestInit }> = [];
    const fetchImpl = mock.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      fetchCalls.push({ input: input.toString(), init });
      return new Response('', { status: 200 });
    });
    const file = new File(['image-bytes'], 'hero image.jpg', { type: 'image/jpeg' });

    const result = await uploadStorefrontImage(
      file,
      'hero',
      transport,
      fetchImpl as unknown as typeof fetch,
    );

    assert.deepEqual(result, asset);
    assert.equal(fetchCalls[0].input, 'https://r2.example/upload');
    assert.equal(fetchCalls[0].init?.method, 'PUT');
    assert.equal(fetchCalls[0].init?.body, file);
    assert.equal(
      (fetchCalls[0].init?.headers as Record<string, string>)['Content-Type'],
      'image/jpeg',
    );
    assert.equal(
      calls[0].path,
      '/admin/storefront/upload-url?filename=hero+image.jpg&slot=hero&content_type=image%2Fjpeg&size_bytes=11',
    );
    assert.deepEqual(calls[1], {
      path: '/admin/storefront/upload-complete',
      method: 'POST',
      body: { asset_id: 'asset-1' },
    });
  });

  it('best-effort cleans the reservation when direct upload or finalize fails', async () => {
    for (const failure of ['put', 'finalize'] as const) {
      const reservation = {
        asset_id: `asset-${failure}`,
        upload_url: 'https://r2.example/upload',
        cdn_url: 'https://cdn.example.com/image.jpg',
        key: 'storefront/staging/image',
        max_size_bytes: MAX_STOREFRONT_IMAGE_BYTES,
      };
      const { calls, transport } = recordingTransport(
        failure === 'put'
          ? [reservation, { status: 'deleted', asset_id: reservation.asset_id }]
          : [reservation, undefined, { status: 'deleted', asset_id: reservation.asset_id }],
      );
      const fetchImpl = mock.fn(async () =>
        failure === 'put'
          ? new Response('storage unavailable', { status: 503 })
          : new Response('', { status: 200 }),
      );

      await assert.rejects(
        uploadStorefrontImage(
          new File(['image'], 'about.webp', { type: 'image/webp' }),
          'about',
          transport,
          fetchImpl as unknown as typeof fetch,
        ),
      );

      assert.equal(
        calls.at(-1)?.path,
        `/admin/storefront/upload?asset_id=${reservation.asset_id}`,
      );
      assert.equal(calls.at(-1)?.method, 'DELETE');
    }
  });
});
