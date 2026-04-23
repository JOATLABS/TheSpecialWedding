import assert from 'node:assert/strict';
import test from 'node:test';

import {
  ACTIVE_SUBSCRIPTION_STATUSES,
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

// ---------------------------------------------------------------------------
// D4 canceled-state coverage
//
// Pairs with Scenario D4 in
// testbed/verify_planner_active_lifecycle.py (phase_subscription_canceled)
// and the open question Q3 in
// docs/plans/SUBSCRIPTION_LIFECYCLE_TEST_PLAN.md §6:
//   "On canceled status after period end (D4), does the PR1
//   isAllowedForExpired guard catch canceled the same way as expired,
//   or is there a separate gate?"
//
// This module can't answer Q3 on its own — that lives in the route-guard
// layer — but it CAN pin the frontend billing-entry contract so a silent
// regression there (e.g. someone dropping "cancelled" from
// FRESH_CHECKOUT_SUBSCRIPTION_STATUSES) fails in milliseconds.
// ---------------------------------------------------------------------------

test('D4 — Stripe "canceled" normalizes to "cancelled" (British spelling is canonical)', () => {
  // The server-side enum uses the British spelling (see
  // app/services/subscription_service.py:458 — users.subscription_status
  // = "cancelled"). Stripe's API uses American. The normalizer bridges
  // them; losing this mapping would split the frontend routing tables.
  assert.equal(normalizeSubscriptionStatus('canceled'), 'cancelled');
  assert.equal(normalizeSubscriptionStatus('CANCELED'), 'cancelled');
  assert.equal(normalizeSubscriptionStatus('  canceled  '), 'cancelled');
  // Already-normalized form passes through untouched.
  assert.equal(normalizeSubscriptionStatus('cancelled'), 'cancelled');
});

test('D4 — cancelled is blocked, not active, not portal-recovery', () => {
  // If "cancelled" ever leaked into ACTIVE_SUBSCRIPTION_STATUSES, a
  // post-period-end planner would keep seeing dashboard content backed
  // by a dead subscription. Pin the membership explicitly.
  assert.equal(ACTIVE_SUBSCRIPTION_STATUSES.has('cancelled'), false);
  assert.equal(BLOCKED_SUBSCRIPTION_STATUSES.has('cancelled'), true);

  // D4 deliberately routes to fresh checkout, not the billing portal —
  // the customer's subscription is gone, there's nothing for the portal
  // to "recover". past_due/suspended go to portal; cancelled does not.
  assert.equal(BILLING_PORTAL_RECOVERY_SUBSCRIPTION_STATUSES.has('cancelled'), false);
  assert.equal(FRESH_CHECKOUT_SUBSCRIPTION_STATUSES.has('cancelled'), true);
});

test('D4 — isBlockedSubscriptionStatus returns true for both Stripe and canonical spellings', () => {
  // Blocked-check is called from middleware and guards that may receive
  // either the raw Stripe value or the already-normalized one. Both
  // must report blocked or login post-cancel silently succeeds.
  assert.equal(isBlockedSubscriptionStatus('canceled'), true);
  assert.equal(isBlockedSubscriptionStatus('cancelled'), true);
});

test('D4 — getPlannerBillingEntryState routes canceled planners to new_checkout', () => {
  // The common post-D4 shape: the Mongo subscription row is still
  // present (hasSubscription=true) with status=cancelled, but there's
  // no active plan to render. Must land on new_checkout so the
  // planner can re-subscribe (D5).
  assert.equal(
    getPlannerBillingEntryState({
      status: 'canceled',
      hasSubscription: true,
      hasPlan: false,
    }),
    'new_checkout',
  );

  // Same for the already-normalized form.
  assert.equal(
    getPlannerBillingEntryState({
      status: 'cancelled',
      hasSubscription: true,
      hasPlan: false,
    }),
    'new_checkout',
  );

  // Edge case: hasPlan=true on a cancelled subscription is a stale-plan
  // data shape (plan_snapshot still populated). Still routes to new
  // checkout — FRESH_CHECKOUT membership wins over hasPlan here.
  assert.equal(
    getPlannerBillingEntryState({
      status: 'cancelled',
      hasSubscription: true,
      hasPlan: true,
    }),
    'new_checkout',
  );
});

test('D3 vs D4 — cancel_at_period_end keeps dashboard until the boundary', () => {
  // D3 asserts cancel_at_period_end=True with status still "active".
  // The planner must retain dashboard access during this window; only
  // D4's post-period-end flip should change routing.
  assert.equal(
    getPlannerBillingEntryState({
      status: 'active',
      hasSubscription: true,
      hasPlan: true,
    }),
    'dashboard',
  );

  // Boundary moment — status flips cancelled, routing flips with it.
  assert.equal(
    getPlannerBillingEntryState({
      status: 'cancelled',
      hasSubscription: true,
      hasPlan: true,
    }),
    'new_checkout',
  );
});

test('D4 vs A6 — canceled and expired route identically from this module', () => {
  // Q3 in the plan asks whether canceled and expired converge. From
  // subscriptionStatus.ts' perspective they do — both are in
  // FRESH_CHECKOUT_SUBSCRIPTION_STATUSES and neither is in
  // BILLING_PORTAL_RECOVERY. Any divergence (isAllowedForExpired gate,
  // 402 vs redirect, etc.) must live outside this module.
  const base = { hasSubscription: true, hasPlan: false } as const;
  assert.equal(
    getPlannerBillingEntryState({ ...base, status: 'cancelled' }),
    getPlannerBillingEntryState({ ...base, status: 'expired' }),
  );
});

test('D4 vs D6 — cancelled is NOT portal_recovery even though past_due is', () => {
  // Regression guard. If someone ever "simplifies" by merging cancelled
  // into BILLING_PORTAL_RECOVERY, a cancelled customer would be bounced
  // into the Stripe billing portal for a subscription that no longer
  // exists. That's a dead-end UX and the PR would be wrong.
  assert.equal(
    getPlannerBillingEntryState({
      status: 'cancelled',
      hasSubscription: true,
      hasPlan: true,
    }),
    'new_checkout',
  );
  assert.equal(
    getPlannerBillingEntryState({
      status: 'past_due',
      hasSubscription: true,
      hasPlan: true,
    }),
    'portal_recovery',
  );
});

test('D5 — resubscribe flips routing back to dashboard', () => {
  // After D5 the subscription transitions cancelled → active with a new
  // plan_snapshot. The module must route to dashboard immediately; if
  // it didn't, the planner would be stuck on a checkout page they just
  // completed.
  assert.equal(
    getPlannerBillingEntryState({
      status: 'active',
      hasSubscription: true,
      hasPlan: true,
    }),
    'dashboard',
  );
});
