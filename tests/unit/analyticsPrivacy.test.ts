import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import {
  filterSensitiveUmamiPayload,
  isAnalyticsSensitivePath,
  UMAMI_BEFORE_SEND_HANDLER_NAME,
  UMAMI_PRIVACY_GUARD_SCRIPT,
} from '../../app/utils/analyticsPrivacy';

const rootLayoutSource = readFileSync(
  new URL('../../app/layout.tsx', import.meta.url),
  'utf8',
);

test('routes every global Umami loader through the pathname-aware boundary', () => {
  const guardPosition = rootLayoutSource.indexOf('tsw-umami-privacy-guard');
  const boundaryPosition = rootLayoutSource.indexOf(
    '<UmamiAnalyticsBoundary config={umamiConfig} />',
  );

  assert.ok(guardPosition >= 0);
  assert.ok(boundaryPosition > guardPosition);
  assert.doesNotMatch(rootLayoutSource, /<UmamiRuntimeLoader\b/);
  assert.doesNotMatch(rootLayoutSource, /<Script\b[^>]*data-website-id/);
});

test('classifies only the first-party DNS instruction route family as sensitive', () => {
  assert.equal(isAnalyticsSensitivePath('/domain-instructions'), true);
  assert.equal(isAnalyticsSensitivePath('/domain-instructions/secret-token'), true);
  assert.equal(isAnalyticsSensitivePath('/domain-instructions/secret-token/print'), true);

  assert.equal(isAnalyticsSensitivePath('/'), false);
  assert.equal(isAnalyticsSensitivePath('/admin/packages'), false);
  assert.equal(isAnalyticsSensitivePath('/domain-instructions-public/secret-token'), false);
  assert.equal(isAnalyticsSensitivePath(null), false);
});

test('drops sensitive Umami payloads without rewriting or retaining the tokenized URL', () => {
  const sensitive = {
    website: 'site-id',
    url: 'https://thespecialwedding.io/domain-instructions/secret-token?source=email',
  };
  assert.equal(filterSensitiveUmamiPayload(sensitive), false);
  assert.equal(
    filterSensitiveUmamiPayload({
      website: 'site-id',
      url: '/features',
      referrer: 'https://thespecialwedding.io/domain-instructions/secret-token',
    }),
    false,
  );

  const ordinary = {
    website: 'site-id',
    url: '/admin/packages?storefront=domain',
  };
  assert.equal(filterSensitiveUmamiPayload(ordinary), ordinary);
  assert.deepEqual(ordinary, {
    website: 'site-id',
    url: '/admin/packages?storefront=domain',
  });

  const eventWithoutUrl = { website: 'site-id', name: 'pricing_viewed' };
  assert.equal(filterSensitiveUmamiPayload(eventWithoutUrl), eventWithoutUrl);
  assert.equal(filterSensitiveUmamiPayload({ url: 'https://%' }), false);
});

test('installs a named before-send guard without logging or persisting route data', () => {
  assert.match(UMAMI_BEFORE_SEND_HANDLER_NAME, /^__[A-Za-z0-9]+$/);
  assert.match(UMAMI_PRIVACY_GUARD_SCRIPT, /window\[handlerName\]/);
  assert.doesNotMatch(
    UMAMI_PRIVACY_GUARD_SCRIPT,
    /console\.|localStorage|sessionStorage|document\.cookie|sendBeacon/,
  );

  const fakeWindow: Record<string, unknown> = {};
  const installGuard = new Function('window', 'URL', UMAMI_PRIVACY_GUARD_SCRIPT);
  installGuard(fakeWindow, URL);
  const handler = fakeWindow[UMAMI_BEFORE_SEND_HANDLER_NAME];
  assert.equal(typeof handler, 'function');
  assert.equal(
    (handler as (type: string, payload: Record<string, unknown>) => unknown)(
      'event',
      { url: '/domain-instructions/secret-token' },
    ),
    false,
  );
  const ordinary = { url: '/features' };
  assert.equal(
    (handler as (type: string, payload: Record<string, unknown>) => unknown)(
      'event',
      ordinary,
    ),
    ordinary,
  );
  assert.equal(
    (handler as (type: string, payload: Record<string, unknown>) => unknown)(
      'event',
      {
        url: '/features',
        referrer: 'https://thespecialwedding.io/domain-instructions/secret-token',
      },
    ),
    false,
  );
});
