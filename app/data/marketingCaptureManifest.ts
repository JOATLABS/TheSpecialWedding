export const MARKETING_CAPTURE_BUILD = 'phase-1-2026-07-12';

export type MarketingCaptureStatus = 'pending' | 'captured' | 'approved';
export type MarketingCaptureTarget = 'hero' | 'homepage' | 'features';

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
  sourceRoute: string;
  source: MarketingCaptureSource;
  renders: Record<MarketingCaptureTarget, MarketingCaptureRender>;
};

const CAPTURE_SPECS = {
  dashboard: {
    status: 'approved',
    route: '/admin/planner',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '182fcb1eebc775154b88d548bac84b8dae0cda562626ccefe22464af0d86e846',
  },
  'real-time': {
    status: 'approved',
    route: '/admin/weddings/[id]',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '0bce1885ad9a4bf3ed46f927656a3de24696ba10a2edf98c219f8eecab1b89ff',
  },
  'couple-portal': {
    status: 'approved',
    route: '/couple/dashboard',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: 'e863cdaad3ad575be642dfa60cdbd6c01650f3820e7b65000eb18ed9de812d00',
  },
  'wedding-website': {
    status: 'approved',
    route: '/[slug]',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '5bd9238a0d5f1f1fa008d1f9ddc765216a0d033b34eb2ac4cd3bf43098b14890',
  },
  'wedding-configuration': {
    status: 'approved',
    route: '/admin/weddings/[id]',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: 'f236ad230c4c9d52ccbef834d083e746dedf2a5ad553d1c73711deb3851401c5',
  },
  'gallery-management': {
    status: 'approved',
    route: '/admin/gallery/upload',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '6c8e53f2298daf242e0a2aec5447563c6d489c8b9cdded4385c87af623a0a920',
  },
  'guest-management': {
    status: 'approved',
    route: '/admin/guests',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '5ddc34fb9174f62e3462f120c18c3ba5264c7c3ba49d3d18544202a6f5ee64a8',
  },
  'seating-orchestrator': {
    status: 'approved',
    route: '/admin/seating',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '322e6169246a4abf25f12b0047db01a94d31b2ae27f81673a793332e8b5726eb',
  },
  'guest-memories': {
    status: 'approved',
    route: '/couple/dashboard',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '5699246b0bc20b916a84fdb25aa69a8e6f9a1d3744cde251bbf08967f0daa423',
  },
  inbox: {
    status: 'approved',
    route: '/admin/communications/inbox',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '975e113e5bc12887108beda319fa869199e3ea94f5531c6ea9278e27efd08c18',
  },
  'book-the-client': {
    status: 'approved',
    route: '/admin/vendors/contracts/[id]',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '2368af281707a12f7c896f6ae373c465d13749d65e82dccc033a694943cb9d74',
  },
  'payments-autopilot': {
    status: 'approved',
    route: '/admin/money',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '725f8e27100bb7b06533180bdba818d98539397e5e60a16a13151c2d2136f5a3',
  },
  budget: {
    status: 'approved',
    route: '/admin/budget',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: 'e783521981d8ebfe24e8bd85e5469a9a936b3a129951acfa58a1262a7d7a5ccf',
  },
  'vendor-network': {
    status: 'approved',
    route: '/admin/vendors',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '58a2bde2f4d1a1774870fa9199e95eea259e61eb165c4e9fadd58dd7ed7669bb',
  },
  'knowledge-base': {
    status: 'approved',
    route: '/admin/support?tab=knowledge_base',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '9a952b792bd4488349aece4daf97f2dd8d9bd5dec6d7df6f385ee10f03aae575',
  },
  forms: {
    status: 'approved',
    route: '/admin/forms',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: 'e9bb6e66211abcf4b73ce458be4d5dbc130199868ca2c835c7d0cadef5c6642d',
  },
  team: {
    status: 'approved',
    route: '/admin/planner/team',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '52c1f36f65c5eb3bc285d747a714a6e19b7a68152f8d83e678c8c28a697cff5b',
  },
} as const;

function buildEntry(
  featureId: string,
  spec: (typeof CAPTURE_SPECS)[keyof typeof CAPTURE_SPECS],
): MarketingCaptureEntry {
  const root = `/marketing/product-proof/${featureId}`;
  const versionedPath = `${root}/features.png?v=${spec.checksum.slice(0, 12)}`;

  return {
    featureId,
    status: spec.status,
    build: MARKETING_CAPTURE_BUILD,
    sourceRoute: spec.route,
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
