import assert from 'node:assert/strict';
import { after, afterEach, before, describe, it } from 'node:test';
import React from 'react';
import { cleanup, fireEvent, render } from '@testing-library/react';

import { installDom } from './testDom';

let PublicMicrositeFooter: typeof import('../../app/components/landing-page/PublicMicrositeFooter').PublicMicrositeFooter;
let PLATFORM_MARKETING_URL: typeof import('../../app/components/landing-page/PublicMicrositeFooter').PLATFORM_MARKETING_URL;
let domHandle: ReturnType<typeof installDom> | null = null;

describe('public microsite platform footer', () => {
  before(async () => {
    domHandle = installDom();
    ({ PublicMicrositeFooter, PLATFORM_MARKETING_URL } = await import(
      '../../app/components/landing-page/PublicMicrositeFooter'
    ));
  });

  afterEach(() => {
    cleanup();
    delete window.umami;
  });

  after(() => {
    domHandle?.cleanup();
    domHandle = null;
  });

  it('links the canonical brand lockup to the marketing site and tracks the referral', () => {
    const tracked: Array<[string, Record<string, unknown> | undefined]> = [];
    window.umami = {
      track: (name, data) => tracked.push([name, data]),
    };

    const view = render(<PublicMicrositeFooter />);
    const footer = view.container.querySelector('[data-microsite-footer="primary"]');
    const brandLink = view.getByRole('link', {
      name: 'Visit The Special Wedding (opens in a new tab)',
    });

    assert.equal(footer?.id, 'footer');
    assert.equal(brandLink.getAttribute('href'), PLATFORM_MARKETING_URL);
    assert.equal(brandLink.getAttribute('target'), '_blank');
    assert.equal(brandLink.getAttribute('rel'), 'noopener noreferrer');
    assert.equal(brandLink.getAttribute('referrerpolicy'), 'no-referrer');
    const marketingUrl = new URL(brandLink.getAttribute('href') || '');
    assert.equal(marketingUrl.origin, 'https://thespecialwedding.io');
    assert.equal(marketingUrl.searchParams.get('utm_source'), 'wedding_microsite');
    for (const sensitiveKey of ['slug', 'guest', 'token', 'email', 'phone', 'wedding_id']) {
      assert.equal(marketingUrl.searchParams.has(sensitiveKey), false);
    }
    assert.ok(view.getByText('THE SPECIAL'));
    assert.ok(view.getByText('Wedding'));
    assert.match(view.container.innerHTML, /var\(--theme-secondary-light/);
    assert.match(view.container.innerHTML, /var\(--theme-accent-light/);

    fireEvent.click(brandLink);

    assert.deepEqual(tracked, [[
      'microsite_platform_brand_clicked',
      { location: 'footer' },
    ]]);
  });

  it('keeps contextual legal actions interactive in the primary footer', () => {
    let privacyClicks = 0;
    let termsClicks = 0;
    const view = render(
      <PublicMicrositeFooter
        onPrivacy={() => {
          privacyClicks += 1;
        }}
        onTerms={() => {
          termsClicks += 1;
        }}
      />,
    );

    fireEvent.click(view.getByRole('button', { name: 'Privacy' }));
    fireEvent.click(view.getByRole('button', { name: 'Terms' }));

    assert.equal(privacyClicks, 1);
    assert.equal(termsClicks, 1);
  });

  it('renders the infinite-scroll clone without duplicate focus targets or ids', () => {
    const view = render(<PublicMicrositeFooter isClone />);
    const footer = view.container.querySelector('[data-microsite-footer="clone"]');

    assert.equal(footer?.hasAttribute('id'), false);
    assert.equal(view.container.querySelectorAll('a, button, [tabindex]').length, 0);
    assert.ok(view.getByText('Privacy'));
    assert.ok(view.getByText('Terms'));
  });

  it('keeps a primary and clone pair to one interactive attribution and one footer id', () => {
    const view = render(
      <>
        <PublicMicrositeFooter onPrivacy={() => {}} onTerms={() => {}} />
        <PublicMicrositeFooter isClone />
      </>,
    );

    assert.equal(
      view.getAllByRole('link', {
        name: 'Visit The Special Wedding (opens in a new tab)',
      }).length,
      1,
    );
    assert.equal(view.getAllByRole('button', { name: 'Privacy' }).length, 1);
    assert.equal(view.getAllByRole('button', { name: 'Terms' }).length, 1);
    assert.equal(view.container.querySelectorAll('#footer').length, 1);

    const svgIds = Array.from(view.container.querySelectorAll('svg [id]')).map(
      (node) => node.id,
    );
    assert.equal(new Set(svgIds).size, svgIds.length);
  });
});
