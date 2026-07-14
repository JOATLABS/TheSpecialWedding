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
      'Start with the planner-owned event plan, then compare the matching venue and time in the public microsite and couple timeline. Planner controls remain private.',
    proof: 'Planner event record → public schedule → couple timeline',
    image: getMarketingCaptureAsset('wedding-configuration', 'homepage'),
    imageAlt: 'Populated wedding configuration for Sofia and Daniel in the Marigold and Co. planner workspace',
    supportingImages: [
      {
        label: 'Couple view',
        image: getMarketingCaptureAsset('couple-portal', 'homepage'),
        imageAlt: 'Sofia and Daniel couple portal reflecting their shared wedding plan',
      },
      {
        label: 'Guest view',
        image: getMarketingCaptureAsset('wedding-website', 'homepage'),
        imageAlt: 'Sofia and Daniel public wedding website showing guest-facing details',
      },
    ],
    featureIds: ['real-time', 'wedding-configuration', 'couple-portal', 'wedding-website'],
  },
  {
    id: 'disorganization-tax',
    pillar: 'Disorganization Tax',
    headline: 'Start the morning with the weddings that need attention.',
    description:
      'Morning View compares active weddings using RSVP movement, recent activity, pending forms, and setup progress, then points the planner to the next wedding action.',
    proof: 'Two active weddings · RSVP, activity, forms, and setup signals',
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
      'The couple portal brings the wedding overview, shared timeline, payment context, and assigned forms into one guided experience. Planner-only controls remain private.',
    proof: 'One guided portal, planner-owned boundaries',
    image: getMarketingCaptureAsset('couple-portal', 'homepage'),
    imageAlt: 'Sofia and Daniel couple portal with their shared wedding plan and next actions',
    supportingImages: [
      {
        label: 'Planner-controlled intake',
        image: getMarketingCaptureAsset('forms', 'homepage'),
        imageAlt: 'Planner form workspace with the couple intake questionnaire',
      },
      {
        label: 'Shared couple experience',
        image: getMarketingCaptureAsset('guest-memories', 'homepage'),
        imageAlt: 'Couple portal Guest Memories experience for Sofia and Daniel',
      },
    ],
    featureIds: ['couple-portal', 'forms', 'guest-memories', 'inbox'],
  },
  {
    id: 'built-for-planners',
    pillar: 'Built for Planners',
    headline: 'Review guest context and a venue-aware seating plan in wedding-specific workspaces.',
    description:
      'Guest Management shows response, group, meal, and plus-one context. Seating shows the room outline, fixtures, tables, assignments, and layout checks. Planner Vendor Management keeps private contacts, contracts, and payment status in its own operational view.',
    proof: 'Guest context · seating plan · planner vendor records',
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
