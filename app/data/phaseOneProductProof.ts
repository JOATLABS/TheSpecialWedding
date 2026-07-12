import { getMarketingCaptureAsset } from './marketingCaptureManifest';

export type PhaseOneProductStory = {
  id: 'connection' | 'disorganization-tax' | 'couple-boundaries' | 'built-for-planners';
  pillar: string;
  headline: string;
  description: string;
  proof: string;
  image: string;
  imageAlt: string;
  featureIds: readonly string[];
};

export const PHASE_ONE_PRODUCT_STORIES = [
  {
    id: 'connection',
    pillar: 'Connection Over Tools',
    headline: 'Change the plan once. Every surface stays aligned.',
    description:
      'The planner record drives event days, the couple portal, guest-facing details, and the public wedding site. A schedule change stops being a chain of PDFs, texts, and spreadsheet corrections.',
    proof: 'Wedding configuration → couple portal → public schedule',
    image: getMarketingCaptureAsset('wedding-configuration', 'homepage').path,
    imageAlt: 'Populated wedding configuration for Sofia and Daniel in the Marigold and Co. planner workspace',
    featureIds: ['real-time', 'wedding-configuration', 'couple-portal', 'wedding-website'],
  },
  {
    id: 'disorganization-tax',
    pillar: 'Disorganization Tax',
    headline: 'Start the morning knowing what changed overnight.',
    description:
      'Morning View brings active weddings, RSVP movement, unread conversations, upcoming work, and financial signals into one operational view—before the first client message arrives.',
    proof: 'Two active weddings, one prioritized morning view',
    image: getMarketingCaptureAsset('dashboard', 'homepage').path,
    imageAlt: 'Populated Morning View showing active weddings and prioritized planner work',
    featureIds: ['dashboard', 'inbox', 'payments-autopilot', 'budget'],
  },
  {
    id: 'couple-boundaries',
    pillar: 'Couple Experience + Boundaries',
    headline: 'Give couples answers without becoming their human API.',
    description:
      'The couple sees the schedule, messages, forms, registry, FAQs, memories, and payment checkpoints you choose to share. Planner-only operations remain private, and fewer questions spill into late-night texts.',
    proof: 'One guided portal, planner-owned boundaries',
    image: getMarketingCaptureAsset('couple-portal', 'homepage').path,
    imageAlt: 'Sofia and Daniel couple portal with their shared wedding plan and next actions',
    featureIds: ['couple-portal', 'forms', 'guest-memories', 'inbox'],
  },
  {
    id: 'built-for-planners',
    pillar: 'Built for Planners',
    headline: 'Move from guest list to event-day floor plan without rebuilding the data.',
    description:
      'Guest households, RSVP status, meals, plus-ones, tables, room geometry, and venue fixtures stay connected. This is wedding-planner infrastructure, not a generic project board with wedding labels.',
    proof: 'Guest → RSVP → table → venue plan',
    image: getMarketingCaptureAsset('seating-orchestrator', 'homepage').path,
    imageAlt: 'Venue-aware seating plan with tables, fixtures, and assigned guests',
    featureIds: ['guest-management', 'seating-orchestrator', 'vendor-network', 'team'],
  },
] as const satisfies readonly [
  PhaseOneProductStory,
  PhaseOneProductStory,
  PhaseOneProductStory,
  PhaseOneProductStory,
];
