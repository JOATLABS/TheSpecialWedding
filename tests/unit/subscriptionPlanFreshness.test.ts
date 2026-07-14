import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

const PLAN_CONSUMERS = [
  'app/components/landing-page/PricingSignupSection.client.tsx',
  'app/components/saas/SignupModal.tsx',
  'app/components/saas/PricingSection.tsx',
  'app/components/saas/SaasLandingPage.tsx',
  'app/admin/planner/billing/page.tsx',
] as const;

describe('mutable subscription-plan browser freshness', () => {
  it('bypasses pre-fix browser cache entries on every shipped plan consumer', () => {
    for (const relativePath of PLAN_CONSUMERS) {
      const source = readFileSync(relativePath, 'utf8');
      assert.match(
        source,
        /public\/subscription-plans[\s\S]{0,180}cache:\s*["']no-store["']/,
        `${relativePath} must request the mutable public catalog with cache: 'no-store'`,
      );
    }
  });
});
