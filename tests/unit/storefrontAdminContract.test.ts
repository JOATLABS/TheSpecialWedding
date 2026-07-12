import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { after, afterEach, before, describe, it, mock } from 'node:test';
import React from 'react';
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import type {
  StorefrontPreviewData,
  StorefrontSettings,
} from '../../app/services/storefrontApi';

import { installDom } from './testDom';

const packagesSource = readFileSync('app/admin/packages/page.tsx', 'utf8');
const modalSource = readFileSync(
  'app/admin/packages/StorefrontSettingsModal.tsx',
  'utf8',
);
const domainSource = readFileSync(
  'app/admin/components/storefront/CustomDomainManager.tsx',
  'utf8',
);
const upgradeSource = readFileSync('app/components/ui/UpgradeModal.tsx', 'utf8');

let StorefrontImagePicker: typeof import('../../app/components/storefront/StorefrontImagePicker').StorefrontImagePicker;
let StorefrontView: typeof import('../../app/components/storefront/StorefrontView').StorefrontView;
let StorefrontSettingsDialog: typeof import('../../app/admin/packages/StorefrontSettingsModal').StorefrontSettingsDialog;
let StorefrontHttpVerification: typeof import('../../app/admin/components/storefront/CustomDomainManager').StorefrontHttpVerification;
let domHandle: ReturnType<typeof installDom> | null = null;

