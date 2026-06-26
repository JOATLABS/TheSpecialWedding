import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { isIgnorableEngagementSignalsError } from '../../app/admin/utils/engagementSignals';

describe('planner engagement signals error handling', () => {
  it('ignores aborted and interrupted background fetches', () => {
    assert.equal(isIgnorableEngagementSignalsError(new DOMException('Aborted', 'AbortError')), true);
    assert.equal(isIgnorableEngagementSignalsError(new TypeError('Failed to fetch')), true);
  });

  it('keeps unexpected engagement signal errors visible', () => {
    assert.equal(isIgnorableEngagementSignalsError(new Error('bad payload')), false);
  });
});
