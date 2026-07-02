export type MarketingDemoPublicationStatus = 'review-ready' | 'published';

export type MarketingDemoVideoChapter = {
  title: string;
  startSeconds: number;
  description: string;
};

export type MarketingDemoVideoPage = {
  slug: string;
  title: string;
  seoTitle: string;
  description: string;
  audience: string;
  durationSeconds: number;
  width: number;
  height: number;
  uploadDate: string;
  lastReviewedDate: string;
  publicationStatus: MarketingDemoPublicationStatus;
  localReviewArtifact: string;
  localProofArtifact: string;
  r2ObjectKey: string;
  thumbnailObjectKey: string;
  captionsObjectKey?: string;
  transcriptObjectKey?: string;
  chapters: readonly MarketingDemoVideoChapter[];
  transcriptSummary: readonly string[];
};

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, '') || 'https://thespecialwedding.io';

const MARKETING_VIDEO_CDN_BASE_URL =
  (
    process.env.NEXT_PUBLIC_MARKETING_VIDEO_CDN_URL ||
    process.env.MARKETING_VIDEO_CDN_BASE_URL ||
    'https://media.thespecialwedding.io/demo-videos'
  ).replace(/\/$/, '');

export const MARKETING_DEMO_VIDEO_PAGES: readonly MarketingDemoVideoPage[] = [
  {
    slug: 'planner-command-center-social-highlights',
    title: 'Planner Command Center Social Highlights',
    seoTitle: 'Planner Command Center Demo Video | The Special Wedding',
    description:
      'A public-safe vertical walkthrough showing how a planner manages weddings, guests, communications, memories, couple portal, seating, vendors, contracts, budget, payments, and notifications from one workspace.',
    audience: 'Professional wedding planners evaluating the real operating workspace before starting a trial.',
    durationSeconds: 80,
    width: 1080,
    height: 1920,
    uploadDate: '2026-07-01',
    lastReviewedDate: '2026-07-01',
    publicationStatus: 'review-ready',
    localReviewArtifact:
      'output/demo-videos/live-recordings/stitched/003-public-safe-social-highlights-v4-vertical.mp4',
    localProofArtifact:
      'output/demo-videos/live-recordings/stitched/003-public-safe-social-highlights-v4-proof.json',
    r2ObjectKey: 'planner-command-center-social-highlights/v4-vertical.mp4',
    thumbnailObjectKey: 'planner-command-center-social-highlights/v4-poster.jpg',
    captionsObjectKey: 'planner-command-center-social-highlights/v4-captions.vtt',
    transcriptObjectKey: 'planner-command-center-social-highlights/v4-transcript.txt',
    chapters: [
      {
        title: 'Real planner workspace',
        startSeconds: 0,
        description: 'A public-safe walkthrough of the platform a planner uses every day.',
      },
      {
        title: 'Planner dashboard',
        startSeconds: 3,
        description: 'Multiple weddings, RSVP movement, reminders, and urgent work from one home base.',
      },
      {
        title: 'Start a new wedding',
        startSeconds: 8,
        description: 'Create a couple workspace and keep a planner portfolio moving.',
      },
      {
        title: 'Guest list operations',
        startSeconds: 17,
        description: 'Import guests, track RSVPs, groups, plus-ones, meal notes, and reminders.',
      },
      {
        title: 'Preview-safe messages',
        startSeconds: 23,
        description: 'Email and SMS campaigns preview before sending in the demo workspace.',
      },
      {
        title: 'Guest memories',
        startSeconds: 27,
        description: 'Guests contribute photos and notes through a shareable memory flow.',
      },
      {
        title: 'Couple portal',
        startSeconds: 37,
        description: 'Couples review tasks, messages, RSVPs, and planning updates without spreadsheets.',
      },
      {
        title: 'Seating orchestrator',
        startSeconds: 42,
        description: 'Drag guests, place tables, and guide setup for real venue layouts.',
      },
      {
        title: 'Vendor contracts',
        startSeconds: 48,
        description: 'Send signable vendor agreements with clean review and payment context.',
      },
      {
        title: 'Budget and payments',
        startSeconds: 52,
        description: 'Track spend, paid items, quotes, and remaining balances by wedding.',
      },
      {
        title: 'Payment Autopilot',
        startSeconds: 57,
        description: 'Review payment method, billing history, plan features, and budget handoff.',
      },
      {
        title: 'One calm command center',
        startSeconds: 74,
        description: 'A single workspace for planners managing multiple weddings, couples, vendors, and guests.',
      },
    ],
    transcriptSummary: [
      'Real planner workspace for the day-to-day command center.',
      'Planner dashboard, new wedding setup, configuration, guest operations, preview-safe communications, guest memories, couple website, couple portal, seating, vendor contracts, budget, payments, packages, money, and notifications.',
      'Current review candidate is visual-only pending final pacing and audio approval.',
    ],
  },
  {
    slug: 'planner-platform-full-walkthrough',
    title: 'Full Planner Platform Walkthrough',
    seoTitle: 'Full Wedding Planner Software Walkthrough | The Special Wedding',
    description:
      'A full-width public-safe review reel covering the planner portfolio, new wedding setup, configuration, shared calendar, guest management, communications, forms, guest memories, gallery, public microsite, couple portal, seating, vendors, contracts, quotes, budgets, payments, team collaboration, and support workflows.',
    audience: 'Planner studios and agency teams evaluating the full workflow surface before adopting the platform.',
    durationSeconds: 486,
    width: 1920,
    height: 1080,
    uploadDate: '2026-07-01',
    lastReviewedDate: '2026-07-01',
    publicationStatus: 'review-ready',
    localReviewArtifact:
      'output/demo-videos/live-recordings/stitched/001-public-safe-marketing-reel-v15-rough.mp4',
    localProofArtifact:
      'output/demo-videos/live-recordings/stitched/001-public-safe-marketing-reel-v15-rough-proof.json',
    r2ObjectKey: 'planner-platform-full-walkthrough/v15-16x9.mp4',
    thumbnailObjectKey: 'planner-platform-full-walkthrough/v15-poster.jpg',
    captionsObjectKey: 'planner-platform-full-walkthrough/v15-captions.vtt',
    transcriptObjectKey: 'planner-platform-full-walkthrough/v15-transcript.txt',
    chapters: [
      {
        title: 'Planner portfolio dashboard',
        startSeconds: 0,
        description: 'JoshLoveWeds manages multiple active weddings from one dashboard.',
      },
      {
        title: 'New wedding setup',
        startSeconds: 18,
        description: 'Add a polished new client without touching live customer data.',
      },
      {
        title: 'Wedding configuration',
        startSeconds: 42,
        description: 'Schedule, RSVP, FAQ, theme, and couple portal setup in one place.',
      },
      {
        title: 'Shared planner calendar',
        startSeconds: 60,
        description: 'Agenda and timeline details stay attached to the wedding workspace.',
      },
      {
        title: 'Guest management',
        startSeconds: 75,
        description: 'RSVP status, guest filters, and plus-one details move through the planner workflow.',
      },
      {
        title: 'Communications',
        startSeconds: 99,
        description: 'Reminder composer and preview-only SMS/email modal for demo-safe sends.',
      },
      {
        title: 'Forms and guest memories',
        startSeconds: 107,
        description: 'Form responses and QR memory upload flows stay connected to the wedding record.',
      },
      {
        title: 'Public microsite and couple portal',
        startSeconds: 166,
        description: 'Guest-facing site, gallery, couple dashboard, timeline, inbox, memories, and FAQ.',
      },
      {
        title: 'Seating and venue layout',
        startSeconds: 214,
        description: 'Seating orchestrator, setup guide, and floor-plan-aware guest placement.',
      },
      {
        title: 'Vendor CRM and contracts',
        startSeconds: 247,
        description: 'Vendor directory, CRM, contract canvas, token portal, and review-safe contract flow.',
      },
      {
        title: 'Quotes, budget, and payments',
        startSeconds: 293,
        description: 'Quote comparison, budget state, payment history, and Payment Autopilot handoff.',
      },
      {
        title: 'Team, support, and operations',
        startSeconds: 389,
        description: 'Team collaboration, program run of show, couple notes, support knowledge base, packages, money, and notifications.',
      },
    ],
    transcriptSummary: [
      'Full public-safe review reel assembled from 24 accepted browser-recorded clips.',
      'The reel covers planner, couple, guest, vendor, contract, budget, payment, team, and support surfaces.',
      'Current full review candidate is pending final human pacing review and final audio direction.',
    ],
  },
];