describe('storefront admin workflow contract', () => {
  before(async () => {
    domHandle = installDom();
    ({ StorefrontImagePicker } = await import(
      '../../app/components/storefront/StorefrontImagePicker'
    ));
    ({ StorefrontView } = await import('../../app/components/storefront/StorefrontView'));
    ({ StorefrontSettingsDialog } = await import(
      '../../app/admin/packages/StorefrontSettingsModal'
    ));
    ({ StorefrontHttpVerification } = await import(
      '../../app/admin/components/storefront/CustomDomainManager'
    ));
  });

  afterEach(() => {
    cleanup();
    mock.restoreAll();
  });

  after(() => {
    domHandle?.cleanup();
    domHandle = null;
  });

  it('gates the Packages entry with canonical access booleans and storefront upgrade copy', () => {
    assert.match(packagesSource, /getStorefrontAccess/);
    assert.match(packagesSource, /storefront_enabled/);
    assert.match(packagesSource, /custom_domain_enabled/);
    assert.doesNotMatch(packagesSource, /planId\.includes/);
    assert.doesNotMatch(packagesSource, /isPremium/);
    assert.match(packagesSource, /Planner Storefront/);
    assert.match(packagesSource, /\/admin\/planner\/billing/);

    assert.match(upgradeSource, /features\?: readonly string\[\]/);
    assert.match(upgradeSource, /ctaLabel\?: string/);
    assert.match(upgradeSource, /ctaHref\?: string/);
  });

  it('keeps design saves separate from immediate custom-domain operations', () => {
    assert.match(modalSource, /custom_domain_enabled/);
    assert.match(modalSource, /apply immediately/i);
    assert.doesNotMatch(modalSource, /custom_domain:\s*draft/);
    assert.match(domainSource, /connectCustomDomain/);
    assert.match(domainSource, /refreshCustomDomain/);
    assert.match(domainSource, /removeCustomDomain/);
    assert.match(domainSource, /ownership_verification_http/);
    assert.match(domainSource, /HTTP verification URL/);
    assert.match(domainSource, /HTTP verification body/);
    assert.doesNotMatch(domainSource, /cname\.thespecialwedding\.com/);
  });

  it('provides slug, publication, contact, live preview, and Save & Preview controls', () => {
    assert.match(modalSource, /StorefrontView/);
    assert.match(modalSource, /Edit design/);
    assert.match(modalSource, /Live preview/);
    assert.match(modalSource, /Storefront URL/);
    assert.match(modalSource, /Publish storefront/);
    assert.match(modalSource, /Contact email/);
    assert.match(modalSource, /Contact phone/);
    assert.match(modalSource, /Save & Preview/);
    assert.match(modalSource, /getStorefrontPreviewUrl/);
    assert.match(modalSource, /new URL\(getStorefrontPreviewUrl/);
    assert.match(modalSource, /window\.location\.origin/);
    assert.match(modalSource, /previewMode/);
    assert.match(modalSource, /failedIds/);
    assert.match(modalSource, /retry before closing/i);
    assert.match(modalSource, /apiRequestRef/);
    assert.match(modalSource, /stableTransport/);
    assert.match(modalSource, /getStorefrontPreviewSeed/);
    assert.doesNotMatch(packagesSource, /previewPackages=/);
    assert.doesNotMatch(modalSource, /useState<any>/);
    assert.doesNotMatch(modalSource, /prev: any/);
  });

  it('exposes a native, labelled file input for pointer and keyboard users', () => {
    const onFileSelect = mock.fn(async (_file: File) => undefined);
    const view = render(
      React.createElement(StorefrontImagePicker, {
        id: 'hero-picker',
        label: 'Hero image',
        hint: 'Landscape image',
        imageUrl: null,
        uploading: false,
        onFileSelect,
        onRemove: () => undefined,
      }),
    );

    const input = view.getByLabelText(/hero image/i);
    assert.equal(input.getAttribute('type'), 'file');
    assert.equal(input.getAttribute('accept'), 'image/jpeg,image/png,image/webp');

    const file = new File(['image'], 'hero.jpg', { type: 'image/jpeg' });
    fireEvent.change(input, { target: { files: [file] } });
    assert.equal(onFileSelect.mock.callCount(), 1);
    assert.equal(onFileSelect.mock.calls[0].arguments[0], file);
  });

  it('renders current draft packages and reviews while disabling inquiries in preview mode', () => {
    const view = render(
      React.createElement(StorefrontView, {
        previewMode: true,
        data: {
          slug: 'jane-events',
          storefront: {
            title: 'Unsaved new title',
            description: 'A live draft description',
            contact_email: 'hello@example.com',
            contact_phone: '+1 555 0100',
            hero_image_url: null,
            about_image_url: null,
            theme_color: '#334155',
            packages_enabled: true,
            reviews_enabled: true,
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
              description: 'Everything handled',
              total_amount: 5000,
              currency: 'USD',
              services: [{ name: 'Vendor sourcing', description: null }],
            },
          ],
          reviews: [
            {
              _id: 'review-1',
              author_name: 'Alex',
              rating: 5,
              text: 'Wonderful planning experience',
              source: 'Google',
              date: '2026-07-01',
            },
          ],
        },
      }),
    );

    view.getAllByText('Unsaved new title');
    view.getByText('Full Planning');
    view.getByText('Vendor sourcing');
    view.getByText(/Wonderful planning experience/);
    const inquiryButton = view.getByRole('button', { name: /inquiries disabled in preview/i });
    assert.equal((inquiryButton as HTMLButtonElement).disabled, true);
  });

  it('renders HTTP-only custom-domain ownership verification instructions', () => {
    const view = render(
      React.createElement(StorefrontHttpVerification, {
        verification: {
          http_url: 'https://events.example.com/.well-known/cf-custom-hostname-challenge/token',
          http_body: 'verification-token-body',
        },
      }),
    );
    view.getByText('HTTP verification URL');
    view.getByText('HTTP verification body');
    view.getByText(/cf-custom-hostname-challenge/);
    view.getByText('verification-token-body');
  });

  it('fails closed on load errors and enables mutations only after a successful retry', async () => {
    let shouldFail = true;
    const settings = storefrontSettingsFixture();
    const preview = storefrontPreviewFixture();
    const transport = mock.fn(async <T>(path: string): Promise<T | undefined> => {
      if (shouldFail) {
        throw new Error('current owner state unavailable');
      }
      return (path.endsWith('/settings') ? { settings } : preview) as T;
    });
    const view = render(
      React.createElement(StorefrontSettingsDialog, {
        isOpen: true,
        onClose: () => undefined,
        access: {
          plan_id: 'signature',
          storefront_enabled: true,
          custom_domain_enabled: false,
        },
        transport,
      }),
    );

    await waitFor(() => view.getByText(/could not be loaded/i));
    assert.equal(
      (view.getByRole('button', { name: /save settings/i }) as HTMLButtonElement).disabled,
      true,
    );
    assert.equal(
      (view.getByRole('button', { name: /save & preview/i }) as HTMLButtonElement).disabled,
      true,
    );

    shouldFail = false;
    fireEvent.click(view.getByRole('button', { name: /retry loading storefront/i }));
    await waitFor(() => view.getByDisplayValue('Luxe Events'));
    assert.equal(
      (view.getByRole('button', { name: /save settings/i }) as HTMLButtonElement).disabled,
      false,
    );
  });

  it('blocks both save actions when an editable storefront slug is blank', async () => {
    const user = userEvent.setup({ document: window.document });
    const settings = storefrontSettingsFixture();
    const preview = storefrontPreviewFixture();
    let postCount = 0;
    const transport = mock.fn(
      async <T>(path: string, method = 'GET'): Promise<T | undefined> => {
        if (path.endsWith('/settings') && method === 'POST') {
          postCount += 1;
          return { status: 'success', settings } as T;
        }
        if (path.endsWith('/settings')) return { settings } as T;
        if (path.endsWith('/preview-data')) return preview as T;
        throw new Error(`Unexpected request ${path}`);
      },
    );
    const openWindow = mock.method(window, 'open', () => null);
    const view = render(
      React.createElement(StorefrontSettingsDialog, {
        isOpen: true,
        onClose: () => undefined,
        access: {
          plan_id: 'signature',
          storefront_enabled: true,
          custom_domain_enabled: false,
        },
        transport,
      }),
    );

    const slug = await waitFor(() => view.getByLabelText(/storefront url/i));
    await user.clear(slug);
    await user.type(slug, '   ');
    await user.click(view.getByRole('switch', { name: /publish storefront/i }));
    assert.equal((slug as HTMLInputElement).value, '   ');
    await user.click(view.getByRole('button', { name: /^save settings$/i }));

    await waitFor(() => view.getByRole('alert'));
    assert.match(view.getByRole('alert').textContent ?? '', /storefront url.*required/i);
    assert.equal(postCount, 0);

    await user.click(view.getByRole('button', { name: /save & preview/i }));
    assert.equal(postCount, 0);
    assert.equal(openWindow.mock.callCount(), 0);
  });

  it('sends only dirty fields and refreshes concurrent canonical publication and assets', async () => {
    const user = userEvent.setup({ document: window.document });
    let canonical = storefrontSettingsFixture();
    let preview = storefrontPreviewFixture();
    let savedBody: unknown;
    const transport = mock.fn(
      async <T>(path: string, method = 'GET', body?: unknown): Promise<T | undefined> => {
        if (path.endsWith('/settings') && method === 'POST') {
          savedBody = body;
          canonical = {
            ...canonical,
            title: 'Updated locally',
            is_published: true,
            hero_asset_id: 'concurrent-hero',
            revision: canonical.revision + 2,
          };
          preview = {
            ...preview,
            storefront: {
              ...preview.storefront,
              title: 'Updated locally',
              hero_image_url: 'https://cdn.example.com/concurrent-hero.jpg',
            },
          };
          return { status: 'success', settings: canonical } as T;
        }
        if (path.endsWith('/settings')) {
          return { settings: canonical } as T;
        }
        if (path.endsWith('/preview-data')) {
          return preview as T;
        }
        throw new Error(`Unexpected request ${path}`);
      },
    );
    const view = render(
      React.createElement(StorefrontSettingsDialog, {
        isOpen: true,
        onClose: () => undefined,
        access: {
          plan_id: 'signature',
          storefront_enabled: true,
          custom_domain_enabled: false,
        },
        transport,
      }),
    );
    const title = await waitFor(() => view.getByLabelText(/storefront title/i));
    await user.clear(title);
    await user.type(title, 'Updated locally');
    await user.click(view.getByRole('button', { name: /save settings/i }));

    await waitFor(() => assert.deepEqual(savedBody, { title: 'Updated locally' }));
    await waitFor(() =>
      assert.equal(
        view.getByRole('switch', { name: /publish storefront/i }).getAttribute('aria-checked'),
        'true',
      ),
    );
  });

  it('reconciles an ambiguous save acknowledgement from canonical owner state', async () => {
    const user = userEvent.setup({ document: window.document });
    let canonical = storefrontSettingsFixture();
    let preview = storefrontPreviewFixture();
    const transport = mock.fn(
      async <T>(path: string, method = 'GET', body?: unknown): Promise<T | undefined> => {
        if (path.endsWith('/settings') && method === 'POST') {
          assert.deepEqual(body, {
            slug: 'Luxe Events New',
            description: 'Durably committed description',
          });
          canonical = {
            ...canonical,
            slug: 'luxe-events-new',
            description: 'Durably committed description',
            revision: canonical.revision + 1,
          };
          preview = {
            ...preview,
            slug: 'luxe-events-new',
            storefront: {
              ...preview.storefront,
              description: 'Durably committed description',
            },
          };
          throw new Error('connection closed after commit');
        }
        if (path.endsWith('/settings')) return { settings: canonical } as T;
        if (path.endsWith('/preview-data')) return preview as T;
        throw new Error(`Unexpected request ${path}`);
      },
    );
    const view = render(
      React.createElement(StorefrontSettingsDialog, {
        isOpen: true,
        onClose: () => undefined,
        access: {
          plan_id: 'signature',
          storefront_enabled: true,
          custom_domain_enabled: false,
        },
        transport,
      }),
    );
    const slug = await waitFor(() => view.getByLabelText(/storefront url/i));
    const description = await waitFor(() => view.getByLabelText(/^description$/i));
    await user.clear(slug);
    await user.type(slug, 'Luxe Events New');
    await user.type(description, 'Durably committed description');
    await user.click(view.getByRole('button', { name: /save settings/i }));

    await waitFor(() => view.getByText(/reconciled after an uncertain response/i));
    assert.equal(
      (view.getByLabelText(/^description$/i) as HTMLTextAreaElement).value,
      'Durably committed description',
    );
  });

  it('reports displaced stable cleanup failure without blocking a normal close', async () => {
    let canonical = storefrontSettingsFixture();
    let preview = storefrontPreviewFixture();
    const onClose = mock.fn(() => undefined);
    const transport = mock.fn(
      async <T>(path: string, method = 'GET', body?: unknown): Promise<T | undefined> => {
        if (path.endsWith('/settings') && method === 'POST') {
          assert.deepEqual(body, { hero_asset_id: null });
          canonical = { ...canonical, hero_asset_id: null, revision: canonical.revision + 1 };
          preview = {
            ...preview,
            storefront: { ...preview.storefront, hero_image_url: null },
          };
          return { status: 'success', settings: canonical } as T;
        }
        if (path.endsWith('/settings')) return { settings: canonical } as T;
        if (path.endsWith('/preview-data')) return preview as T;
        if (path.includes('/storefront/upload?asset_id=hero-old')) {
          throw new Error('temporary delete failure');
        }
        throw new Error(`Unexpected request ${path}`);
      },
    );
    const view = render(
      React.createElement(StorefrontSettingsDialog, {
        isOpen: true,
        onClose,
        access: {
          plan_id: 'signature',
          storefront_enabled: true,
          custom_domain_enabled: false,
        },
        transport,
      }),
    );
    const remove = await waitFor(() => view.getByRole('button', { name: /^remove$/i }));
    fireEvent.click(remove);
    fireEvent.click(view.getByRole('button', { name: /save settings/i }));

    await waitFor(() => view.getByText(/old image will be cleaned up/i));
    fireEvent.click(view.getByRole('button', { name: /^cancel$/i }));
    await waitFor(() => assert.equal(onClose.mock.callCount(), 1));
  });

  it('cleans a ready image that finishes after the settings dialog unmounts', async () => {
    const settings = storefrontSettingsFixture();
    const preview = storefrontPreviewFixture();
    let resolveFinalize: ((value: unknown) => void) | undefined;
    const finalize = new Promise<unknown>((resolve) => {
      resolveFinalize = resolve;
    });
    const calls: string[] = [];
    const transport = mock.fn(
      async <T>(path: string): Promise<T | undefined> => {
        calls.push(path);
        if (path.endsWith('/settings')) return { settings } as T;
        if (path.endsWith('/preview-data')) return preview as T;
        if (path.includes('/upload-url?')) {
          return {
            asset_id: 'late-ready',
            upload_url: 'https://r2.example/upload',
            cdn_url: 'https://cdn.example.com/late.jpg',
            key: 'storefront/staging/late',
            max_size_bytes: 5 * 1024 * 1024,
          } as T;
        }
        if (path.endsWith('/upload-complete')) return (await finalize) as T;
        if (path.includes('/storefront/upload?')) {
          return { status: 'deleted', asset_id: 'late-ready' } as T;
        }
        throw new Error(`Unexpected request ${path}`);
      },
    );
    const originalFetch = globalThis.fetch;
    const originalCreateObjectUrl = URL.createObjectURL;
    const originalRevokeObjectUrl = URL.revokeObjectURL;
    globalThis.fetch = mock.fn(async () => new Response('', { status: 200 })) as unknown as typeof fetch;
    URL.createObjectURL = () => 'blob:late-image';
    URL.revokeObjectURL = () => undefined;
    try {
      const view = render(
        React.createElement(StorefrontSettingsDialog, {
          isOpen: true,
          onClose: () => undefined,
          access: {
            plan_id: 'signature',
            storefront_enabled: true,
            custom_domain_enabled: false,
          },
          transport,
        }),
      );
      const input = await waitFor(() => view.getByLabelText(/about image/i));
      fireEvent.change(input, {
        target: { files: [new File(['image'], 'late.jpg', { type: 'image/jpeg' })] },
      });
      await waitFor(() => assert.equal(calls.some((path) => path.endsWith('/upload-complete')), true));
      view.unmount();
      resolveFinalize?.({
        asset_id: 'late-ready',
        slot: 'about',
        state: 'ready',
        key: 'storefront/hero/late.jpg',
        cdn_url: 'https://cdn.example.com/late.jpg',
        content_type: 'image/jpeg',
        size_bytes: 5,
      });
      await waitFor(() =>
        assert.equal(
          calls.some((path) => path.includes('/storefront/upload?asset_id=late-ready')),
          true,
        ),
      );
    } finally {
      globalThis.fetch = originalFetch;
      URL.createObjectURL = originalCreateObjectUrl;
      URL.revokeObjectURL = originalRevokeObjectUrl;
    }
  });
});

function storefrontSettingsFixture(): StorefrontSettings {
  return {
    slug: 'luxe-events',
    title: 'Luxe Events',
    description: null,
    contact_email: null,
    contact_phone: null,
    hero_asset_id: 'hero-old',
    about_asset_id: null,
    theme_color: '#0f172a',
    packages_enabled: true,
    reviews_enabled: true,
    is_published: false,
    published_at: null,
    created_at: null,
    updated_at: null,
    revision: 1,
    slug_editable: true,
    slug_persisted: true,
  };
}

function storefrontPreviewFixture(): StorefrontPreviewData {
  return {
    slug: 'luxe-events',
    storefront: {
      title: 'Luxe Events',
      description: null,
      contact_email: null,
      contact_phone: null,
      hero_image_url: 'https://cdn.example.com/hero-old.jpg',
      about_image_url: null,
      theme_color: '#0f172a',
      packages_enabled: true,
      reviews_enabled: true,
    },
    planner: {
      company_name: 'Luxe Events LLC',
      first_name: 'Ada',
      profile_image_url: null,
    },
    packages: [],
    reviews: [],
  };
}
