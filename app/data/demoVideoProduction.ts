import { DEMO_VIDEO_PLAYLIST, type DemoVideo } from './demoVideos';

export type DemoVideoCaptureSurface =
  | 'planner-admin'
  | 'couple-portal'
  | 'public-site'
  | 'public-form'
  | 'guest-token'
  | 'client-payment-token'
  | 'vendor-token'
  | 'payment-link';

export type DemoVideoExportFormat = 'web-16x9' | 'social-9x16';

export type DemoVideoExportTarget = {
  format: DemoVideoExportFormat;
  compositionId: 'DemoVideo16x9' | 'DemoVideo9x16';
  width: number;
  height: number;
  fps: number;
  assetPath: string;
  thumbnailPath: string;
};

export type DemoVideoProductionRequirement = {
  demoId: DemoVideo['id'];
  captureSurfaces: readonly DemoVideoCaptureSurface[];
  routeParameters: readonly string[];
  sideEffectGuards: readonly string[];
  rawRecordingPath: string;
  narrationPath: string;
  captureReceiptPath: string;
  renderInputPath: string;
  renderNarrationInputPath: string;
  captionPath: string;
  transcriptPath: string;
  playbackApprovalPath: string;
  exportTargets: readonly DemoVideoExportTarget[];
};

const PUBLIC_DEMO_VIDEO_ROOT = '/demo-videos';
const STATIC_DEMO_VIDEO_ROOT = 'demo-videos';
const DEFAULT_FPS = 30;

const SURFACE_SESSION_COPY: Record<DemoVideoCaptureSurface, string> = {
  'planner-admin': 'Requires a seeded planner/admin browser session state.',
  'couple-portal': 'Requires a seeded couple browser session state.',
  'public-site': 'No authenticated session required, but slug placeholders must resolve to seeded public weddings.',
  'public-form': 'No authenticated session required, but public forms must use disposable fixture submissions.',
  'guest-token': 'Requires a disposable guest upload token and prepared demo media only.',
  'client-payment-token': 'Requires a seeded client payment portal token and read-only payment state.',
  'vendor-token': 'Requires a disposable vendor or contract token with no real counterparty data.',
  'payment-link': 'Requires Stripe test mode and must stop before any irreversible financial confirmation.',
};

function unique<T>(items: readonly T[]): T[] {
  return Array.from(new Set(items));
}

export function getRouteParameters(routes: readonly string[]): string[] {
  return unique(
    routes.flatMap((route) => {
      const matches = route.matchAll(/\[([^\]]+)\]/g);
      return Array.from(matches, (match) => match[1]).filter(Boolean);
    }),
  ).sort();
}

export function getCaptureSurfaces(routes: readonly string[]): DemoVideoCaptureSurface[] {
  return unique(
    routes.map((route): DemoVideoCaptureSurface => {
      if (route.startsWith('/admin')) return 'planner-admin';
      if (route.startsWith('/couple')) return 'couple-portal';
      if (route.startsWith('/portal/ads') || route.startsWith('/vendor-contract') || route.startsWith('/contracts')) {
        return 'vendor-token';
      }
      if (route.startsWith('/portal')) return 'client-payment-token';
      if (route.startsWith('/pay')) return 'payment-link';
      if (route.includes('/upload/')) return 'guest-token';
      if (route.startsWith('/forms/')) return 'public-form';
      return 'public-site';
    }),
  ).sort();
}

