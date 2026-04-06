import assert from 'node:assert/strict';
import test from 'node:test';

import {
  BLOCKED_SUBSCRIPTION_STATUSES,
  isBlockedSubscriptionStatus,
  normalizeSubscriptionStatus,
} from '@/utils/subscriptionStatus';

test('normalizeSubscriptionStatus maps Stripe aliases to canonical values', () => {
  assert.equal(normalizeSubscriptionStatus('trialing'), 'trial');
  assert.equal(normalizeSubscriptionStatus('canceled'), 'cancelled');
  assert.equal(normalizeSubscriptionStatus('incomplete'), 'pending_payment');
  assert.equal(normalizeSubscriptionStatus('incomplete_expired'), 'expired');
  assert.equal(normalizeSubscriptionStatus('unpaid'), 'suspended');
});

test('blocked status helper includes billing-problem states after normalization', () => {
  assert.equal(isBlockedSubscriptionStatus('past_due'), true);
  assert.equal(isBlockedSubscriptionStatus('unpaid'), true);
  assert.equal(isBlockedSubscriptionStatus('pending_checkout'), true);
  assert.equal(BLOCKED_SUBSCRIPTION_STATUSES.has('active'), false);
});
