export const MARKETING_CAPTURE_BUILD = '4ea6ec1f6c75f529133a9a60afc9fb471e40976c';

export const MARKETING_CAPTURE_RUNTIME_ORIGIN = 'http://127.0.0.1:3100' as const;
export const MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR =
  'meta[name="tsw-app-build-commit"]' as const;

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

export type MarketingCaptureReviewReceipt = {
  schemaVersion: 1;
  featureId: string;
  capturedAt: string;
  reviewedAt: string;
  reviewer: string;
  appBuildCommit: string;
  artifactSha256: string;
  runtimeBuildIdentity: {
    origin: typeof MARKETING_CAPTURE_RUNTIME_ORIGIN;
    identitySelector: typeof MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR;
    observedCommit: string;
    verifiedAt: string;
  };
  browser: 'Google Chrome';
  browserWasVisible: true;
  interactionsWereManual: true;
  scriptedBrowserCaptureWasUsed: false;
  pageZoomPercent: 100;
  viewportMode: 'Responsive';
  devicePixelRatio: 1;
  captureCommand: 'Capture screenshot';
  fullSizeScreenshotWasUsed: false;
  originalPngReviewed: true;
  postCaptureTransformsApplied: false;
};

export type MarketingCaptureSource = {
  path: string;
  width: number;
  height: number;
  checksum: string;
  framing: 'full-window';
  captureMethod: 'manual-visible-browser';
  reviewReceipt: MarketingCaptureReviewReceipt | null;
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
  featureId: string;
  status: MarketingCaptureStatus;
  build: string;
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
  reviewReceipt?: MarketingCaptureReviewReceipt;
};

