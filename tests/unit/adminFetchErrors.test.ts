import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { isAbortLikeFetchError } from '@/admin/utils/adminFetchErrors';

describe('adminFetchErrors', () => {
  it('identifies browser abort-like fetch failures', () => {
    assert.equal(isAbortLikeFetchError(new DOMException('Aborted', 'AbortError')), true);
    assert.equal(isAbortLikeFetchError(new TypeError('Failed to fetch')), true);
  });

  it('keeps real errors visible', () => {
    assert.equal(isAbortLikeFetchError(new Error('500')), false);
    assert.equal(isAbortLikeFetchError(new TypeError('Unexpected token')), false);
    assert.equal(isAbortLikeFetchError(null), false);
  });
});
