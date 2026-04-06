import assert from 'node:assert/strict';
import test from 'node:test';

import {
  BILLING_PORTAL_RECOVERY_SUBSCRIPTION_STATUSES,
  BLOCKED_SUBSCRIPTION_STATUSES,
  FRESH_CHECKOUT_SUBSCRIPTION_STATUSES,
  getPlannerBillingEntryState,
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

test('status buckets separate fresh checkout from billing-portal recovery', () => {
  assert.equal(FRESH_CHECKOUT_SUBSCRIPTION_STATUSES.has('pending_checkout'), true);
  assert.equal(FRESH_CHECKOUT_SUBSCRIPTION_STATUSES.has('expired'), true);
  assert.equal(FRESH_CHECKOUT_SUBSCRIPTION_STATUSES.has('past_due'), false);
  assert.equal(BILLING_PORTAL_RECOVERY_SUBSCRIPTION_STATUSES.has('past_due'), true);
  assert.equal(BILLING_PORTAL_RECOVERY_SUBSCRIPTION_STATUSES.has('suspended'), true);
});

test('planner billing entry state preserves portal recovery when plan lookup fails', () => {
  assert.equal(
    getPlannerBillingEntryState({
      status: 'past_due',
      hasSubscription: true,
      hasPlan: false,
    }),
    'portal_recovery',
  );

  assert.equal(
    getPlannerBillingEntryState({
      status: 'pending_checkout',
      hasSubscription: true,
      hasPlan: false,
    }),
    'new_checkout',
  );

  assert.equal(
    getPlannerBillingEntryState({
      status: 'active',
      hasSubscription: true,
      hasPlan: false,
    }),
    'dashboard',
  );

  assert.equal(
    getPlannerBillingEntryState({
      status: 'trial',
      hasSubscription: true,
      hasPlan: false,
    }),
    'dashboard',
  );

  assert.equal(
    getPlannerBillingEntryState({
      status: 'active',
      hasSubscription: true,
      hasPlan: true,
    }),
    'dashboard',
  );
});
