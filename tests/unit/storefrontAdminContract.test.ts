import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { after, afterEach, before, describe, it, mock } from 'node:test';
import React from 'react';
import { cleanup, fireEvent, render } from '@testing-library/react';

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
let domHandle: ReturnType<typeof installDom> | null = null;

describe('storefront admin workflow contract', () => {
  before(async () => {
    domHandle = installDom();
    ({ StorefrontImagePicker } = await import(
      '../../app/components/storefront/StorefrontImagePicker'
    ));
    ({ StorefrontView } = await import('../../app/components/storefront/StorefrontView'));
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
});
