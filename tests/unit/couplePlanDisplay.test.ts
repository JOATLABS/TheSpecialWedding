import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { after, afterEach, before, describe, it } from 'node:test';
import { cleanup, render } from '@testing-library/react';
import React from 'react';
import { installDom } from './testDom';

// Contract for the couples' one-time tier display (2026-07-28 catalog:
// Couple Plan — One Wedding, $199 one-time, COUPLE_LIFETIME_OFFER in
// app/constants/billing.py; workspace closes 90 days post-wedding — NOT
// lifetime access). The couple offer is NOT a subscription plan:
// it must render as a compact card after the planner tiers in the shared
// pricing grid and must never enter the planner signup/checkout flow.

const source = (path: string) => readFileSync(path, 'utf8');

const homePage = source('app/page.tsx');
const pricingSection = source('app/components/landing-page/PricingSignupSection.client.tsx');
const coupleCard = source('app/components/landing-page/CouplePlanSection.tsx');
const rootLayout = source('app/layout.tsx');
const billingConstants = source('app/constants/billing.py');

let PricingSignupSection: typeof import('../../app/components/landing-page/PricingSignupSection.client').PricingSignupSection;
let domHandle: ReturnType<typeof installDom> | null = null;
const originalFetch = globalThis.fetch;

before(async () => {
  domHandle = installDom();
  globalThis.fetch = (async () =>
    new Response('[]', {
      status: 200,
      headers: { 'content-type': 'application/json' },
    })) as typeof fetch;
  ({ PricingSignupSection } = await import(
    '../../app/components/landing-page/PricingSignupSection.client'
  ));
});

afterEach(() => cleanup());

after(() => {
  globalThis.fetch = originalFetch;
  domHandle?.cleanup();
  domHandle = null;
});

describe('couple one-time plan display contract', () => {
  it('keeps the catalog constant at $199 one-time', () => {
    assert.match(billingConstants, /"amount_usd": 199/);
    assert.match(billingConstants, /"billing": "one_time"/);
  });

  it('renders the couple card after the planner tiers in the homepage pricing grid', () => {
    assert.match(homePage, /<PricingSignupSection/);
    assert.match(pricingSection, /<CouplePlanCard \/>/);

    // Planner-first: planner tiers render before the couple card, but every
    // offer stays in the same aligned grid instead of splitting the couple
    // offer into a standalone homepage section.
    const plannerTiersIndex = pricingSection.indexOf('displayPricing.map');
    const coupleIndex = pricingSection.indexOf('<CouplePlanCard');
    assert.notEqual(plannerTiersIndex, -1);
    assert.notEqual(coupleIndex, -1);
    assert.ok(
      plannerTiersIndex < coupleIndex,
      'planner tiers must render before the couple card',
    );
    assert.doesNotMatch(homePage, /<CouplePlan(?:Card|Section)\b/);
    assert.doesNotMatch(pricingSection, /lg:min-h-\[36rem\]/);
    assert.doesNotMatch(coupleCard, /lg:min-h-\[36rem\]/);
  });

  it('renders Couple Plan as the third peer beside the two planner tiers', () => {
    const pricing = [
      {
        id: 'plan_boutique',
        name: 'Solo Founding',
        price: '$49',
        period: '/month',
        features: ['Unlimited weddings'],
        cta: 'Choose Solo Founding',
        popular: true,
      },
      {
        id: 'plan_solo_standard',
        name: 'Solo Standard',
        price: '$99',
        period: '/month',
        features: ['Unlimited weddings'],
        cta: 'Choose Solo Standard',
      },
    ];
    const theme = {
      primary_color: '#D4A5A5',
      secondary_color: '#E8C46A',
      accent_color: '#FFE4D6',
      background_style: 'gradient' as const,
      font_style: 'elegant' as const,
    };

    const view = render(React.createElement(PricingSignupSection, { pricing, theme }));
    const grid = view.container.querySelector<HTMLElement>('#pricing .grid.items-stretch');
    assert.ok(grid);
    assert.match(grid.className, /\blg:grid-cols-3\b/);

    const cards = Array.from(grid.children);
    assert.equal(cards.length, 3);
    assert.ok(cards.every((card) => card.tagName === 'ARTICLE'));
    assert.deepEqual(
      cards.map((card) => card.querySelector('h3')?.textContent),
      ['Solo Founding', 'Solo Standard', 'Couple Plan'],
    );
    assert.ok(cards.every((card) => !card.className.includes('lg:min-h-[36rem]')));
  });

  it('pins the couple card to the locked price and one-time framing', () => {
    assert.match(coupleCard, /For couples/);
    assert.match(coupleCard, /\$199/);
    assert.match(coupleCard, /one-time/);
    assert.match(coupleCard, /Active through 90 days after your wedding/);
    assert.match(coupleCard, /One wedding workspace\. One payment\. No subscription or renewal\./);
    // Emmanuel 2026-07-28: there is NO lifetime access — the workspace is
    // removed 90 days after the wedding ends. No user-facing lifetime claims
    // (the code-internal constant COUPLE_LIFETIME_OFFER is exempt).
    assert.doesNotMatch(coupleCard, /lifetime (access|of the wedding)/i);
    assert.doesNotMatch(coupleCard, /Lifetime of the wedding/);
    // Grounded in the locked scheme — one wedding, whole planning window.
    assert.match(coupleCard, /Planning tools, guests & RSVPs/);
    assert.match(coupleCard, /Wedding website/);
    assert.match(coupleCard, /galleries/i);
    assert.match(coupleCard, /Export your wedding data/);

    const featureBlock = coupleCard.match(/const COUPLE_FEATURES = \[([\s\S]*?)\];/)?.[1];
    assert.ok(featureBlock, 'couple feature list must remain explicit');
    assert.equal(featureBlock.match(/"[^"]+"/g)?.length, 4, 'couple card must stay compact');
  });

  it('reads the checkout URL from env with a real contact fallback', () => {
    assert.match(coupleCard, /process\.env\.NEXT_PUBLIC_COUPLE_CHECKOUT_URL/);
    // Graceful fallback when the Payment Link is not configured — never a
    // fabricated checkout URL.
    assert.match(coupleCard, /mailto:hello@thespecialwedding\.io/);
    assert.doesNotMatch(coupleCard, /https:\/\/buy\.stripe\.com/);
    assert.doesNotMatch(coupleCard, /price_1[A-Za-z0-9]/);
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
