import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

// Contract for the couples' one-time tier display (2026-07-28 catalog:
// Couple Plan — One Wedding, $199 one-time, COUPLE_LIFETIME_OFFER in
// app/constants/billing.py; workspace closes 90 days post-wedding — NOT
// lifetime access). The couple offer is NOT a subscription plan:
// it must render as a peer card inside the homepage pricing grid while
// staying out of the planner signup/checkout flow.

const source = (path: string) => readFileSync(path, 'utf8');

const homePage = source('app/page.tsx');
const coupleSection = source('app/components/landing-page/CouplePlanSection.tsx');
const rootLayout = source('app/layout.tsx');
const billingConstants = source('app/constants/billing.py');

describe('couple one-time plan display contract', () => {
  it('keeps the catalog constant at $199 one-time', () => {
    assert.match(billingConstants, /"amount_usd": 199/);
    assert.match(billingConstants, /"billing": "one_time"/);
  });

  it('renders the couple card through the homepage pricing grid', () => {
    assert.match(homePage, /<PricingSignupSection pricing=\{fallbackPricing\} theme=\{defaultTheme\} \/>/);
    const pricingSection = source('app/components/landing-page/PricingSignupSection.client.tsx');
    assert.match(pricingSection, /import \{ CouplePlanCard \} from "\.\/CouplePlanSection"/);
    assert.match(pricingSection, /<CouplePlanCard \/>/);

    // Planner-first: the planner pricing section must render before the
    // couples' card inside PricingSignupSection.
    const plannerPricingIndex = pricingSection.indexOf('{displayPricing.map');
    const coupleIndex = pricingSection.indexOf('<CouplePlanCard');
    assert.notEqual(plannerPricingIndex, -1);
    assert.notEqual(coupleIndex, -1);
    assert.ok(
      plannerPricingIndex < coupleIndex,
      'planner tiers must render before the couples card',
    );
  });

  it('pins the couple card to the locked price and one-time framing', () => {
    assert.match(coupleSection, /For couples/);
    assert.match(coupleSection, /\$199/);
    assert.match(coupleSection, /one-time/);
    assert.match(coupleSection, /through 90 days after your wedding/i);
    assert.match(coupleSection, /Nothing renews\./);
    // Emmanuel 2026-07-28: there is NO lifetime access — the workspace is
    // removed 90 days after the wedding ends. No user-facing lifetime claims
    // (the code-internal constant COUPLE_LIFETIME_OFFER is exempt).
    assert.doesNotMatch(coupleSection, /lifetime (access|of the wedding)/i);
    assert.doesNotMatch(coupleSection, /Lifetime of the wedding/);
    // Grounded in the locked scheme — one wedding, whole planning window.
    assert.match(coupleSection, /One live wedding workspace/);
    assert.match(coupleSection, /Full planning tools/);
    assert.match(coupleSection, /RSVP tracking/);
    assert.match(coupleSection, /wedding website/);
    assert.match(coupleSection, /galleries/i);
    assert.match(coupleSection, /Export your wedding data/);
  });

  it('reads the checkout URL from env with a real contact fallback', () => {
    assert.match(coupleSection, /process\.env\.NEXT_PUBLIC_COUPLE_CHECKOUT_URL/);
    // Graceful fallback when the Payment Link is not configured — never a
    // fabricated checkout URL.
    assert.match(coupleSection, /mailto:hello@thespecialwedding\.io/);
    assert.doesNotMatch(coupleSection, /https:\/\/buy\.stripe\.com/);
    assert.doesNotMatch(coupleSection, /price_1[A-Za-z0-9]/);
  });

  it('keeps the couple offer out of the planner signup flow and plan fallbacks', () => {
    const signupModal = source('app/components/saas/SignupModal.tsx');
    assert.doesNotMatch(signupModal, /Couple Lifetime|offer_couple_lifetime|\$199/);

    // The couple offer is not a Mongo plan; the homepage planner fallback
    // catalog must not grow a fake couple plan entry.
    assert.doesNotMatch(homePage, /offer_couple_lifetime/);
  });

  it('advertises the $199 one-time offer in the public JSON-LD catalog', () => {
    assert.match(rootLayout, /name: 'Couple Plan — One Wedding'/);
    assert.doesNotMatch(rootLayout, /lifetime of the wedding/i);
    assert.match(rootLayout, /price: '199'/);
    assert.match(rootLayout, /highPrice: '199'/);
    assert.match(rootLayout, /offerCount: 3/);
  });

  it('answers couple pricing in the homepage FAQ and resources FAQ', () => {
    assert.match(homePage, /one-time \$199 fee/);
    assert.match(homePage, /90 days after your wedding day/);
    const resourcesFaq = source('app/resources/resourcesShared.ts');
    assert.match(resourcesFaq, /one-time \$199 fee/);
    assert.match(resourcesFaq, /90 days after your wedding/i);
    assert.doesNotMatch(resourcesFaq, /lifetime of your wedding/i);
  });

  it('documents both couple env keys in .env.example', () => {
    const envExample = source('.env.example');
    assert.match(envExample, /STRIPE_COUPLE_LIFETIME_PRICE_ID=/);
    assert.match(envExample, /NEXT_PUBLIC_COUPLE_CHECKOUT_URL=/);
  });
});
