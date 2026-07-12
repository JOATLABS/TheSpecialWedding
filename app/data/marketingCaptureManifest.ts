export const MARKETING_CAPTURE_BUILD = 'phase-1-2026-07-12';

export type MarketingCaptureStatus = 'pending' | 'captured' | 'approved';
export type MarketingCaptureTarget = 'hero' | 'homepage' | 'features';

export type MarketingCaptureAsset = {
  path: string;
  width: number;
  height: number;
  aspectRatio: string;
  focalLocator: string;
};

export type MarketingCaptureEntry = {
  featureId: string;
  status: MarketingCaptureStatus;
  checksum: string | null;
  build: string;
  sourceRoute: string;
  targets: Record<MarketingCaptureTarget, MarketingCaptureAsset>;
};

const CAPTURE_SPECS = {
  dashboard: { route: '/admin/planner', focal: 'main' },
  'real-time': { route: '/admin/weddings/[id]', focal: '[data-capture="event-days"]' },
  'couple-portal': { route: '/couple/dashboard', focal: 'main' },
  'wedding-website': { route: '/[slug]', focal: 'main' },
  'wedding-configuration': { route: '/admin/weddings/[id]', focal: 'main' },
  'gallery-management': { route: '/admin/gallery/upload', focal: 'main' },
  'guest-management': { route: '/admin/guests', focal: 'main' },
  'seating-orchestrator': { route: '/admin/seating?weddingId=[id]', focal: 'main' },
  'guest-memories': { route: '/admin/memories', focal: 'main' },
  inbox: { route: '/admin/communications/inbox', focal: 'main' },
  'book-the-client': { route: '/admin/vendors/contracts/[id]', focal: 'main' },
  'payments-autopilot': { route: '/admin/money', focal: 'main' },
  budget: { route: '/admin/budget', focal: 'main' },
  'vendor-network': { route: '/admin/vendors', focal: 'main' },
  'knowledge-base': { route: '/admin/support?tab=knowledge_base', focal: 'main' },
  forms: { route: '/admin/forms', focal: 'main' },
  team: { route: '/admin/planner/team', focal: 'main' },
} as const;

function buildEntry(featureId: string, sourceRoute: string, focalLocator: string): MarketingCaptureEntry {
  const root = `/marketing/product-proof/${featureId}`;

  return {
    featureId,
    status: 'pending',
    checksum: null,
    build: MARKETING_CAPTURE_BUILD,
    sourceRoute,
    targets: {
      hero: {
        path: `${root}/hero.png`,
        width: 1600,
        height: 1120,
        aspectRatio: '10:7',
        focalLocator,
      },
      homepage: {
        path: `${root}/homepage.png`,
        width: 1600,
        height: 900,
        aspectRatio: '16:9',
        focalLocator,
      },
      features: {
        path: `${root}/features.png`,
        width: 1600,
        height: 1000,
        aspectRatio: '16:10',
        focalLocator,
      },
    },
  };
}

export const MARKETING_CAPTURE_MANIFEST = Object.fromEntries(
  Object.entries(CAPTURE_SPECS).map(([featureId, spec]) => [
    featureId,
    buildEntry(featureId, spec.route, spec.focal),
  ]),
) as Record<keyof typeof CAPTURE_SPECS, MarketingCaptureEntry>;

export function getMarketingCaptureAsset(
  featureId: keyof typeof MARKETING_CAPTURE_MANIFEST,
  target: MarketingCaptureTarget,
): MarketingCaptureAsset {
  return MARKETING_CAPTURE_MANIFEST[featureId].targets[target];
}

