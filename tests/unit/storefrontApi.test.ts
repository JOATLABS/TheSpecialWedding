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
import * as storefrontApiModule from '../../app/services/storefrontApi';

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
  it('exposes and maps the production custom-domain lifecycle without leaking server DTOs', async () => {
    const api = storefrontApiModule as unknown as Record<string, (...args: any[]) => any>;
    for (const operation of [
      'preflightCustomDomain',
      'claimCustomDomain',
      'verifyCustomDomain',
      'getCustomDomainStatus',
      'observeCustomDomain',
      'startCustomDomainConnect',
      'completeCustomDomainConnect',
      'retryCustomDomainVerification',
      'sendCustomDomainInstructions',
      'getCustomDomainInstructionLinks',
      'normalizeStorefrontError',
    ]) {
      assert.equal(typeof api[operation], 'function', `${operation} must be exported`);
    }

    const raw = {
      hostname: 'events.customer.example',
      host_type: 'subdomain',
      intent: 'new',
      recommended_flow: 'manual',
      authoritative_dns: {
        zone: 'customer.example',
        provider: 'cloudflare',
        provider_name: 'Cloudflare',
        nameservers: ['anna.ns.cloudflare.com'],
        control_panel_url: 'https://dash.cloudflare.com/example/dns',
      },
      registrar: 'Namecheap',
      platform_provider: 'Cloudflare for The Special Wedding',
      domain_connect_supported: false,
      self_service_allowed: false,
      customer_action: 'Keep the current routing unchanged and request an assisted cutover.',
      expected_records: [
        {
          type: 'CNAME',
          name: 'events.customer.example',
          value: 'domains.thespecialwedding.com',
          ttl: 300,
          purpose: 'storefront_routing',
        },
      ],
      observed_records: [],
      conflicts: [
        {
          code: 'cloudflare_o2o_migration_requires_assistance',
          record_type: 'NS',
          values: ['anna.ns.cloudflare.com'],
          message: 'Cloudflare-to-Cloudflare migration requires an assisted cutover.',
        },
      ],
    };
    const { calls, transport } = recordingTransport([raw]);
    const mapped = await api.preflightCustomDomain(
      'events.customer.example',
      'new',
      transport,
    );

    assert.equal(mapped.hostType, 'subdomain');
    assert.equal(mapped.dnsProvider.name, 'Cloudflare');
    assert.equal(mapped.dnsProvider.controlPanelUrl, 'https://dash.cloudflare.com/example/dns');
    assert.equal(mapped.expectedRecords[0].fqdn, 'events.customer.example');
    assert.equal(mapped.expectedRecords[0].relativeHost, 'events');
    assert.equal(mapped.expectedRecords[0].purpose, 'storefront_routing');
    assert.equal(mapped.selfServiceAllowed, false);
    assert.equal(
      mapped.customerAction,
      'Keep the current routing unchanged and request an assisted cutover.',
    );
    assert.equal(
      mapped.conflicts[0].message,
      'Cloudflare-to-Cloudflare migration requires an assisted cutover.',
    );
    assert.deepEqual(calls, [
      {
        path: '/admin/storefront/custom-domain/preflight',
        method: 'POST',
        body: { domain: 'events.customer.example', intent: 'new' },
      },
    ]);
  });

  it('targets claim, verification, Domain Connect, retry, and instruction endpoints exactly', async () => {
    const api = storefrontApiModule as unknown as Record<string, (...args: any[]) => any>;
    const status = {
      attempt_id: 'attempt_1',
      hostname: 'events.customer.example',
      intent: 'new',
      application_status: 'dns_setup_pending',
      action: 'action_required',
      ownership_status: 'pending',
      routing_dns_status: 'pending',
      provider_hostname_status: 'not_started',
      ssl_status: 'not_started',
      https_status: 'not_started',
      conflict_code: null,
      next_check_at: '2026-07-15T17:05:00Z',
      expected_records: [],
      observed_records: [],
      conflicts: [],
    };
    const { calls, transport } = recordingTransport([
      status,
      status,
      status,
      status,
      status,
      { authorization_url: 'https://dns.example/authorize', attempt_id: 'attempt_1' },
      status,
      status,
      {
        status: 'sent',
        link_id: 'sfil_receipt_1',
        state: 'active',
        created_at: '2026-07-15T17:05:00Z',
        expires_at: '2026-07-22T17:05:00Z',
        recipient_hint: 'd***@e***.com',
      },
      {
        links: [
          {
            link_id: 'sfil_receipt_1',
            state: 'active',
            created_at: '2026-07-15T17:05:00Z',
            expires_at: '2026-07-22T17:05:00Z',
            recipient_hint: 'd***@e***.com',
          },
        ],
      },
      { status: 'revoked' },
    ]);

    await api.claimCustomDomain('events.customer.example', 'new', transport);
    const verified = await api.verifyCustomDomain(transport, 'attempt_1');
    await api.getCustomDomainStatus(transport);
    await api.observeCustomDomain('attempt_1', transport);
    await api.getCustomDomainStatus(transport, 'attempt_1');
    const authorization = await api.startCustomDomainConnect('attempt_1', transport);
    await api.completeCustomDomainConnect('attempt_1', transport);
    await api.retryCustomDomainVerification('attempt_1', transport);
    const instructionReceipt = await api.sendCustomDomainInstructions(
      { attemptId: 'attempt_1', email: 'dns@example.com', note: 'Please add these.' },
      transport,
    );
    const instructionLinks = await api.getCustomDomainInstructionLinks(
      'attempt_1',
      transport,
    );
    await api.revokeCustomDomainInstructions(instructionReceipt.linkId, transport);

    assert.equal(authorization.authorizationUrl, 'https://dns.example/authorize');
    assert.deepEqual(instructionReceipt, {
      status: 'sent',
      linkId: 'sfil_receipt_1',
      state: 'active',
      createdAt: '2026-07-15T17:05:00Z',
      expiresAt: '2026-07-22T17:05:00Z',
      recipientHint: 'd***@e***.com',
    });
    assert.deepEqual(instructionLinks, [
      {
        linkId: 'sfil_receipt_1',
        state: 'active',
        createdAt: '2026-07-15T17:05:00Z',
        expiresAt: '2026-07-22T17:05:00Z',
        recipientHint: 'd***@e***.com',
      },
    ]);
    assert.equal(verified.conflictCode, null);
    assert.equal(verified.nextCheckAt, '2026-07-15T17:05:00Z');
    assert.deepEqual(calls, [
      {
        path: '/admin/storefront/custom-domain/claim',
        method: 'POST',
        body: { domain: 'events.customer.example', intent: 'new' },
      },
      {
        path: '/admin/storefront/custom-domain/verify',
        method: 'POST',
        body: { attempt_id: 'attempt_1' },
      },
      { path: '/admin/storefront/custom-domain/status', method: 'GET', body: undefined },
      {
        path: '/admin/storefront/custom-domain/observe',
        method: 'POST',
        body: { attempt_id: 'attempt_1' },
      },
      {
        path: '/admin/storefront/custom-domain/status?attempt_id=attempt_1',
        method: 'GET',
        body: undefined,
      },
      {
        path: '/admin/storefront/custom-domain/domain-connect/authorize',
        method: 'POST',
        body: { attempt_id: 'attempt_1' },
      },
      {
        path: '/admin/storefront/custom-domain/domain-connect/complete',
        method: 'POST',
        body: { attempt_id: 'attempt_1' },
      },
      {
        path: '/admin/storefront/custom-domain/retry',
        method: 'POST',
        body: { attempt_id: 'attempt_1' },
      },
      {
        path: '/admin/storefront/custom-domain/instructions',
        method: 'POST',
        body: {
          attempt_id: 'attempt_1',
          email: 'dns@example.com',
          note: 'Please add these.',
        },
      },
      {
        path: '/admin/storefront/custom-domain/instructions?attempt_id=attempt_1',
        method: 'GET',
        body: undefined,
      },
      {
        path: '/admin/storefront/custom-domain/instructions/sfil_receipt_1',
        method: 'DELETE',
        body: undefined,
      },
    ]);
  });

  it('normalizes typed and legacy FastAPI errors into customer-safe messages', () => {
    const api = storefrontApiModule as unknown as Record<string, (...args: any[]) => any>;
    const typed = api.normalizeStorefrontError(
      new Error(
        JSON.stringify({
          detail: {
            code: 'hostname_reserved',
            message: 'This domain is already connected.',
            customer_action: 'Verify ownership or contact support.',
            retryable: false,
            support_id: 'SUP-777',
          },
        }),
      ),
      'Unable to check the domain',
    );
    assert.equal(typed.message, 'This domain is already connected.');
    assert.equal(typed.customerAction, 'Verify ownership or contact support.');
    assert.equal(typed.supportId, 'SUP-777');

    const legacy = api.normalizeStorefrontError(
      new Error('{"detail":"Storefront custom-domain CNAME target is not configured"}'),
      'Unable to check the domain',
    );
    assert.equal(legacy.code, 'custom_domain_configuration_unavailable');
    assert.match(legacy.message, /temporarily unavailable/i);
    assert.doesNotMatch(legacy.message, /\{|detail|CNAME target/i);

    const mediaUnavailable = api.normalizeStorefrontError(
      new Error(
        JSON.stringify({
          detail: 'Storefront image storage is temporarily unavailable',
        }),
      ),
      'Unable to upload the image.',
    );
    assert.equal(
      mediaUnavailable.message,
      'Storefront image storage is temporarily unavailable',
    );
    assert.equal(mediaUnavailable.retryable, true);

    const productionEnvelope = api.normalizeStorefrontError(
      new Error(
        JSON.stringify({
          error: {
            code: 'dns_routing_mismatch',
            message: 'The routing record does not match yet.',
            customer_action: 'Replace the CNAME value and check again.',
            retryable: true,
            support_id: 'SUP-778',
            field_errors: {},
          },
        }),
      ),
      'Unable to check the domain',
    );
    assert.equal(productionEnvelope.code, 'dns_routing_mismatch');
    assert.equal(productionEnvelope.message, 'The routing record does not match yet.');
    assert.equal(
      productionEnvelope.customerAction,
      'Replace the CNAME value and check again.',
    );
    assert.equal(productionEnvelope.supportId, 'SUP-778');

    const providerDocument = api.normalizeStorefrontError(
      new Error('<Error><Code>AccessDenied</Code><RequestId>internal-id</RequestId></Error>'),
      'Unable to upload the image.',
    );
    assert.equal(providerDocument.message, 'Unable to upload the image.');
    assert.doesNotMatch(providerDocument.message, /AccessDenied|RequestId|</i);

    const stackTrace = api.normalizeStorefrontError(
      new Error('TypeError: secret failure\n    at internal/service.ts:12:3'),
      'Unable to save storefront settings.',
    );
    assert.equal(stackTrace.message, 'Unable to save storefront settings.');

    const wrappedTrace = api.normalizeStorefrontError(
      new Error(
        JSON.stringify({
          error: {
            code: 'provider_failure',
            message: 'Traceback: internal secret\n    at provider.ts:9:1',
            customer_action: '<script>retry with secret</script>',
            retryable: true,
            support_id: '{raw-provider-id}',
          },
        }),
      ),
      'The provider operation is temporarily unavailable.',
    );
    assert.equal(wrappedTrace.message, 'The provider operation is temporarily unavailable.');
    assert.equal(wrappedTrace.customerAction, null);
    assert.equal(wrappedTrace.supportId, null);

    const rawProviderDiagnostic = api.normalizeStorefrontError(
      new Error(
        'Cloudflare API token secret-token failed for zone 123 at 10.0.0.4',
      ),
      'The provider operation is temporarily unavailable.',
    );
    assert.equal(
      rawProviderDiagnostic.message,
      'The provider operation is temporarily unavailable.',
    );
    assert.doesNotMatch(
      rawProviderDiagnostic.message,
      /secret-token|zone 123|10\.0\.0\.4/i,
    );
  });

  it('fails closed on unknown instruction send, list, and revoke receipt states', async () => {
    const api = storefrontApiModule as unknown as Record<string, (...args: any[]) => any>;
    const receipt = {
      status: 'sent',
      link_id: 'sfil_receipt_1',
      state: 'active',
      created_at: '2026-07-15T17:05:00Z',
      expires_at: '2026-07-22T17:05:00Z',
      recipient_hint: 'd***@e***.com',
    };

    await assert.rejects(
      api.sendCustomDomainInstructions(
        { attemptId: 'attempt_1', email: 'dns@example.com' },
        async () => ({ ...receipt, status: 'queued' }),
      ),
      /unreadable receipt/i,
    );
    await assert.rejects(
      api.sendCustomDomainInstructions(
        { attemptId: 'attempt_1', email: 'dns@example.com' },
        async () => ({ ...receipt, state: 'provider_accepted' }),
      ),
      /unreadable receipt/i,
    );
    await assert.rejects(
      api.getCustomDomainInstructionLinks(
        'attempt_1',
        async () => ({ links: [{ ...receipt, state: 'revoked' }] }),
      ),
      /unreadable receipt/i,
    );
    await assert.rejects(
      api.revokeCustomDomainInstructions(
        'sfil_receipt_1',
        async () => ({ status: 'accepted' }),
      ),
      /unreadable receipt/i,
    );
  });

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
      {
        plan_id: 'signature',
        storefront_enabled: true,
        custom_domain_enabled: false,
        can_manage_existing_domain: false,
      },
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
