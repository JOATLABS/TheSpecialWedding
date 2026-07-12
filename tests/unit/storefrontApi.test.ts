import assert from 'node:assert/strict';
import { describe, it, mock } from 'node:test';

import {
  MAX_STOREFRONT_IMAGE_BYTES,
  connectCustomDomain,
  deleteStorefrontUpload,
  buildStorefrontSettingsPatch,
  getStorefrontAccess,
  getStorefrontPreviewData,
  getStorefrontPreviewSeed,
  getStorefrontPreviewUrl,
  getStorefrontSettings,
  refreshCustomDomain,
  removeCustomDomain,
  saveStorefrontSettings,
  uploadStorefrontImage,
  type StorefrontApiTransport,
  type StorefrontSettingsField,
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

  it('loads canonical owner preview data without requiring a persisted slug', async () => {
    const preview = {
      slug: 'luxe-light-events',
      storefront: {
        title: null,
        description: null,
        contact_email: null,
        contact_phone: null,
        hero_image_url: null,
        about_image_url: null,
        theme_color: '#0f172a',
        packages_enabled: true,
        reviews_enabled: true,
      },
      planner: { company_name: 'Luxe & Light', first_name: 'Ada', profile_image_url: null },
      packages: [],
      reviews: [],
    };
    const { calls, transport } = recordingTransport([preview]);

    assert.deepEqual(await getStorefrontPreviewSeed(transport), preview);
    assert.deepEqual(calls, [
      { path: '/admin/storefront/preview-data', method: 'GET', body: undefined },
    ]);
  });

  it('builds a dirty-field patch without replaying untouched concurrent fields', () => {
    const dirty = new Set<StorefrontSettingsField>(['title', 'contact_email']);
    const patch = buildStorefrontSettingsPatch(
      {
        slug: 'stale-slug',
        title: 'Updated title',
        contact_email: 'hello@example.com',
        hero_asset_id: 'stale-hero',
        is_published: false,
      },
      dirty,
    );

    assert.deepEqual(patch, {
      title: 'Updated title',
      contact_email: 'hello@example.com',
    });
    assert.equal('slug' in patch, false);
    assert.equal('hero_asset_id' in patch, false);
    assert.equal('is_published' in patch, false);
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

  it('cleans a finalized asset when the owning UI lifecycle closes during finalize', async () => {
    let resolveFinalize: ((asset: unknown) => void) | undefined;
    const finalizeResponse = new Promise<unknown>((resolve) => {
      resolveFinalize = resolve;
    });
    const calls: Array<{ path: string; method: string; body: unknown }> = [];
    let active = true;
    const transport: StorefrontApiTransport = async <T>(
      path: string,
      method = 'GET',
      body?: unknown,
    ): Promise<T | undefined> => {
      calls.push({ path, method, body });
      if (path.includes('upload-url')) {
        return {
          asset_id: 'late-asset',
          upload_url: 'https://r2.example/upload',
          cdn_url: 'https://cdn.example.com/late.jpg',
          key: 'storefront/staging/late',
          max_size_bytes: MAX_STOREFRONT_IMAGE_BYTES,
        } as T;
      }
      if (path === '/admin/storefront/upload-complete') {
        return (await finalizeResponse) as T;
      }
      if (path.includes('/admin/storefront/upload?')) {
        return { status: 'deleted', asset_id: 'late-asset' } as T;
      }
      throw new Error(`Unexpected request ${path}`);
    };
    const fetchImpl = mock.fn(async () => new Response('', { status: 200 }));

    const upload = uploadStorefrontImage(
      new File(['image'], 'late.jpg', { type: 'image/jpeg' }),
      'hero',
      transport,
      fetchImpl as unknown as typeof fetch,
      { isActive: () => active },
    );
    await new Promise((resolve) => setTimeout(resolve, 0));
    active = false;
    resolveFinalize?.({
      asset_id: 'late-asset',
      slot: 'hero',
      state: 'ready',
      key: 'storefront/hero/late.jpg',
      cdn_url: 'https://cdn.example.com/late.jpg',
      content_type: 'image/jpeg',
      size_bytes: 5,
    });

    await assert.rejects(upload, /lifecycle closed/i);
    assert.equal(calls.at(-1)?.path, '/admin/storefront/upload?asset_id=late-asset');
    assert.equal(calls.at(-1)?.method, 'DELETE');
  });

  it('cleans a reservation when the owning UI lifecycle closes during reserve', async () => {
    let resolveReservation: ((value: unknown) => void) | undefined;
    const reservation = new Promise<unknown>((resolve) => {
      resolveReservation = resolve;
    });
    let active = true;
    const calls: string[] = [];
    const transport: StorefrontApiTransport = async <T>(path: string): Promise<T | undefined> => {
      calls.push(path);
      if (path.includes('/upload-url?')) return (await reservation) as T;
      if (path.includes('/storefront/upload?')) {
        return { status: 'deleted', asset_id: 'reserve-late' } as T;
      }
      throw new Error(`Unexpected request ${path}`);
    };
    const upload = uploadStorefrontImage(
      new File(['image'], 'reserve.jpg', { type: 'image/jpeg' }),
      'hero',
      transport,
      mock.fn(async () => new Response('', { status: 200 })) as unknown as typeof fetch,
      { isActive: () => active },
    );
    active = false;
    resolveReservation?.({
      asset_id: 'reserve-late',
      upload_url: 'https://r2.example/upload',
      cdn_url: 'https://cdn.example.com/reserve.jpg',
      key: 'storefront/staging/reserve',
      max_size_bytes: MAX_STOREFRONT_IMAGE_BYTES,
    });

    await assert.rejects(upload, /lifecycle closed/i);
    assert.equal(calls.at(-1), '/admin/storefront/upload?asset_id=reserve-late');
  });

  it('cleans a reservation when the owning UI lifecycle closes during direct PUT', async () => {
    let resolvePut: ((value: Response) => void) | undefined;
    const put = new Promise<Response>((resolve) => {
      resolvePut = resolve;
    });
    let active = true;
    const { calls, transport } = recordingTransport([
      {
        asset_id: 'put-late',
        upload_url: 'https://r2.example/upload',
        cdn_url: 'https://cdn.example.com/put.jpg',
        key: 'storefront/staging/put',
        max_size_bytes: MAX_STOREFRONT_IMAGE_BYTES,
      },
      { status: 'deleted', asset_id: 'put-late' },
    ]);
    const upload = uploadStorefrontImage(
      new File(['image'], 'put.jpg', { type: 'image/jpeg' }),
      'hero',
      transport,
      mock.fn(async () => put) as unknown as typeof fetch,
      { isActive: () => active },
    );
    await Promise.resolve();
    active = false;
    resolvePut?.(new Response('', { status: 200 }));

    await assert.rejects(upload, /lifecycle closed/i);
    assert.equal(calls.at(-1)?.path, '/admin/storefront/upload?asset_id=put-late');
  });
});
