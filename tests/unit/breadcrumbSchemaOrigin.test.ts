import assert from 'node:assert/strict';
import test from 'node:test';

import { getBreadcrumbSchemaOrigin } from '../../app/components/seo/BreadcrumbSchema';

const originalFrontendUrl = process.env.FRONTEND_URL;
const originalSiteUrl = process.env.NEXT_PUBLIC_SITE_URL;

function restoreEnv() {
  if (originalFrontendUrl === undefined) {
    delete process.env.FRONTEND_URL;
  } else {
    process.env.FRONTEND_URL = originalFrontendUrl;
  }

  if (originalSiteUrl === undefined) {
    delete process.env.NEXT_PUBLIC_SITE_URL;
  } else {
    process.env.NEXT_PUBLIC_SITE_URL = originalSiteUrl;
  }
}

test.afterEach(() => {
  restoreEnv();
});

test('breadcrumb schema origin falls back when the configured frontend URL uses the invalid TLD', () => {
  process.env.FRONTEND_URL = 'https://build.thespecialwedding.invalid';
  delete process.env.NEXT_PUBLIC_SITE_URL;

  assert.equal(getBreadcrumbSchemaOrigin(), 'https://thespecialwedding.io');
});

test('breadcrumb schema origin skips invalid higher-priority URLs before using a valid override', () => {
  process.env.FRONTEND_URL = 'https://build.thespecialwedding.invalid';
  process.env.NEXT_PUBLIC_SITE_URL = 'https://staging.thespecialwedding.io';

  assert.equal(getBreadcrumbSchemaOrigin(), 'https://staging.thespecialwedding.io');
});

test('breadcrumb schema origin accepts a valid http or https site URL override', () => {
  delete process.env.FRONTEND_URL;
  process.env.NEXT_PUBLIC_SITE_URL = 'https://staging.thespecialwedding.io/some/path';

  assert.equal(getBreadcrumbSchemaOrigin(), 'https://staging.thespecialwedding.io');
});

test('breadcrumb schema origin ignores unsupported URL schemes', () => {
  process.env.FRONTEND_URL = 'ftp://thespecialwedding.io';
  process.env.NEXT_PUBLIC_SITE_URL = 'https://thespecialwedding.io';

  assert.equal(getBreadcrumbSchemaOrigin(), 'https://thespecialwedding.io');
});