const CAPTURE_SPECS = {
  dashboard: {
    status: 'approved',
    route: '/admin/planner',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '934ac7050b606fdb13ae833cbd6ac375fb944522254e0ede803872bcc6eb2037',
    build: '4113e701f25683dcb621bd991009a583604df1d3',
    reviewReceipt: {
      schemaVersion: 1,
      featureId: 'dashboard',
      capturedAt: '2026-07-14T04:47:55.000Z',
      reviewedAt: '2026-07-14T04:48:10.000Z',
      reviewer: 'OpenAI Codex manual visual review',
      appBuildCommit: '4113e701f25683dcb621bd991009a583604df1d3',
      artifactSha256: '934ac7050b606fdb13ae833cbd6ac375fb944522254e0ede803872bcc6eb2037',
      runtimeBuildIdentity: {
        origin: MARKETING_CAPTURE_RUNTIME_ORIGIN,
        identitySelector: MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR,
        observedCommit: '4113e701f25683dcb621bd991009a583604df1d3',
        verifiedAt: '2026-07-14T04:45:00.000Z',
      },
      browser: 'Google Chrome',
      browserWasVisible: true,
      interactionsWereManual: true,
      scriptedBrowserCaptureWasUsed: false,
      pageZoomPercent: 100,
      viewportMode: 'Responsive',
      devicePixelRatio: 1,
      captureCommand: 'Capture screenshot',
      fullSizeScreenshotWasUsed: false,
      originalPngReviewed: true,
      postCaptureTransformsApplied: false,
    },
  },
  'real-time': {
    status: 'approved',
    route: '/admin/weddings/wedding_marketing_capture_sofia_daniel',
    focal: 'main',
    interaction: 'Open Events and wait for the Traditional event at The Glasshouse at Riverbend at 4:00 PM.',
    width: 1440,
    height: 900,
    checksum: '5803440808fc12954dc75cbb9d265b13ed8fba8633fd3209441149428c113f7d',
    build: '4113e701f25683dcb621bd991009a583604df1d3',
    reviewReceipt: {
      schemaVersion: 1,
      featureId: 'real-time',
      capturedAt: '2026-07-14T04:49:14.000Z',
      reviewedAt: '2026-07-14T04:49:25.000Z',
      reviewer: 'OpenAI Codex manual visual review',
      appBuildCommit: '4113e701f25683dcb621bd991009a583604df1d3',
      artifactSha256: '5803440808fc12954dc75cbb9d265b13ed8fba8633fd3209441149428c113f7d',
      runtimeBuildIdentity: {
        origin: MARKETING_CAPTURE_RUNTIME_ORIGIN,
        identitySelector: MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR,
        observedCommit: '4113e701f25683dcb621bd991009a583604df1d3',
        verifiedAt: '2026-07-14T04:45:00.000Z',
      },
      browser: 'Google Chrome',
      browserWasVisible: true,
      interactionsWereManual: true,
      scriptedBrowserCaptureWasUsed: false,
      pageZoomPercent: 100,
      viewportMode: 'Responsive',
      devicePixelRatio: 1,
      captureCommand: 'Capture screenshot',
      fullSizeScreenshotWasUsed: false,
      originalPngReviewed: true,
      postCaptureTransformsApplied: false,
    },
  },
  'couple-portal': {
    status: 'approved',
    route: '/couple/dashboard',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: 'daa25e1c2f17983e07c4b2b4b69ce403ce338844346abae625ccedbc31cbfc59',
    build: '4113e701f25683dcb621bd991009a583604df1d3',
    reviewReceipt: {
      schemaVersion: 1,
      featureId: 'couple-portal',
      capturedAt: '2026-07-14T04:53:05.000Z',
      reviewedAt: '2026-07-14T04:53:17.000Z',
      reviewer: 'OpenAI Codex manual visual review',
      appBuildCommit: '4113e701f25683dcb621bd991009a583604df1d3',
      artifactSha256: 'daa25e1c2f17983e07c4b2b4b69ce403ce338844346abae625ccedbc31cbfc59',
      runtimeBuildIdentity: {
        origin: MARKETING_CAPTURE_RUNTIME_ORIGIN,
        identitySelector: MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR,
        observedCommit: '4113e701f25683dcb621bd991009a583604df1d3',
        verifiedAt: '2026-07-14T04:45:00.000Z',
      },
      browser: 'Google Chrome',
      browserWasVisible: true,
      interactionsWereManual: true,
      scriptedBrowserCaptureWasUsed: false,
      pageZoomPercent: 100,
      viewportMode: 'Responsive',
      devicePixelRatio: 1,
      captureCommand: 'Capture screenshot',
      fullSizeScreenshotWasUsed: false,
      originalPngReviewed: true,
      postCaptureTransformsApplied: false,
    },
  },
  'wedding-website': {
    status: 'approved',
    route: '/sofia-and-daniel',
    focal: 'main',
    interaction: 'Open the Venue section and wait for The Glasshouse at Riverbend.',
    width: 1440,
    height: 900,
    checksum: 'fc820621227b026d32d88d2f57abe4dec5819336386a8422c7c5630e86da2e81',
    build: '4ea6ec1f6c75f529133a9a60afc9fb471e40976c',
    reviewReceipt: {
      schemaVersion: 1,
      featureId: 'wedding-website',
      capturedAt: '2026-07-14T14:29:48.000Z',
      reviewedAt: '2026-07-14T14:30:30.000Z',
      reviewer: 'OpenAI Codex manual visual review',
      appBuildCommit: '4ea6ec1f6c75f529133a9a60afc9fb471e40976c',
      artifactSha256: 'fc820621227b026d32d88d2f57abe4dec5819336386a8422c7c5630e86da2e81',
      runtimeBuildIdentity: {
        origin: MARKETING_CAPTURE_RUNTIME_ORIGIN,
        identitySelector: MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR,
        observedCommit: '4ea6ec1f6c75f529133a9a60afc9fb471e40976c',
        verifiedAt: '2026-07-14T14:25:46.000Z',
      },
      browser: 'Google Chrome',
      browserWasVisible: true,
      interactionsWereManual: true,
      scriptedBrowserCaptureWasUsed: false,
      pageZoomPercent: 100,
      viewportMode: 'Responsive',
      devicePixelRatio: 1,
      captureCommand: 'Capture screenshot',
      fullSizeScreenshotWasUsed: false,
      originalPngReviewed: true,
      postCaptureTransformsApplied: false,
    },
  },
  'wedding-configuration': {
    status: 'approved',
    route: '/admin/weddings/wedding_marketing_capture_sofia_daniel',
    focal: 'main',
    interaction: 'Open the RSVP section without changing any fields.',
    width: 1440,
    height: 900,
    checksum: '80a1e2e673006d9a6a8cc39c14c068f6276d0d8284903cdcb6d07610c997e269',
    build: '4113e701f25683dcb621bd991009a583604df1d3',
    reviewReceipt: {
      schemaVersion: 1,
      featureId: 'wedding-configuration',
      capturedAt: '2026-07-14T04:51:46.000Z',
      reviewedAt: '2026-07-14T04:51:58.000Z',
      reviewer: 'OpenAI Codex manual visual review',
      appBuildCommit: '4113e701f25683dcb621bd991009a583604df1d3',
      artifactSha256: '80a1e2e673006d9a6a8cc39c14c068f6276d0d8284903cdcb6d07610c997e269',
      runtimeBuildIdentity: {
        origin: MARKETING_CAPTURE_RUNTIME_ORIGIN,
        identitySelector: MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR,
        observedCommit: '4113e701f25683dcb621bd991009a583604df1d3',
        verifiedAt: '2026-07-14T04:45:00.000Z',
      },
      browser: 'Google Chrome',
      browserWasVisible: true,
      interactionsWereManual: true,
      scriptedBrowserCaptureWasUsed: false,
      pageZoomPercent: 100,
      viewportMode: 'Responsive',
      devicePixelRatio: 1,
      captureCommand: 'Capture screenshot',
      fullSizeScreenshotWasUsed: false,
      originalPngReviewed: true,
      postCaptureTransformsApplied: false,
    },
  },
  'gallery-management': {
    status: 'approved',
    route: '/admin/gallery/upload',
    focal: 'main',
    interaction: 'Select Sofia & Daniel, open Manage Gallery, and wait for the three seeded gallery items.',
    width: 1440,
    height: 900,
    checksum: '1de2901650e7e3e0b09e0e5e79cc9c61321dd60cbd2f410246a4975d1d3d254f',
    build: '4ea6ec1f6c75f529133a9a60afc9fb471e40976c',
    reviewReceipt: {
      schemaVersion: 1,
      featureId: 'gallery-management',
      capturedAt: '2026-07-14T14:28:07.000Z',
      reviewedAt: '2026-07-14T14:30:30.000Z',
      reviewer: 'OpenAI Codex manual visual review',
      appBuildCommit: '4ea6ec1f6c75f529133a9a60afc9fb471e40976c',
      artifactSha256: '1de2901650e7e3e0b09e0e5e79cc9c61321dd60cbd2f410246a4975d1d3d254f',
      runtimeBuildIdentity: {
        origin: MARKETING_CAPTURE_RUNTIME_ORIGIN,
        identitySelector: MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR,
        observedCommit: '4ea6ec1f6c75f529133a9a60afc9fb471e40976c',
        verifiedAt: '2026-07-14T14:25:46.000Z',
      },
      browser: 'Google Chrome',
      browserWasVisible: true,
      interactionsWereManual: true,
      scriptedBrowserCaptureWasUsed: false,
      pageZoomPercent: 100,
      viewportMode: 'Responsive',
      devicePixelRatio: 1,
      captureCommand: 'Capture screenshot',
      fullSizeScreenshotWasUsed: false,
      originalPngReviewed: true,
      postCaptureTransformsApplied: false,
    },
  },
  'guest-management': {
    status: 'approved',
    route: '/admin/guests',
    focal: 'main',
    interaction: 'Verify the wedding picker shows Sofia & Daniel; select it if needed.',
    width: 1440,
    height: 900,
    checksum: '9d57a833a022ca38a602fae582c8465bbf9c2c2c1ced565b86f87694bf4a1522',
    build: '4113e701f25683dcb621bd991009a583604df1d3',
    reviewReceipt: {
      schemaVersion: 1,
      featureId: 'guest-management',
      capturedAt: '2026-07-14T04:59:29.000Z',
      reviewedAt: '2026-07-14T04:59:42.000Z',
      reviewer: 'OpenAI Codex manual visual review',
      appBuildCommit: '4113e701f25683dcb621bd991009a583604df1d3',
      artifactSha256: '9d57a833a022ca38a602fae582c8465bbf9c2c2c1ced565b86f87694bf4a1522',
      runtimeBuildIdentity: {
        origin: MARKETING_CAPTURE_RUNTIME_ORIGIN,
        identitySelector: MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR,
        observedCommit: '4113e701f25683dcb621bd991009a583604df1d3',
        verifiedAt: '2026-07-14T04:45:00.000Z',
      },
      browser: 'Google Chrome',
      browserWasVisible: true,
      interactionsWereManual: true,
      scriptedBrowserCaptureWasUsed: false,
      pageZoomPercent: 100,
      viewportMode: 'Responsive',
      devicePixelRatio: 1,
      captureCommand: 'Capture screenshot',
      fullSizeScreenshotWasUsed: false,
      originalPngReviewed: true,
      postCaptureTransformsApplied: false,
    },
  },
  'seating-orchestrator': {
    status: 'approved',
    route: '/admin/seating?weddingId=wedding_marketing_capture_sofia_daniel',
    focal: 'main',
    interaction: 'Select Sofia & Daniel, then use the in-product Zoom out control twice until the canvas reads 70%. Keep Chrome page zoom at 100%.',
    width: 1440,
    height: 900,
    checksum: 'd70618782128a1f159ee202e03c9227536a5bd2af9c0274420405b6f0b84c4a7',
    build: '4113e701f25683dcb621bd991009a583604df1d3',
    reviewReceipt: {
      schemaVersion: 1,
      featureId: 'seating-orchestrator',
      capturedAt: '2026-07-14T05:03:33.000Z',
      reviewedAt: '2026-07-14T05:03:47.000Z',
      reviewer: 'OpenAI Codex manual visual review',
      appBuildCommit: '4113e701f25683dcb621bd991009a583604df1d3',
      artifactSha256: 'd70618782128a1f159ee202e03c9227536a5bd2af9c0274420405b6f0b84c4a7',
      runtimeBuildIdentity: {
        origin: MARKETING_CAPTURE_RUNTIME_ORIGIN,
        identitySelector: MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR,
        observedCommit: '4113e701f25683dcb621bd991009a583604df1d3',
        verifiedAt: '2026-07-14T04:45:00.000Z',
      },
      browser: 'Google Chrome',
      browserWasVisible: true,
      interactionsWereManual: true,
      scriptedBrowserCaptureWasUsed: false,
      pageZoomPercent: 100,
      viewportMode: 'Responsive',
      devicePixelRatio: 1,
      captureCommand: 'Capture screenshot',
      fullSizeScreenshotWasUsed: false,
      originalPngReviewed: true,
      postCaptureTransformsApplied: false,
    },
  },
  'guest-memories': {
    status: 'approved',
    route: '/couple/dashboard',
    focal: 'main',
    interaction: 'Open Memories in the couple portal and wait for the review queue.',
    width: 1440,
    height: 900,
    checksum: 'bfdf3ea08b74c759ff5dc3ff6ba20914bb1e876cafa1561125eef707003547ff',
    build: '2e2033e8e2fb3bfe7a06bfa4ea9f4f78e0533ab3',
    reviewReceipt: {
      schemaVersion: 1,
      featureId: 'guest-memories',
      capturedAt: '2026-07-15T04:32:09.000Z',
      reviewedAt: '2026-07-15T04:33:47.000Z',
      reviewer: 'OpenAI Codex manual visual review',
      appBuildCommit: '2e2033e8e2fb3bfe7a06bfa4ea9f4f78e0533ab3',
      artifactSha256: 'bfdf3ea08b74c759ff5dc3ff6ba20914bb1e876cafa1561125eef707003547ff',
      runtimeBuildIdentity: {
        origin: MARKETING_CAPTURE_RUNTIME_ORIGIN,
        identitySelector: MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR,
        observedCommit: '2e2033e8e2fb3bfe7a06bfa4ea9f4f78e0533ab3',
        verifiedAt: '2026-07-15T04:26:00.000Z',
      },
      browser: 'Google Chrome',
      browserWasVisible: true,
      interactionsWereManual: true,
      scriptedBrowserCaptureWasUsed: false,
      pageZoomPercent: 100,
      viewportMode: 'Responsive',
      devicePixelRatio: 1,
      captureCommand: 'Capture screenshot',
      fullSizeScreenshotWasUsed: false,
      originalPngReviewed: true,
      postCaptureTransformsApplied: false,
    },
  },
  inbox: {
    status: 'approved',
    route: '/admin/communications/inbox',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: 'c71032e14792e0640878f1d8da21a22a6b4def59deeeedf4630c689cc5ff98a7',
    build: '4113e701f25683dcb621bd991009a583604df1d3',
    reviewReceipt: {
      schemaVersion: 1,
      featureId: 'inbox',
      capturedAt: '2026-07-14T05:04:47.000Z',
      reviewedAt: '2026-07-14T05:05:00.000Z',
      reviewer: 'OpenAI Codex manual visual review',
      appBuildCommit: '4113e701f25683dcb621bd991009a583604df1d3',
      artifactSha256: 'c71032e14792e0640878f1d8da21a22a6b4def59deeeedf4630c689cc5ff98a7',
      runtimeBuildIdentity: {
        origin: MARKETING_CAPTURE_RUNTIME_ORIGIN,
        identitySelector: MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR,
        observedCommit: '4113e701f25683dcb621bd991009a583604df1d3',
        verifiedAt: '2026-07-14T04:45:00.000Z',
      },
      browser: 'Google Chrome',
      browserWasVisible: true,
      interactionsWereManual: true,
      scriptedBrowserCaptureWasUsed: false,
      pageZoomPercent: 100,
      viewportMode: 'Responsive',
      devicePixelRatio: 1,
      captureCommand: 'Capture screenshot',
      fullSizeScreenshotWasUsed: false,
      originalPngReviewed: true,
      postCaptureTransformsApplied: false,
    },
  },
  'book-the-client': {
    status: 'approved',
    route: '/admin/vendors/contracts/67c100000000000000000001',
    focal: 'main',
    interaction: 'Open Payments and wait for Payment Milestones without changing the contract.',
    width: 1440,
    height: 900,
    checksum: '097e8f8ea4f8dd65e91da45e111cd07ae16b0c540265472428af4c9ead59e9cd',
    build: '4113e701f25683dcb621bd991009a583604df1d3',
    reviewReceipt: {
      schemaVersion: 1,
      featureId: 'book-the-client',
      capturedAt: '2026-07-14T05:07:46.000Z',
      reviewedAt: '2026-07-14T05:07:58.000Z',
      reviewer: 'OpenAI Codex manual visual review',
      appBuildCommit: '4113e701f25683dcb621bd991009a583604df1d3',
      artifactSha256: '097e8f8ea4f8dd65e91da45e111cd07ae16b0c540265472428af4c9ead59e9cd',
      runtimeBuildIdentity: {
        origin: MARKETING_CAPTURE_RUNTIME_ORIGIN,
        identitySelector: MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR,
        observedCommit: '4113e701f25683dcb621bd991009a583604df1d3',
        verifiedAt: '2026-07-14T04:45:00.000Z',
      },
      browser: 'Google Chrome',
      browserWasVisible: true,
      interactionsWereManual: true,
      scriptedBrowserCaptureWasUsed: false,
      pageZoomPercent: 100,
      viewportMode: 'Responsive',
      devicePixelRatio: 1,
      captureCommand: 'Capture screenshot',
      fullSizeScreenshotWasUsed: false,
      originalPngReviewed: true,
      postCaptureTransformsApplied: false,
    },
  },
  'payments-autopilot': {
    status: 'approved',
    route: '/admin/money',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: 'f95c4aa3f1d89b23355abade0d07a5e493e3d33906d4abe78edc139387b38210',
    build: '4113e701f25683dcb621bd991009a583604df1d3',
    reviewReceipt: {
      schemaVersion: 1,
      featureId: 'payments-autopilot',
      capturedAt: '2026-07-14T05:09:49.000Z',
      reviewedAt: '2026-07-14T05:10:01.000Z',
      reviewer: 'OpenAI Codex manual visual review',
      appBuildCommit: '4113e701f25683dcb621bd991009a583604df1d3',
      artifactSha256: 'f95c4aa3f1d89b23355abade0d07a5e493e3d33906d4abe78edc139387b38210',
      runtimeBuildIdentity: {
        origin: MARKETING_CAPTURE_RUNTIME_ORIGIN,
        identitySelector: MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR,
        observedCommit: '4113e701f25683dcb621bd991009a583604df1d3',
        verifiedAt: '2026-07-14T04:45:00.000Z',
      },
      browser: 'Google Chrome',
      browserWasVisible: true,
      interactionsWereManual: true,
      scriptedBrowserCaptureWasUsed: false,
      pageZoomPercent: 100,
      viewportMode: 'Responsive',
      devicePixelRatio: 1,
      captureCommand: 'Capture screenshot',
      fullSizeScreenshotWasUsed: false,
      originalPngReviewed: true,
      postCaptureTransformsApplied: false,
    },
  },
  budget: {
    status: 'approved',
    route: '/admin/budget?wedding_id=wedding_marketing_capture_sofia_daniel',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: 'e02efbc75b891df55767ff2924c5b22cde2fe50b8bb539e94611e814a949fb86',
    build: '4113e701f25683dcb621bd991009a583604df1d3',
    reviewReceipt: {
      schemaVersion: 1,
      featureId: 'budget',
      capturedAt: '2026-07-14T05:11:28.000Z',
      reviewedAt: '2026-07-14T05:11:40.000Z',
      reviewer: 'OpenAI Codex manual visual review',
      appBuildCommit: '4113e701f25683dcb621bd991009a583604df1d3',
      artifactSha256: 'e02efbc75b891df55767ff2924c5b22cde2fe50b8bb539e94611e814a949fb86',
      runtimeBuildIdentity: {
        origin: MARKETING_CAPTURE_RUNTIME_ORIGIN,
        identitySelector: MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR,
        observedCommit: '4113e701f25683dcb621bd991009a583604df1d3',
        verifiedAt: '2026-07-14T04:45:00.000Z',
      },
      browser: 'Google Chrome',
      browserWasVisible: true,
      interactionsWereManual: true,
      scriptedBrowserCaptureWasUsed: false,
      pageZoomPercent: 100,
      viewportMode: 'Responsive',
      devicePixelRatio: 1,
      captureCommand: 'Capture screenshot',
      fullSizeScreenshotWasUsed: false,
      originalPngReviewed: true,
      postCaptureTransformsApplied: false,
    },
  },
  'vendor-network': {
    status: 'approved',
    route: '/admin/vendors',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: 'ea63aa33dfe203547563d40315d80b87e382b541027925199cb9dc1fe0898193',
    build: '4113e701f25683dcb621bd991009a583604df1d3',
    reviewReceipt: {
      schemaVersion: 1,
      featureId: 'vendor-network',
      capturedAt: '2026-07-14T05:13:06.000Z',
      reviewedAt: '2026-07-14T05:13:18.000Z',
      reviewer: 'OpenAI Codex manual visual review',
      appBuildCommit: '4113e701f25683dcb621bd991009a583604df1d3',
      artifactSha256: 'ea63aa33dfe203547563d40315d80b87e382b541027925199cb9dc1fe0898193',
      runtimeBuildIdentity: {
        origin: MARKETING_CAPTURE_RUNTIME_ORIGIN,
        identitySelector: MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR,
        observedCommit: '4113e701f25683dcb621bd991009a583604df1d3',
        verifiedAt: '2026-07-14T04:45:00.000Z',
      },
      browser: 'Google Chrome',
      browserWasVisible: true,
      interactionsWereManual: true,
      scriptedBrowserCaptureWasUsed: false,
      pageZoomPercent: 100,
      viewportMode: 'Responsive',
      devicePixelRatio: 1,
      captureCommand: 'Capture screenshot',
      fullSizeScreenshotWasUsed: false,
      originalPngReviewed: true,
      postCaptureTransformsApplied: false,
    },
  },
  'knowledge-base': {
    status: 'approved',
    route: '/admin/support?tab=knowledge_base',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '7fc6f8789bed6063f7c0ba3a69246b291fc27d57dbe0c3d9d011ad0113809d98',
    build: '4113e701f25683dcb621bd991009a583604df1d3',
    reviewReceipt: {
      schemaVersion: 1,
      featureId: 'knowledge-base',
      capturedAt: '2026-07-14T05:14:47.000Z',
      reviewedAt: '2026-07-14T05:15:00.000Z',
      reviewer: 'OpenAI Codex manual visual review',
      appBuildCommit: '4113e701f25683dcb621bd991009a583604df1d3',
      artifactSha256: '7fc6f8789bed6063f7c0ba3a69246b291fc27d57dbe0c3d9d011ad0113809d98',
      runtimeBuildIdentity: {
        origin: MARKETING_CAPTURE_RUNTIME_ORIGIN,
        identitySelector: MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR,
        observedCommit: '4113e701f25683dcb621bd991009a583604df1d3',
        verifiedAt: '2026-07-14T04:45:00.000Z',
      },
      browser: 'Google Chrome',
      browserWasVisible: true,
      interactionsWereManual: true,
      scriptedBrowserCaptureWasUsed: false,
      pageZoomPercent: 100,
      viewportMode: 'Responsive',
      devicePixelRatio: 1,
      captureCommand: 'Capture screenshot',
      fullSizeScreenshotWasUsed: false,
      originalPngReviewed: true,
      postCaptureTransformsApplied: false,
    },
  },
  forms: {
    status: 'approved',
    route: '/admin/forms/form_marketing_capture_couple_intake/edit',
    focal: 'main',
    interaction: 'Open the seeded Couple Intake Questionnaire edit builder without changing any fields.',
    width: 1440,
    height: 900,
    checksum: '8f491fe41658d6c871e8d8f7198c3d5a0f8dc2c3436f97db4be05ec09a0f9aa2',
    build: '4113e701f25683dcb621bd991009a583604df1d3',
    reviewReceipt: {
      schemaVersion: 1,
      featureId: 'forms',
      capturedAt: '2026-07-14T10:52:08.000Z',
      reviewedAt: '2026-07-14T10:52:22.000Z',
      reviewer: 'OpenAI Codex manual visual review',
      appBuildCommit: '4113e701f25683dcb621bd991009a583604df1d3',
      artifactSha256: '8f491fe41658d6c871e8d8f7198c3d5a0f8dc2c3436f97db4be05ec09a0f9aa2',
      runtimeBuildIdentity: {
        origin: MARKETING_CAPTURE_RUNTIME_ORIGIN,
        identitySelector: MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR,
        observedCommit: '4113e701f25683dcb621bd991009a583604df1d3',
        verifiedAt: '2026-07-14T04:45:00.000Z',
      },
      browser: 'Google Chrome',
      browserWasVisible: true,
      interactionsWereManual: true,
      scriptedBrowserCaptureWasUsed: false,
      pageZoomPercent: 100,
      viewportMode: 'Responsive',
      devicePixelRatio: 1,
      captureCommand: 'Capture screenshot',
      fullSizeScreenshotWasUsed: false,
      originalPngReviewed: true,
      postCaptureTransformsApplied: false,
    },
  },
  team: {
    status: 'approved',
    route: '/admin/planner/team',
    focal: 'main',
    width: 1440,
    height: 900,
    checksum: '589b14aaf818de332fa94031c1e46872105ff59d6af701cfe367371164b631bf',
    build: '4113e701f25683dcb621bd991009a583604df1d3',
    reviewReceipt: {
      schemaVersion: 1,
      featureId: 'team',
      capturedAt: '2026-07-14T10:53:47.000Z',
      reviewedAt: '2026-07-14T10:54:03.000Z',
      reviewer: 'OpenAI Codex manual visual review',
      appBuildCommit: '4113e701f25683dcb621bd991009a583604df1d3',
      artifactSha256: '589b14aaf818de332fa94031c1e46872105ff59d6af701cfe367371164b631bf',
      runtimeBuildIdentity: {
        origin: MARKETING_CAPTURE_RUNTIME_ORIGIN,
        identitySelector: MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR,
        observedCommit: '4113e701f25683dcb621bd991009a583604df1d3',
        verifiedAt: '2026-07-14T04:45:00.000Z',
      },
      browser: 'Google Chrome',
      browserWasVisible: true,
      interactionsWereManual: true,
      scriptedBrowserCaptureWasUsed: false,
      pageZoomPercent: 100,
      viewportMode: 'Responsive',
      devicePixelRatio: 1,
      captureCommand: 'Capture screenshot',
      fullSizeScreenshotWasUsed: false,
      originalPngReviewed: true,
      postCaptureTransformsApplied: false,
    },
  },
} as const satisfies Record<string, CaptureSpec>;

