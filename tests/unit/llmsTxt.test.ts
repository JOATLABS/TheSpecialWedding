import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

const llmsText = readFileSync('public/llms.txt', 'utf8');

describe('llms.txt public authority file', () => {
  it('uses the canonical public pricing tiers and template URL', () => {
    for (const expected of [
      '# The Special Wedding',
      '**Solo Founding**: $49/month',
      '**Solo Standard**: $99/month',
      '**White Glove**: $149/month',
      'a planner storefront on a shareable platform URL',
      'an optional custom domain',
      'https://thespecialwedding.io/resources/templates',
      'All plans include a 30-day free trial',
    ]) {
      assert.equal(
        llmsText.includes(expected),
        true,
        `public/llms.txt should include ${expected}`
      );
    }
  });

  it('does not reintroduce retired pricing or unsupported plan promises', () => {
    for (const retiredClaim of [
      'Starter',
      'Pro: $59',
      '**Solo**: Free',
      '**Boutique**',
      '**Signature**',
      '**Enterprise**',
      'QR check-in',
      'white-label',
      'API access',
      'dedicated support',
      'resources?tab=templates',
    ]) {
      assert.equal(
        llmsText.includes(retiredClaim),
        false,
        `public/llms.txt should not include retired claim: ${retiredClaim}`
      );
    }
  });

  it('uses current product and founder proof instead of unverified testimonial claims', () => {
    assert.match(llmsText, /Founder And Workflow Proof/);
    assert.match(llmsText, /current full-window product views/);
    assert.doesNotMatch(llmsText, /publishes planner testimonials/);
    assert.doesNotMatch(llmsText, /Phase 1/);
  });
});