export function getSideEffectGuards(
  routes: readonly string[],
  surfaces: readonly DemoVideoCaptureSurface[],
): string[] {
  const guards = surfaces.map((surface) => SURFACE_SESSION_COPY[surface]);

  if (routes.some((route) => route.includes('/communications'))) {
    guards.push('Use local/test messaging transport only; do not send real SMS or email.');
  }

  if (routes.some((route) => route.startsWith('/admin/vendors/contracts'))) {
    guards.push('Use a seeded planner-owned fictional contract; do not request or imply a real legal signature.');
  }

  if (routes.some((route) => route.startsWith('/contracts') || route.startsWith('/vendor-contract'))) {
    guards.push('Use demo contract tokens only; do not request a real legal signature.');
  }

  if (routes.some((route) => route.includes('/budget'))) {
    guards.push('Use seeded read-only finance records; do not record or initiate a payment.');
  }

  if (routes.some((route) => route.includes('/pay'))) {
    guards.push('Use Stripe test-mode payment states only.');
  }

  if (surfaces.includes('client-payment-token')) {
    guards.push('Use the seeded read-only client payment portal; do not open payment-method or transaction controls.');
  }

  if (routes.some((route) => route.includes('/upload/'))) {
    guards.push('Use prepared non-private demo media; do not expose local Finder paths or personal filenames.');
  }

  return unique(guards);
}

function buildExportTargets(demoId: string): DemoVideoExportTarget[] {
  return [
    {
      format: 'web-16x9',
      compositionId: 'DemoVideo16x9',
      width: 1920,
      height: 1080,
      fps: DEFAULT_FPS,
      assetPath: `${PUBLIC_DEMO_VIDEO_ROOT}/exports/${demoId}-16x9.mp4`,
      thumbnailPath: `${PUBLIC_DEMO_VIDEO_ROOT}/thumbnails/${demoId}-16x9.png`,
    },
  ];
}

export function getDemoVideoProductionRequirement(demo: DemoVideo): DemoVideoProductionRequirement {
  const captureSurfaces = getCaptureSurfaces(demo.routePlan);

  return {
    demoId: demo.id,
    captureSurfaces,
    routeParameters: getRouteParameters(demo.routePlan),
    sideEffectGuards: getSideEffectGuards(demo.routePlan, captureSurfaces),
    rawRecordingPath: `output/demo-videos/raw/${demo.id}.mp4`,
    narrationPath: `output/demo-videos/narration/${demo.id}.m4a`,
    captureReceiptPath: `output/demo-videos/receipts/${demo.id}.json`,
    renderInputPath: `${STATIC_DEMO_VIDEO_ROOT}/.render-input/${demo.id}.mp4`,
    renderNarrationInputPath: `${STATIC_DEMO_VIDEO_ROOT}/.render-input/${demo.id}.m4a`,
    captionPath: `${STATIC_DEMO_VIDEO_ROOT}/captions/${demo.id}.vtt`,
    transcriptPath: `${STATIC_DEMO_VIDEO_ROOT}/transcripts/${demo.id}.md`,
    playbackApprovalPath: `output/demo-videos/playback-approvals/${demo.id}.json`,
    exportTargets: buildExportTargets(demo.id),
  };
}

export const DEMO_VIDEO_PRODUCTION_REQUIREMENTS: readonly DemoVideoProductionRequirement[] =
  DEMO_VIDEO_PLAYLIST.map(getDemoVideoProductionRequirement);

export function getDemoVideoProductionRequirementById(
  demoId: string,
): DemoVideoProductionRequirement | undefined {
  return DEMO_VIDEO_PRODUCTION_REQUIREMENTS.find((requirement) => requirement.demoId === demoId);
}

export function getDemoVideoById(demoId: string): DemoVideo | undefined {
  return DEMO_VIDEO_PLAYLIST.find((demo) => demo.id === demoId);
}

export function getDemoVideoExportTarget(
  requirement: DemoVideoProductionRequirement,
  format: DemoVideoExportFormat,
): DemoVideoExportTarget | undefined {
  return requirement.exportTargets.find((target) => target.format === format);
}

export function buildDemoVideoTranscript(demo: DemoVideo): string {
  const lines = [
    `# ${demo.title}`,
    '',
    `Audience: ${demo.audience}`,
    `Target duration: ${demo.durationSeconds} seconds`,
    '',
    '## Script',
    '',
    ...demo.script.flatMap((step) => [
      `### ${step.timestamp}`,
      '',
      `Action: ${step.action}`,
      '',
      step.voiceover,
      '',
    ]),
  ];

  return `${lines.join('\n').trim()}\n`;
}
