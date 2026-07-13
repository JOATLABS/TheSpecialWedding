export const MARKETING_CAPTURE_BUILD = '3d089827224b33db223d99c4950631d7f533f64d';

export const MARKETING_CAPTURE_VIEWPORT = {
  width: 1440,
  height: 900,
} as const;

export const MARKETING_CAPTURE_SESSIONS = ['planner', 'couple', 'public'] as const;

export const MARKETING_CAPTURE_SAFETY_ASSERTIONS = [
  'No localhost address, developer overlay, token, or local file path is visible.',
  'No smoke, test, proof-render, or personal-customer identity is visible.',
  'The complete product shell and populated stable state are visible.',
] as const;

export type MarketingCaptureStatus = 'pending' | 'captured' | 'approved';
export type MarketingCaptureTarget = 'hero' | 'homepage' | 'features';
export type MarketingCaptureSession = (typeof MARKETING_CAPTURE_SESSIONS)[number];

export type MarketingCaptureSource = {
  path: string;
  width: number;
  height: number;
  checksum: string;
  framing: 'full-window';
  captureMethod: 'manual-in-app-browser';
  captureBounds: {
    x: 0;
    y: 0;
    width: number;
    height: number;
  };
  focalLocator: string;
};

export type MarketingCaptureRender = {
  frameAspectRatio: '16:10';
  fit: 'contain';
  zoom: false;
};

export type MarketingCaptureAsset = MarketingCaptureSource & {
  render: MarketingCaptureRender;
};

export type MarketingCaptureEntry = {
  featureId: string;
  status: MarketingCaptureStatus;
  build: string;
  requiredSession: MarketingCaptureSession;
  sourceRoute: string;
  stableState: {
    selector: string;
    expectedVisibleText: string;
  };
  viewport: {
    width: 1440;
    height: 900;
  };
  safeInteraction?: string;
  safetyAssertions: readonly string[];
  source: MarketingCaptureSource;
  renders: Record<MarketingCaptureTarget, MarketingCaptureRender>;
};

type CaptureSpec = {
  status: MarketingCaptureStatus;
  route: string;
  focal: string;
  interaction?: string;
  width: number;
  height: number;
  checksum: string;
  build?: string;
};

const CAPTURE_SPECS = {
  dashboard: {
    status: 'pending',
    route: '/admin/planner',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '182fcb1eebc775154b88d548bac84b8dae0cda562626ccefe22464af0d86e846',
  },
  'real-time': {
    status: 'pending',
    route: '/admin/weddings/wedding_marketing_capture_sofia_daniel',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '0bce1885ad9a4bf3ed46f927656a3de24696ba10a2edf98c219f8eecab1b89ff',
  },
  'couple-portal': {
    status: 'pending',
    route: '/couple/dashboard',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: 'e863cdaad3ad575be642dfa60cdbd6c01650f3820e7b65000eb18ed9de812d00',
  },
  'wedding-website': {
    status: 'pending',
    route: '/sofia-and-daniel',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '5bd9238a0d5f1f1fa008d1f9ddc765216a0d033b34eb2ac4cd3bf43098b14890',
  },
  'wedding-configuration': {
    status: 'pending',
    route: '/admin/weddings/wedding_marketing_capture_sofia_daniel',
    focal: 'main',
    interaction: 'Open the RSVP section without changing any fields.',
    width: 1440,
    height: 900,
    checksum: 'f236ad230c4c9d52ccbef834d083e746dedf2a5ad553d1c73711deb3851401c5',
  },
  'gallery-management': {
    status: 'pending',
    route: '/admin/gallery/upload',
    focal: 'main',
    interaction: 'Select Sofia & Daniel, open Manage Gallery, and wait for the three seeded gallery items.',
    width: 1440,
    height: 900,
    checksum: '6c8e53f2298daf242e0a2aec5447563c6d489c8b9cdded4385c87af623a0a920',
  },
  'guest-management': {
    status: 'pending',
    route: '/admin/guests',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '5ddc34fb9174f62e3462f120c18c3ba5264c7c3ba49d3d18544202a6f5ee64a8',
  },
  'seating-orchestrator': {
    status: 'pending',
    route: '/admin/seating?weddingId=wedding_marketing_capture_sofia_daniel',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '322e6169246a4abf25f12b0047db01a94d31b2ae27f81673a793332e8b5726eb',
  },
  'guest-memories': {
    status: 'pending',
    route: '/couple/dashboard',
    focal: 'main',
    interaction: 'Open Memories in the couple portal and wait for the review queue.',
    width: 1440,
    height: 900,
    checksum: '5699246b0bc20b916a84fdb25aa69a8e6f9a1d3744cde251bbf08967f0daa423',
  },
  inbox: {
    status: 'pending',
    route: '/admin/communications/inbox',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '975e113e5bc12887108beda319fa869199e3ea94f5531c6ea9278e27efd08c18',
  },
  'book-the-client': {
    status: 'pending',
    route: '/admin/vendors/contracts/67c100000000000000000001',
    focal: 'main',
    interaction: 'Open Payments and wait for Payment Milestones without changing the contract.',
    width: 1440,
    height: 900,
    checksum: '2368af281707a12f7c896f6ae373c465d13749d65e82dccc033a694943cb9d74',
  },
  'payments-autopilot': {
    status: 'pending',
    route: '/admin/money',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '725f8e27100bb7b06533180bdba818d98539397e5e60a16a13151c2d2136f5a3',
  },
  budget: {
    status: 'pending',
    route: '/admin/budget?wedding_id=wedding_marketing_capture_sofia_daniel',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: 'e783521981d8ebfe24e8bd85e5469a9a936b3a129951acfa58a1262a7d7a5ccf',
  },
  'vendor-network': {
    status: 'pending',
    route: '/admin/vendors',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '58a2bde2f4d1a1774870fa9199e95eea259e61eb165c4e9fadd58dd7ed7669bb',
  },
  'knowledge-base': {
    status: 'pending',
    route: '/admin/support?tab=knowledge_base',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '9a952b792bd4488349aece4daf97f2dd8d9bd5dec6d7df6f385ee10f03aae575',
  },
  forms: {
    status: 'pending',
    route: '/admin/forms',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: 'e9bb6e66211abcf4b73ce458be4d5dbc130199868ca2c835c7d0cadef5c6642d',
  },
  team: {
    status: 'pending',
    route: '/admin/planner/team',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '52c1f36f65c5eb3bc285d747a714a6e19b7a68152f8d83e678c8c28a697cff5b',
  },
} as const satisfies Record<string, CaptureSpec>;

