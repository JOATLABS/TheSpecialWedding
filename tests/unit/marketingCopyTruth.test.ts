import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, it } from 'node:test';

import { MARKETING_FEATURES } from '../../app/data/marketingFeatures';
import { PHASE_ONE_PRODUCT_STORIES } from '../../app/data/phaseOneProductProof';

const ROOT = process.cwd();

function source(relativePath: string): string {
  return readFileSync(path.join(ROOT, relativePath), 'utf8');
}

const SAFE_VENDOR_PLAN_COPY = 'Planner-owned vendor CRM, contracts & milestones';

const PRICING_COPY_SOURCES = [
  'app/page.tsx',
  'app/components/saas/SignupModal.tsx',
  'app/api/subscription_management.py',
  'scripts/seed_subscription_plans.py',
] as const;

const APPROVED_STORY_COPY = [
  {
    id: 'connection',
    pillar: 'Connection Over Tools',
    headline: 'One wedding plan, presented clearly across each audience.',
    description:
      'Start with the planner-owned event plan, then compare the matching venue and time in the public microsite and couple timeline. Planner controls remain private.',
    proof: 'Planner event record → public schedule → couple timeline',
    supportingLabels: ['Couple view', 'Guest view'],
  },
  {
    id: 'disorganization-tax',
    pillar: 'Disorganization Tax',
    headline: 'Start the morning with the weddings that need attention.',
    description:
      'Morning View compares active weddings using RSVP movement, recent activity, pending forms, and setup progress, then points the planner to the next wedding action.',
    proof: 'Two active weddings · RSVP, activity, forms, and setup signals',
    supportingLabels: ['Planner inbox', 'Wedding budget'],
  },
  {
    id: 'couple-boundaries',
    pillar: 'Couple Experience + Boundaries',
    headline: 'Give couples a clear view without exposing planner operations.',
    description:
      'The couple portal brings the wedding overview, shared timeline, payment context, and assigned forms into one guided experience. Planner-only controls remain private.',
    proof: 'One guided portal, planner-owned boundaries',
    supportingLabels: ['Planner-controlled intake', 'Shared couple experience'],
  },
  {
    id: 'built-for-planners',
    pillar: 'Built for Planners',
    headline: 'Review guest context and a venue-aware seating plan in wedding-specific workspaces.',
    description:
      'Guest Management shows response, group, meal, and plus-one context. Seating shows the room outline, fixtures, tables, assignments, and layout checks. Planner Vendor Management keeps private contacts, contracts, and payment status in its own operational view.',
    proof: 'Guest context · seating plan · planner vendor records',
    supportingLabels: ['Guest records', 'Planner vendor records'],
  },
] as const;

const APPROVED_FEATURE_COPY = {
  dashboard: {
    title: 'The Morning View',
    tagline:
      'Compare active weddings by RSVP movement, recent activity, pending forms, and setup progress.',
    description:
      'Morning View gives planners a portfolio scan of populated status, progress, and next-action context. Open the wedding record when setup needs attention.',
  },
  'real-time': {
    title: 'Wedding Timeline & Event Days',
    tagline:
      'Present rehearsal, ceremony, reception, brunch, and cultural-event details across planner, couple, and public views.',
    description:
      'Configure each event day with its date, venue, time, attire, and order of events. The planner record, couple timeline, and public schedule present the prepared details for their respective audiences.',
  },
  'couple-portal': {
    title: 'A Guided Couple Portal',
    tagline:
      'Share the schedule, payment context, forms, and next steps couples need while planner-only work stays private.',
    description:
      'Couples get a guided dashboard for their wedding overview, timeline, payment context, and assigned forms. Planner-only controls and internal operations remain outside the couple view.',
  },
  'wedding-website': {
    title: 'Planner Record → Public Microsite',
    tagline:
      'Present the wedding story, schedule, and approved gallery in a polished guest-facing view without planner controls.',
    description:
      'Prepare the story, branding, event details, and gallery in the planner wedding record. The public microsite presents those approved details for guests while private planning work stays out of view.',
  },
  'guest-management': {
    title: 'Guest Management',
    tagline:
      'Review invitation, RSVP, group, meal, and plus-one context from one planner page.',
    description:
      'Guest Management combines populated totals with filterable table and card views, so planners can inspect response and guest context without rebuilding a spreadsheet.',
  },
} as const;

