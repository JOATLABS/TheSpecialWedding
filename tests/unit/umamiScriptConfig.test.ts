import assert from 'node:assert/strict';
import test from 'node:test';

import { resolveUmamiScriptConfig } from '../../app/utils/umamiScriptConfig';

test('uses explicit public Umami script vars when configured', () => {
  assert.deepEqual(
    resolveUmamiScriptConfig({
      NEXT_PUBLIC_UMAMI_WEBSITE_ID: 'site-public',
      NEXT_PUBLIC_UMAMI_SRC: 'https://umami.thespecialwedding.io/script.js',
      UMAMI_WEBSITE_ID: 'site-server',
      UMAMI_DASHBOARD_URL: 'https://analytics.example.com',
    }),
    {
      websiteId: 'site-public',
      src: 'https://umami.thespecialwedding.io/script.js',
    },
  );
});

test('falls back to server Umami id and public dashboard URL', () => {
  assert.deepEqual(
    resolveUmamiScriptConfig({
      UMAMI_WEBSITE_ID: 'site-server',
      UMAMI_DASHBOARD_URL: 'https://umami.thespecialwedding.io',
    }),
    {
      websiteId: 'site-server',
      src: 'https://umami.thespecialwedding.io/script.js',
    },
  );
});

test('can derive a public script origin from a public API base', () => {
  assert.deepEqual(
    resolveUmamiScriptConfig({
      UMAMI_WEBSITE_ID: 'site-server',
      UMAMI_API_BASE: 'https://umami.thespecialwedding.io/api',
    }),
    {
      websiteId: 'site-server',
      src: 'https://umami.thespecialwedding.io/script.js',
    },
  );
});

test('does not expose local or private Umami URLs to the public page', () => {
  assert.equal(
    resolveUmamiScriptConfig({
      UMAMI_WEBSITE_ID: 'site-server',
      UMAMI_DASHBOARD_URL: 'http://localhost:3000',
      UMAMI_API_BASE: 'http://umami-service:3000/api',
    }),
    null,
  );
});

test('does not emit config without a website id', () => {
  assert.equal(
    resolveUmamiScriptConfig({
      NEXT_PUBLIC_UMAMI_SRC: 'https://umami.thespecialwedding.io/script.js',
      UMAMI_DASHBOARD_URL: 'https://umami.thespecialwedding.io',
    }),
    null,
  );
});
