import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

const homePageSource = readFileSync('app/page.tsx', 'utf8');

function planFallbackSource(planId: string): string {
  const start = homePageSource.indexOf(`id: "${planId}"`);
  assert.notEqual(start, -1, `missing fallback pricing plan ${planId}`);

  const nextPlan = homePageSource.indexOf('\n  {', start + 1);
  return homePageSource.slice(start, nextPlan === -1 ? undefined : nextPlan);
}

describe('server-rendered storefront plan copy', () => {
  it('qualifies storefront and custom-domain claims to eligible tiers', () => {
    for (const eligiblePlan of ['plan_signature']) {
      const source = planFallbackSource(eligiblePlan);
      assert.match(source, /Planner storefront on a shareable platform URL/);
      assert.match(source, /Optional custom domain/);
    }

    for (const ineligiblePlan of ['plan_boutique', 'plan_solo_standard']) {
      const source = planFallbackSource(ineligiblePlan);
      assert.doesNotMatch(source, /Planner storefront/);
      assert.doesNotMatch(source, /custom domain/i);
    }
  });

  it('does not server-render a retired free tier', () => {
    assert.doesNotMatch(homePageSource, /plan_solo"|plan_enterprise/);
    assert.doesNotMatch(homePageSource, /"\$0"/);
  });
});
