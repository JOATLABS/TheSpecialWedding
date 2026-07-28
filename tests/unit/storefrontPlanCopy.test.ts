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
  it('does not advertise storefront or custom-domain claims on any live tier', () => {
    // 2026-07-28 catalog: storefront/custom-domain shipped with the retired
    // Signature tier; no live plan sells them. If a tier regains these
    // entitlements, gate the copy to that tier only.
    for (const plan of ['plan_boutique', 'plan_solo_standard']) {
      const source = planFallbackSource(plan);
      assert.doesNotMatch(source, /Planner storefront/);
      assert.doesNotMatch(source, /custom domain/i);
    }
  });

  it('does not server-render retired tiers or yearly pricing', () => {
    assert.doesNotMatch(homePageSource, /plan_solo"|plan_signature|plan_enterprise/);
    assert.doesNotMatch(homePageSource, /"\$0"/);
    assert.doesNotMatch(homePageSource, /\/year|\/yr/);
  });
});