const CAPTURE_SCENE_CONTEXT = {
  dashboard: { session: 'planner', expectedText: 'Welcome back, Marigold & Co. Weddings!' },
  'real-time': { session: 'planner', expectedText: 'The Glasshouse at Riverbend' },
  'couple-portal': { session: 'couple', expectedText: '24 guests added so far' },
  'wedding-website': { session: 'public', expectedText: 'The Glasshouse at Riverbend' },
  'wedding-configuration': { session: 'planner', expectedText: 'RSVP Configuration' },
  'gallery-management': { session: 'planner', expectedText: 'Garden terrace portrait' },
  'guest-management': { session: 'planner', expectedText: 'Guest Management' },
  'seating-orchestrator': { session: 'planner', expectedText: '70%' },
  'guest-memories': { session: 'couple', expectedText: 'Review queue' },
  inbox: { session: 'planner', expectedText: 'Sofia & Daniel' },
  'book-the-client': { session: 'planner', expectedText: 'Payment Milestones' },
  'payments-autopilot': { session: 'planner', expectedText: 'Money' },
  budget: { session: 'planner', expectedText: '$82,500' },
  'vendor-network': { session: 'planner', expectedText: 'Vendor Management' },
  'knowledge-base': { session: 'planner', expectedText: 'Knowledge Base' },
  forms: { session: 'planner', expectedText: 'Couple Intake Questionnaire' },
  team: { session: 'planner', expectedText: 'Team Management' },
} as const satisfies Record<
  keyof typeof CAPTURE_SPECS,
  { session: MarketingCaptureSession; expectedText: string }
