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

const PRICING_COPY_SOURCES = [
  'app/page.tsx',
  'app/components/saas/SignupModal.tsx',
  'app/api/subscription_management.py',
  'scripts/seed_subscription_plans.py',
] as const;

const PUBLIC_COPY_TRUTH_SOURCES = [
  ...PRICING_COPY_SOURCES,
  'public/llms.txt',
  'app/resources/resourcesShared.ts',
  'app/scripts/seed_knowledge_base.py',
  'app/resources/blog/data.tsx',
  'app/scripts/seed_blog.py',
  'app/api/saas_config.py',
  'app/components/saas/SaasLandingPage.tsx',
  'app/components/saas/PlannerAuthModal.tsx',
  'app/services/user_management_service.py',
] as const;

const RETIRED_VENDOR_ACCESS_PROMISES =
  /vendor[- ]collaboration workspaces?|invite photographers, caterers, and venues into dedicated workspaces|invite vendors to collaborative timelines|invite and collaborate with vendors|give vendors access to update|vendors access only their assigned tasks|vendor updates scoped to their deliverables|vendor collaboration features are game-changing|vendor collaboration hub|vendor invites|token-based vendor workspaces|all three paths a vendor can take|vendors can be invited into dedicated workspaces|Planner-owned vendor CRM, contracts & milestones|dedicated vendor portal|vendor portal access|every florist, caterer, and photographer has|role-based access to the timeline|uploads deliverables to the gallery|signs off on contracts inside the platform|publish schedules for planners, vendors, and couples/i;

const UNIMPLEMENTED_SIGNATURE_PROMISES =
  /cross-wedding analytics(?: &| and)? revenue tracking|agency-grade reporting/i;

const RETIRED_AUTOMATION_PROMISES =
  /no copy-paste, no drift|no manual data sync|caterer rollup updates automatically|guest-facing schedule and the planner's timeline stay in sync|server-sent events push changes|couple portal updates live\. no refresh|inbound emails auto-thread|audit log captures every write|every write is captured|real-time updates visible across your team and to the couple|everything syncs in seconds|the couple configures colors, fonts, background style, and event-type copy/i;

const RETIRED_SUPPORT_PROMISES =
  /live chat with our success team|on-call escalation for critical day-of moments|Signature and Agency plans|support infrastructure that exists when you need it at 11pm|support desk that actually responds/i;

const RETIRED_PLAN_HIGHLIGHTS =
  /Up to 50 guests|AI-powered timeline & vendor matching|QR check-in & live counts|\b(?:1|25|100|500)GB storage\b|Group onboarding session|White-label \(your brand, no Special Wedding mentions\)|API access \+ webhooks|Dedicated success manager|Custom integrations/i;

// 2026-07-28 pricing (final): two paid tiers (Solo Founding $49/mo / Solo
// Standard $99/mo), yearly = monthly × 10; the free tier, Signature, and
// Enterprise are retired. White-Glove is a one-time setup add-on, not a tier.
const APPROVED_PLAN_HIGHLIGHTS = [
  'Unlimited weddings',
  'Unlimited guests',
  'Vendor management',
  'Seating orchestration',
  'Automated reminders',
  'Calendar sync (Google, Outlook)',
  '300 AI credits/month',
  '25GB guest memories storage',
  'Email support',
  'Everything in Solo Founding',
  '750 AI credits/month',
  '50GB guest memories storage',
] as const;

