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
  dashboard: {
    route: '/admin/planner',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: 'c4afe5972d2253f91af152440e87b17e4ed2af1a29d76fbaf162cdaaa045e644',
  },
  'real-time': {
    route: '/admin/weddings/[id]',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '0177ab28bc2581b57b80fade0dd7e9500e5049a9cda960fe4e991a4bea9a372b',
  },
  'couple-portal': {
    route: '/couple/dashboard',
    focal: 'main',
    width: 1280,
    height: 720,
    checksum: '8a470789afa506c87097dacb05b16be695723bda010395a8c93e64e1ce68c0a4',
  },
  'wedding-website': {
    route: '/[slug]',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '72c4137063e8b19859d6cfb06b09bb8c7aedf1eb6ace7e9ee9aca8a98f4e2a7e',
  },
  'wedding-configuration': {
    route: '/admin/weddings/[id]',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '0c66fa98b4024fbe1061b0eef550ba3e39859fbe0ace363f26b6c941ba68d436',
  },
  'gallery-management': {
    route: '/admin/gallery/upload',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: 'd5b3431e6dc6274073f0954e71c733ddfc2877330eb9c455ea2fc440e094e4bd',
  },
  'guest-management': {
    route: '/admin/guests',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '1670c6365aeff341d07d2ac8fa3fcd0fcf3fe79b11f5d0c8a81d5bc76b4e820e',
  },
  'seating-orchestrator': {
    route: '/admin/seating',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: 'e37f322b28209bb32b09cc520ac4df65054ac94bd2d21679842f3736d9be4a2d',
  },
  'guest-memories': {
    route: '/couple/dashboard',
    focal: 'main',
    width: 1280,
    height: 720,
    checksum: '2c63db3de0715b1ab143ba877a9847829bd5354f66ad82ab35e3a565a869fd1f',
  },
  inbox: {
    route: '/admin/communications/inbox',
    focal: 'main',
    width: 1280,
    height: 720,
    checksum: '84be4a98db76cfe73145332e775141e1b17e5a4c668fb2c5b0d904aba42ca26d',
  },
  'book-the-client': {
    route: '/admin/vendors/contracts/[id]',
    focal: 'main',
    width: 1280,
    height: 720,
    checksum: '44a16d4f192ff2fb0216f1cf119abab1fd6803333123c1de37cbdf65df2df5ca',
  },
  'payments-autopilot': {
    route: '/admin/money',
    focal: 'main',
    width: 1280,
    height: 720,
    checksum: '283c821576582bea4f589352c6187964e07c233c3dee71ae0c67c53467979511',
  },
  budget: {
    route: '/admin/budget',
    focal: 'main',
    width: 1280,
    height: 720,
    checksum: 'b190f9f8a4542c396b2814fc5f4c9bc282945ccf9d8d8c76d3736c1e652a6229',
  },
  'vendor-network': {
    route: '/admin/vendors',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: 'aa7c2a679efbeeec896b27eb2b8736a5f8a282d86f58d35dfdaa56f1168448b3',
  },
  'knowledge-base': {
    route: '/admin/support?tab=knowledge_base',
    focal: 'main',
    width: 1280,
    height: 720,
    checksum: '4bad23c36467512fdcc8d7535a097a71c0f4089c7dae084c463e2f950aea1753',
  },
  forms: {
    route: '/admin/forms',
    focal: 'main',
    width: 1280,
    height: 720,
    checksum: 'd8cf68f5a616dc1ea67bac72d06fd7a62acb15a8b9e47127fc425cc90b889a99',
  },
  team: {
    route: '/admin/planner/team',
    focal: 'main',
    width: 1280,
    height: 720,
    checksum: '1cf712a6effb500ae575b6ee8f8a6c4543d757669270d7e608505bf9f155087d',
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
    status: 'approved',
    checksum: spec.checksum,
    build: MARKETING_CAPTURE_BUILD,
    sourceRoute: spec.route,
    targets: {
      hero: {
        path: versionedPath,
        width: spec.width,
        height: spec.height,
        aspectRatio: '10:7',
        focalLocator: spec.focal,
      },
      homepage: {
        path: versionedPath,
        width: spec.width,
        height: spec.height,
        aspectRatio: '16:9',
        focalLocator: spec.focal,
      },
      features: {
        path: versionedPath,
        width: spec.width,
        height: spec.height,
        aspectRatio: '16:10',
        focalLocator: spec.focal,
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
  return MARKETING_CAPTURE_MANIFEST[featureId].targets[target];
}