>;

function parseCanonicalIsoDateTime(value: string): number | null {
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed) || new Date(parsed).toISOString() !== value) {
    return null;
  }
  return parsed;
}

/**
 * Browser-safe publication gate for marketing proof images.
 *
 * This deliberately repeats the capture receipt's immutable attestations at
 * render time. A status flip alone must never make an unreviewed, stale, or
 * scripted artifact public.
 */
export function isMarketingCaptureAssetApproved(
  asset: MarketingCaptureAsset,
): boolean {
  const receipt = asset.reviewReceipt;
  if (
    asset.status !== 'approved'
    || asset.captureMethod !== 'manual-visible-browser'
    || asset.framing !== 'full-window'
    || asset.width !== MARKETING_CAPTURE_VIEWPORT.width
    || asset.height !== MARKETING_CAPTURE_VIEWPORT.height
    || asset.captureBounds.x !== 0
    || asset.captureBounds.y !== 0
    || asset.captureBounds.width !== asset.width
    || asset.captureBounds.height !== asset.height
    || asset.render.frameAspectRatio !== '16:10'
    || asset.render.fit !== 'contain'
    || asset.render.zoom !== false
    || !/^[0-9a-f]{40}$/.test(asset.build)
    || !/^[0-9a-f]{64}$/.test(asset.checksum)
    || !receipt
  ) {
    return false;
  }

  const runtimeBuildIdentity = receipt.runtimeBuildIdentity;
  if (
    !runtimeBuildIdentity
    || typeof receipt.capturedAt !== 'string'
    || typeof receipt.reviewedAt !== 'string'
    || typeof receipt.reviewer !== 'string'
    || typeof runtimeBuildIdentity.verifiedAt !== 'string'
  ) {
    return false;
  }

  const capturedAt = parseCanonicalIsoDateTime(receipt.capturedAt);
  const reviewedAt = parseCanonicalIsoDateTime(receipt.reviewedAt);
  const runtimeVerifiedAt = parseCanonicalIsoDateTime(
    runtimeBuildIdentity.verifiedAt,
  );
  const runtimeWasVerifiedNearCapture =
    runtimeVerifiedAt !== null
    && capturedAt !== null
    && runtimeVerifiedAt <= capturedAt
    && capturedAt - runtimeVerifiedAt <= 24 * 60 * 60 * 1000;

  return (
    receipt.schemaVersion === 1
    && receipt.featureId === asset.featureId
    && receipt.reviewer.trim().length > 0
    && receipt.appBuildCommit === asset.build
    && receipt.artifactSha256 === asset.checksum
    && runtimeBuildIdentity.origin === MARKETING_CAPTURE_RUNTIME_ORIGIN
    && runtimeBuildIdentity.identitySelector
      === MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR
    && runtimeBuildIdentity.observedCommit === asset.build
    && runtimeWasVerifiedNearCapture
    && capturedAt !== null
    && reviewedAt !== null
    && capturedAt <= reviewedAt
    && receipt.browser === 'Google Chrome'
    && receipt.browserWasVisible === true
    && receipt.interactionsWereManual === true
    && receipt.scriptedBrowserCaptureWasUsed === false
    && receipt.pageZoomPercent === 100
    && receipt.viewportMode === 'Responsive'
    && receipt.devicePixelRatio === 1
    && receipt.captureCommand === 'Capture screenshot'
    && receipt.fullSizeScreenshotWasUsed === false
    && receipt.originalPngReviewed === true
    && receipt.postCaptureTransformsApplied === false
  );
}

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
      captureMethod: 'manual-visible-browser',
      reviewReceipt: spec.reviewReceipt ?? null,
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
    featureId: entry.featureId,
    status: entry.status,
    build: entry.build,
    render: entry.renders[target],
  };
}
