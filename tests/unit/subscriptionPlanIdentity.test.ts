import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import {
  normalizeOwnedPlanForBilling,
} from '@/utils/subscriptionPlanIdentity';

test('owner-scoped billing response preserves saved commercial terms', () => {
  const retained = normalizeOwnedPlanForBilling(
    { id: 'legacy_solo', name: 'Solo (grandfathered)', price_monthly: 19 },
    'legacy_solo',
  );
  assert.equal(retained?._id, 'legacy_solo');
  assert.equal(retained?.price_monthly, 19);
});

test('owner-plan normalization rejects a mismatched response identity', () => {
  assert.equal(
    normalizeOwnedPlanForBilling(
      { id: 'different_plan', name: 'Wrong plan' },
      'legacy_solo',
    ),
    null,
  );
});

test('planner billing resolves identity in Stripe, legacy, and profile fallbacks', () => {
  const source = readFileSync('app/admin/planner/billing/page.tsx', 'utf8');
  const resolverCalls = source.match(/await resolvePlanDetail\(/g) ?? [];

  assert.equal(resolverCalls.length, 3);
  assert.match(
    source,
    /admin\/users\/\$\{encodeURIComponent\(billingUserId\)\}\/subscription-plan/,
  );
  assert.doesNotMatch(
    source,
    /public\/subscription-plans\/\$\{encodeURIComponent\(subscription\.plan_id\)\}/,
  );
  assert.doesNotMatch(source, /findSubscriptionBillingPlan/);
  assert.match(
    source,
    /ACTIVE_SUBSCRIPTION_STATUSES\.has\(normalizedProfileStatus\)/,
  );
  assert.doesNotMatch(source, /\['active', 'trial'\]\.includes/);
});