const CAPTURE_SCENE_CONTEXT = {
  dashboard: { session: 'planner', expectedText: 'Welcome back, Marigold & Co. Weddings!' },
  'real-time': { session: 'planner', expectedText: 'Sofia & Daniel' },
  'couple-portal': { session: 'couple', expectedText: 'Sofia & Daniel' },
  'wedding-website': { session: 'public', expectedText: 'Sofia & Daniel' },
  'wedding-configuration': { session: 'planner', expectedText: 'RSVP Configuration' },
  'gallery-management': { session: 'planner', expectedText: 'Gallery Management' },
  'guest-management': { session: 'planner', expectedText: 'Guest Management' },
  'seating-orchestrator': { session: 'planner', expectedText: 'Seating Arrangement' },
  'guest-memories': { session: 'couple', expectedText: 'Guest Memories' },
  inbox: { session: 'planner', expectedText: 'Inbox' },
  'book-the-client': { session: 'planner', expectedText: 'Payment Milestones' },
  'payments-autopilot': { session: 'planner', expectedText: 'Money' },
  budget: { session: 'planner', expectedText: 'Budget Overview' },
  'vendor-network': { session: 'planner', expectedText: 'Vendor Management' },
  'knowledge-base': { session: 'planner', expectedText: 'Knowledge Base' },
  forms: { session: 'planner', expectedText: 'Couple Intake Questionnaire' },
  team: { session: 'planner', expectedText: 'Team Management' },
} as const satisfies Record<
  keyof typeof CAPTURE_SPECS,
  { session: MarketingCaptureSession; expectedText: string }
>;

function buildEntry(
  featureId: string,
  spec: CaptureSpec,
): MarketingCaptureEntry {
  const root = `/marketing/product-proof/${featureId}`;
  const versionedPath = `${root}/features.png?v=${spec.checksum.slice(0, 12)}`;

  const scene = CAPTURE_SCENE_CONTEXT[featureId as keyof typeof CAPTURE_SCENE_CONTEXT];

  return {
    featureId,
    status: spec.status,
    build: spec.build ?? MARKETING_CAPTURE_BUILD,
    requiredSession: scene.session,
    sourceRoute: spec.route,
    stableState: {
      selector: spec.focal,
      expectedVisibleText: scene.expectedText,
    },
    viewport: { ...MARKETING_CAPTURE_VIEWPORT },
    ...(spec.interaction ? { safeInteraction: spec.interaction } : {}),
    safetyAssertions: MARKETING_CAPTURE_SAFETY_ASSERTIONS,
    source: {
      path: versionedPath,
      width: spec.width,
      height: spec.height,
      checksum: spec.checksum,
      framing: 'full-window',
      captureMethod: 'manual-in-app-browser',
      captureBounds: {
        x: 0,
        y: 0,
        width: spec.width,
        height: spec.height,
      },
      focalLocator: spec.focal,
    },
    renders: {
      hero: {
        frameAspectRatio: '16:10',
        fit: 'contain',
        zoom: false,
      },
      homepage: {
        frameAspectRatio: '16:10',
        fit: 'contain',
        zoom: false,
      },
      features: {
        frameAspectRatio: '16:10',
        fit: 'contain',
        zoom: false,
      },
    },
  };
}

export const MARKETING_CAPTURE_MANIFEST = Object.fromEntries(
  Object.entries(CAPTURE_SPECS).map(([featureId, spec]) => [
    featureId,
    buildEntry(featureId, spec),
  ]),
) as Record<keyof typeof CAPTURE_SPECS, MarketingCaptureEntry>;

export function getMarketingCaptureAsset(
  featureId: keyof typeof MARKETING_CAPTURE_MANIFEST,
  target: MarketingCaptureTarget,
): MarketingCaptureAsset {
  const entry = MARKETING_CAPTURE_MANIFEST[featureId];
  return {
    ...entry.source,
    render: entry.renders[target],
  };
}
