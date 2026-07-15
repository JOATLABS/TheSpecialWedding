import { getMarketingCaptureAsset, type MarketingCaptureAsset } from './marketingCaptureManifest';

export type PhaseOneProductStory = {
  id: 'connection' | 'disorganization-tax' | 'couple-boundaries' | 'built-for-planners';
  pillar: string;
  headline: string;
  description: string;
  proof: string;
  image: MarketingCaptureAsset;
  imageAlt: string;
  supportingImages: readonly {
    label: string;
    image: MarketingCaptureAsset;
    imageAlt: string;
  }[];
  featureIds: readonly string[];
};

export const PHASE_ONE_PRODUCT_STORIES = [
  {
    id: 'connection',
    pillar: 'Connection Over Tools',
    headline: 'One wedding plan, presented clearly across each audience.',
    description:
      'Start with the planner-owned event plan, then follow the same wedding into the public guest view and the couple’s guided workspace. Each audience sees the context it needs while planner controls remain private.',
    proof: 'Planner event plan → public guest view → guided couple workspace',
    image: getMarketingCaptureAsset('real-time', 'homepage'),
    imageAlt: 'Sofia and Daniel event plan showing The Glasshouse at Riverbend at 4:00 PM in the planner workspace',
    supportingImages: [
      {
        label: 'Public guest view',
        image: getMarketingCaptureAsset('wedding-website', 'homepage'),
        imageAlt: 'Sofia and Daniel public wedding website showing guest-facing details',
      },
      {
        label: 'Couple workspace',
        image: getMarketingCaptureAsset('couple-portal', 'homepage'),
        imageAlt: 'Sofia and Daniel couple portal reflecting their shared wedding plan',
      },
    ],
    featureIds: ['real-time', 'couple-portal', 'wedding-website'],
  },
  {
    id: 'disorganization-tax',
    pillar: 'Disorganization Tax',
    headline: 'Stop paying the disorganization tax every morning.',
    description:
      'Morning View compares RSVP movement, recent activity, pending forms, and setup progress across active weddings, so the planner can act without rebuilding context across inboxes, sheets, and point tools.',
    proof: 'Two active weddings · one prioritized operating view',
    image: getMarketingCaptureAsset('dashboard', 'homepage'),
    imageAlt: 'Populated Morning View showing active weddings and prioritized planner work',
    supportingImages: [
      {
        label: 'Planner inbox',
        image: getMarketingCaptureAsset('inbox', 'homepage'),
        imageAlt: 'Planner inbox showing wedding conversations in one operational queue',
      },
      {
        label: 'Wedding budget',
        image: getMarketingCaptureAsset('budget', 'homepage'),
        imageAlt: 'Wedding budget showing current category spend and remaining funds',
      },
    ],
    featureIds: ['dashboard', 'inbox', 'payments-autopilot', 'budget'],
  },
  {
    id: 'couple-boundaries',
    pillar: 'Couple Experience + Boundaries',
    headline: 'Give couples a clear view without exposing planner operations.',
    description:
      'The couple dashboard gives Sofia and Daniel a focused wedding overview and RSVP progress. A separate planner workspace presents the Couple Intake Questionnaire, while the couple portal’s Guest Memories review queue shows status filters, keep/reject decisions, and individual downloads.',
    proof: 'Couple overview · planner intake · couple memories controls',
    image: getMarketingCaptureAsset('couple-portal', 'homepage'),
    imageAlt: 'Sofia and Daniel couple dashboard showing the wedding date and RSVP progress',
    supportingImages: [
      {
        label: 'Planner-controlled intake',
        image: getMarketingCaptureAsset('forms', 'homepage'),
        imageAlt: 'Planner form workspace with the couple intake questionnaire',
      },
      {
        label: 'Couple Guest Memories',
        image: getMarketingCaptureAsset('guest-memories', 'homepage'),
        imageAlt: 'Sofia and Daniel Guest Memories review queue showing status filters, keep and reject decisions, and individual download controls',
      },
    ],
    featureIds: ['couple-portal', 'forms', 'guest-memories', 'inbox'],
  },
  {
    id: 'built-for-planners',
    pillar: 'Built for Planners',
    headline: 'Run wedding-specific work generic project tools do not understand.',
    description:
      'Guest Management keeps RSVP, group, meal, and plus-one context together. Seating models the room outline, fixtures, tables, assignments, and layout checks. Planner Vendor Management keeps private contacts, contracts, and payment status in its own operational workspace.',
    proof: 'RSVP context · room layout · private vendor operations',
    image: getMarketingCaptureAsset('seating-orchestrator', 'homepage'),
    imageAlt: 'Venue-aware seating plan with tables, fixtures, and assigned guests',
    supportingImages: [
      {
        label: 'Guest records',
        image: getMarketingCaptureAsset('guest-management', 'homepage'),
        imageAlt: 'Planner guest management workspace with RSVP and household details',
      },
      {
        label: 'Planner vendor records',
        image: getMarketingCaptureAsset('vendor-network', 'homepage'),
        imageAlt: 'Planner Vendor Management showing private contacts, contracts, and payment status',
      },
    ],
    featureIds: ['guest-management', 'seating-orchestrator', 'vendor-network', 'team'],
  },
] as const satisfies readonly [
  PhaseOneProductStory,
  PhaseOneProductStory,
  PhaseOneProductStory,
  PhaseOneProductStory,
];