export function getMarketingDemoVideoBySlug(slug: string): MarketingDemoVideoPage | undefined {
  return MARKETING_DEMO_VIDEO_PAGES.find((video) => video.slug === slug);
}

export function getMarketingDemoVideoCanonicalPath(video: MarketingDemoVideoPage): string {
  return `/resources/demos/${video.slug}`;
}

export function getMarketingDemoVideoCanonicalUrl(video: MarketingDemoVideoPage): string {
  return `${SITE_URL}${getMarketingDemoVideoCanonicalPath(video)}`;
}

export function getMarketingDemoVideoAssetUrl(objectKey: string): string {
  return `${MARKETING_VIDEO_CDN_BASE_URL}/${objectKey.replace(/^\/+/, '')}`;
}

export function getMarketingDemoVideoThumbnailUrl(video: MarketingDemoVideoPage): string {
  return getMarketingDemoVideoAssetUrl(video.thumbnailObjectKey);
}

export function getMarketingDemoVideoContentUrl(video: MarketingDemoVideoPage): string {
  return getMarketingDemoVideoAssetUrl(video.r2ObjectKey);
}

export function getMarketingDemoVideoCaptionsUrl(video: MarketingDemoVideoPage): string | undefined {
  if (!video.captionsObjectKey) return undefined;
  return getMarketingDemoVideoAssetUrl(video.captionsObjectKey);
}

export function isMarketingDemoVideoIndexable(video: MarketingDemoVideoPage): boolean {
  return (
    video.publicationStatus === 'published' ||
    process.env.MARKETING_VIDEO_INCLUDE_REVIEW_READY_IN_SITEMAP === 'true'
  );
}

export function formatIso8601Duration(totalSeconds: number): string {
  const seconds = Math.max(1, Math.round(totalSeconds));
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes === 0) return `PT${remainingSeconds}S`;
  if (remainingSeconds === 0) return `PT${minutes}M`;
  return `PT${minutes}M${remainingSeconds}S`;
}