describe('public marketing copy truth contract', () => {
  it('pins the approved planner-first hero and Phase 1 story copy', () => {
    assert.ok(
      source('app/page.tsx').includes(
        'Manage the wedding record, public details, couple timeline, and guest-response context from one planner-owned workspace—while planner-only operations stay private.',
      ),
    );
    assert.ok(
      source('app/features/page.tsx').includes(
        'Protect planner time, give couples a calmer experience, and present one coherent wedding plan across planner, couple, public, and guest-response views.',
      ),
    );

    assert.deepEqual(
      PHASE_ONE_PRODUCT_STORIES.map((story) => ({
        id: story.id,
        pillar: story.pillar,
        headline: story.headline,
        description: story.description,
        proof: story.proof,
        supportingLabels: story.supportingImages.map(({ label }) => label),
      })),
      APPROVED_STORY_COPY,
    );

    const vendorProof = PHASE_ONE_PRODUCT_STORIES.find((story) => story.id === 'built-for-planners');
    assert.ok(vendorProof);
    assert.equal(
      vendorProof.supportingImages[1]?.imageAlt,
      'Planner Vendor Management showing private contacts, contracts, and payment status',
    );
  });

  it('pins conversion-card copy to claims demonstrated by the walkthrough contracts', () => {
    const actualFeatureCopy = Object.fromEntries(
      Object.keys(APPROVED_FEATURE_COPY).map((featureId) => {
        const feature = MARKETING_FEATURES.find((candidate) => candidate.id === featureId);
        assert.ok(feature, `missing marketing feature: ${featureId}`);
        return [
          featureId,
          {
            title: feature.title,
            tagline: feature.tagline,
            description: feature.description,
          },
        ];
      }),
    );

    assert.deepEqual(actualFeatureCopy, APPROVED_FEATURE_COPY);

    const humanFacingCopy = [
      ...MARKETING_FEATURES.flatMap((feature) => [feature.title, feature.tagline, feature.description]),
      ...PHASE_ONE_PRODUCT_STORIES.flatMap((story) => [
        story.headline,
        story.description,
        story.proof,
        ...story.supportingImages.flatMap(({ label, imageAlt }) => [label, imageAlt]),
      ]),
    ].join(' ');

    assert.doesNotMatch(
      humanFacingCopy,
      /auto[- ]?publish|never out of date|every surface stays aligned|the couple sees what you see|what changed overnight|vendor[- ]collaboration workspaces?|vendor portal|vendor delivery|can never drift|every surface writes/i,
    );
  });

  it('keeps every public pricing source free of unfinished vendor-access promises', () => {
    for (const relativePath of PRICING_COPY_SOURCES) {
      const pricingSource = source(relativePath);
      assert.ok(
        pricingSource.includes(SAFE_VENDOR_PLAN_COPY),
        `${relativePath} must use the approved planner-owned vendor feature copy`,
      );
      assert.doesNotMatch(
        pricingSource,
        /vendor[- ]collaboration workspaces?|vendor portal/i,
        `${relativePath} must not promise unfinished vendor access`,
      );
    }

    for (const relativePath of [
      'app/api/subscription_management.py',
      'scripts/seed_subscription_plans.py',
    ]) {
      assert.doesNotMatch(
        source(relativePath),
        /["']vendor_collaboration["']\s*:\s*True/,
        `${relativePath} must keep the unfinished vendor-collaboration entitlement disabled`,
      );
    }

    assert.ok(
      source('scripts/seed_subscription_plans.py').includes(
        'SEED_VERSION = "2026-07-14T00:00:00+00:00"',
      ),
      'the pricing truth refresh must advance the seed strategy version so existing plan records are updated',
    );
  });
});