const APPROVED_STORY_COPY = [
  {
    id: 'connection',
    pillar: 'Connection Over Tools',
    headline: 'One wedding plan, presented clearly across each audience.',
    description:
      'Start with the planner-owned event plan, then follow the same wedding into the public guest view and the couple’s guided workspace. Each audience sees the context it needs while planner controls remain private.',
    proof: 'Planner event plan → public guest view → guided couple workspace',
    supportingLabels: ['Public guest view', 'Couple workspace'],
  },
  {
    id: 'disorganization-tax',
    pillar: 'Disorganization Tax',
    headline: 'Stop paying the disorganization tax every morning.',
    description:
      'Morning View compares RSVP movement, recent activity, pending forms, and setup progress across active weddings, so the planner can act without rebuilding context across inboxes, sheets, and point tools.',
    proof: 'Two active weddings · one prioritized operating view',
    supportingLabels: ['Planner inbox', 'Wedding budget'],
  },
  {
    id: 'couple-boundaries',
    pillar: 'Couple Experience + Boundaries',
    headline: 'Give couples a clear view without exposing planner operations.',
    description:
      'The couple dashboard gives Sofia and Daniel a focused wedding overview and RSVP progress. A separate planner workspace presents the Couple Intake Questionnaire, while the couple portal’s Guest Memories review queue shows status filters, keep/reject decisions, and individual downloads.',
    proof: 'Couple overview · planner intake · couple memories controls',
    supportingLabels: ['Planner-controlled intake', 'Couple Guest Memories'],
  },
  {
    id: 'built-for-planners',
    pillar: 'Built for Planners',
    headline: 'Run wedding-specific work generic project tools do not understand.',
    description:
      'Guest Management keeps RSVP, group, meal, and plus-one context together. Seating models the room outline, fixtures, tables, assignments, and layout checks. Planner Vendor Management keeps private contacts, contracts, and payment status in its own operational workspace.',
    proof: 'RSVP context · room layout · private vendor operations',
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
  'wedding-configuration': {
    title: 'Wedding Configuration',
    tagline:
      'Review event days, RSVP rules, privacy, registry, FAQs, theme, story, and public-wedding settings in one planner record.',
    description:
      'The Configure screen groups the planner-owned details behind the wedding experience: event days, venue, time, attire, RSVP and privacy rules, registry, FAQs, theme, and story. Public and couple views present the prepared details for their audiences while planner controls remain private.',
  },
  'gallery-management': {
    title: 'Gallery Management',
    tagline:
      'Review each wedding gallery and its approved media from the planner workspace.',
    description:
      'Select a wedding and review its populated gallery, image labels, folder category, and total count from one planner workspace. Uploading new media and reviewing Guest Memories remain separate, clearly labelled workflows.',
  },
  'guest-management': {
    title: 'Guest Management',
    tagline:
      'Review invitation, RSVP, group, meal, and plus-one context from one planner page.',
    description:
      'Guest Management combines populated totals with filterable table and card views, so planners can inspect response and guest context without rebuilding a spreadsheet.',
  },
  budget: {
    title: 'Budget Management',
    tagline:
      'See planned versus spent totals, remaining funds, category status, vendor-quote counts, and payment history in one wedding budget.',
    description:
      'Budget Management gives planners a populated view of total budget, actual spend, remaining funds, category progress, available quote counts, and payment history for the selected wedding. The same view presents AI Insights, PDF export, and Excel export controls.',
  },
  forms: {
    title: 'Forms Canvas',
    tagline:
      'Review a populated Couple Intake Questionnaire beside the field palette and visible Preview and Save Form controls.',
    description:
      'The Forms Canvas shows a populated Couple Intake Questionnaire alongside available text, email, phone, number, date, text-area, dropdown, radio, checkbox, rating, and scale fields. Builder, Preview, and Save Form controls appear together in the planner workspace.',
  },
  team: {
    title: 'Team Management',
    tagline:
      'Review team seats, member roles and status, assigned-wedding counts, and last activity from one studio view.',
    description:
      'The populated Team Management view keeps seat capacity and the visible roster together, including each member’s role, status, assigned-wedding count, and last active time.',
  },
} as const;

describe('public marketing copy truth contract', () => {
  it('pins the approved planner-first hero and Phase 1 story copy', () => {
    assert.ok(
      source('app/page.tsx').includes(
        'Planner, couple, and guests — one connected record, with your operations kept private.',
      ),
    );
    assert.ok(
      source('app/features/page.tsx').includes(
        'The complete planner operating system — seventeen connected surfaces spanning weddings, guests, seating, vendors, forms, and finances.',
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
      /auto[- ]?publish|never out of date|every surface stays aligned|the couple sees what you see|what changed overnight|vendor[- ]collaboration workspaces?|vendor portal|vendor delivery|can never drift|every surface writes|save once|guest-list-to-slug publishing|same media library feeds|read the same source/i,
    );
  });

  it('keeps the current Couple, Budget, Forms, and Team proof free of unseen outcomes', () => {
    const coupleBoundaries = PHASE_ONE_PRODUCT_STORIES.find(
      (story) => story.id === 'couple-boundaries',
    );
    assert.ok(coupleBoundaries);
    assert.deepEqual(
      [
        coupleBoundaries.image.featureId,
        ...coupleBoundaries.supportingImages.map(({ image }) => image.featureId),
      ],
      ['couple-portal', 'forms', 'guest-memories'],
    );
    assert.doesNotMatch(
      coupleBoundaries.description,
      /shared timeline|payment context|assigned forms/i,
    );
    assert.match(coupleBoundaries.description, /wedding overview and RSVP progress/i);
    assert.match(coupleBoundaries.description, /Guest Memories/i);
    assert.equal(
      coupleBoundaries.imageAlt,
      'Sofia and Daniel couple dashboard showing the wedding date and RSVP progress',
    );
    assert.equal(
      coupleBoundaries.supportingImages[1]?.imageAlt,
      'Sofia and Daniel Guest Memories review queue showing status filters, keep and reject decisions, and individual download controls',
    );

    const proofBoundFeatureCopy = Object.fromEntries(
      ['budget', 'forms', 'team'].map((featureId) => {
        const feature = MARKETING_FEATURES.find((candidate) => candidate.id === featureId);
        assert.ok(feature, `missing marketing feature: ${featureId}`);
        return [featureId, `${feature.title} ${feature.tagline} ${feature.description}`];
      }),
    );

    assert.doesNotMatch(proofBoundFeatureCopy.budget, /pressure-tests every|warn you before overruns/i);
    assert.doesNotMatch(proofBoundFeatureCopy.forms, /send wedding checklists|write back to the record/i);
    assert.doesNotMatch(proofBoundFeatureCopy.team, /trace every action|audit log/i);
  });

  it('keeps every public source free of unfinished vendor-access promises', () => {
    for (const relativePath of PUBLIC_COPY_TRUTH_SOURCES) {
      assert.doesNotMatch(
        source(relativePath),
        RETIRED_VENDOR_ACCESS_PROMISES,
        `${relativePath} must not promise unfinished vendor access`,
      );
      assert.doesNotMatch(
        source(relativePath),
        UNIMPLEMENTED_SIGNATURE_PROMISES,
        `${relativePath} must not promise analytics that are not plan-gated`,
      );
      assert.doesNotMatch(
        source(relativePath),
        RETIRED_AUTOMATION_PROMISES,
        `${relativePath} must not promise unverified automatic propagation`,
      );
      assert.doesNotMatch(
        source(relativePath),
        RETIRED_SUPPORT_PROMISES,
        `${relativePath} must match the actual paid-plan support contract`,
      );
    }

    for (const relativePath of PRICING_COPY_SOURCES) {
      const pricingSource = source(relativePath);
      for (const highlight of APPROVED_PLAN_HIGHLIGHTS) {
        assert.ok(pricingSource.includes(highlight), `${relativePath} must include ${highlight}`);
      }
      assert.doesNotMatch(
        pricingSource,
        RETIRED_PLAN_HIGHLIGHTS,
        `${relativePath} must not restore retired plan highlights`,
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
      source('app/utils/subscription_plan_seed_policy.py').includes(
        'PUBLIC_PLAN_COPY_SEED_VERSION = "2026-07-28T13:00:00+00:00"',
      ),
      'the 2026-07 pricing strategy refresh must advance the copy revision',
    );
  });
});
