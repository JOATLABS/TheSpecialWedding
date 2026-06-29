import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { buildAdminApiUrl } from '@/admin/planner/buildAdminApiUrl';

describe('buildAdminApiUrl', () => {
  it('builds absolute URLs from the browser-relative proxy base', () => {
    const url = buildAdminApiUrl(
      '/api/proxy',
      '/admin/ai/weddings/wedding-1/insights',
      'http://127.0.0.1:3100',
    );

    assert.equal(
      url.toString(),
      'http://127.0.0.1:3100/api/proxy/admin/ai/weddings/wedding-1/insights',
    );
  });

  it('preserves absolute backend API bases', () => {
    const url = buildAdminApiUrl(
      'http://127.0.0.1:8000/',
      'admin/ai/weddings/wedding-1/insights',
      'http://127.0.0.1:3100',
    );

    assert.equal(
      url.toString(),
      'http://127.0.0.1:8000/admin/ai/weddings/wedding-1/insights',
    );
  });
});
