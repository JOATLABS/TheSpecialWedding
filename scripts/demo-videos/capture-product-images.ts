import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  chromium,
  type BrowserContext,
  type BrowserContextOptions,
  type Page,
} from 'playwright';

import { parseCliArgs, resolveFromRepo } from './cli';
import { scanCaptureArtifact, type CaptureArtifactSafetyReceipt } from './media-safety';
import { assertPublicSafeStorageState } from './public-safe-storage';
import {
  createCaptureReadinessMonitor,
  installCaptureStability,
  waitForCaptureReady,
} from './wait-for-capture-ready';

export const PRODUCT_IMAGE_FEATURE_IDS = [
  'dashboard',
  'real-time',
  'couple-portal',
  'wedding-website',
  'configuration',
  'gallery',
  'guests',
  'seating',
  'guest-memories',
  'communications',
  'contracts',
  'payments',
  'budget',
  'vendors',
  'knowledge-base',
  'forms',
  'team',
] as const;

export type ProductImageFeatureId = (typeof PRODUCT_IMAGE_FEATURE_IDS)[number];
export type ProductImageTargetName = 'hero' | 'homepage' | 'features';
type CaptureSession = 'planner' | 'couple' | 'public';

export const MARKETING_CAPTURE_FEATURE_IDS = [
  'dashboard',
  'real-time',
  'couple-portal',
  'wedding-website',
  'wedding-configuration',
  'gallery-management',
  'guest-management',
  'seating-orchestrator',
  'guest-memories',
  'inbox',
  'book-the-client',
  'payments-autopilot',
  'budget',
  'vendor-network',
  'knowledge-base',
  'forms',
  'team',
] as const;

export type MarketingCaptureFeatureId = (typeof MARKETING_CAPTURE_FEATURE_IDS)[number];

type ProductImageCaptureSpec = {
  captureId: ProductImageFeatureId;
  featureId: MarketingCaptureFeatureId;
  route: string;
  session: CaptureSession;
  expectedText?: string;
  focusSelectors: readonly string[];
  prepare?: { role: 'button'; name: string; exact: boolean };
};

type CaptureFixtures = {
  primaryWeddingId: string;
  primarySlug: string;
  guestMemoriesUploadToken: string;
  vendorContractId: string;
};

type ProductImageTarget = {
  name: ProductImageTargetName;
  width: number;
  height: number;
};

type ScreenshotClip = { x: number; y: number; width: number; height: number };

type ProductImageArtifactReceipt = {
  target: ProductImageTargetName;
  relativePath: string;
  width: number;
  height: number;
  safety: CaptureArtifactSafetyReceipt;
};

type ProductImageFeatureReceipt = {
  captureId: ProductImageFeatureId;
  featureId: MarketingCaptureFeatureId;
  routeTemplate: string;
  checkpoint: 'stable-product-surface';
  readinessFrameSha256: string;
  artifacts: ProductImageArtifactReceipt[];
};

type ProductImageCaptureReceipt = {
  generatedAt: string;
  gitSha: string;
  viewport: { width: number; height: number; deviceScaleFactor: number };
  approvalStatus: 'review-required';
  features: ProductImageFeatureReceipt[];
};

const VIEWPORT = { width: 1920, height: 1080, deviceScaleFactor: 1 } as const;

export const PRODUCT_IMAGE_TARGETS: readonly ProductImageTarget[] = [
  { name: 'hero', width: 1440, height: 900 },
  { name: 'homepage', width: 1600, height: 900 },
  { name: 'features', width: 1280, height: 800 },
] as const;

export const PRODUCT_IMAGE_CAPTURE_SPECS: readonly ProductImageCaptureSpec[] = [
  { captureId: 'dashboard', featureId: 'dashboard', route: '/admin/planner', session: 'planner', expectedText: 'Your Weddings', focusSelectors: ['main', 'body'] },
  { captureId: 'real-time', featureId: 'real-time', route: '/admin/weddings/[id]', session: 'planner', expectedText: 'Event Details', focusSelectors: ['main', 'body'], prepare: { role: 'button', name: 'events', exact: false } },
  { captureId: 'couple-portal', featureId: 'couple-portal', route: '/couple/dashboard', session: 'couple', expectedText: 'Dashboard', focusSelectors: ['main', 'body'] },
  { captureId: 'wedding-website', featureId: 'wedding-website', route: '/[slug]', session: 'public', focusSelectors: ['main', 'body'] },
  { captureId: 'configuration', featureId: 'wedding-configuration', route: '/admin/weddings/[id]', session: 'planner', expectedText: 'Event Details', focusSelectors: ['main', 'body'] },
  { captureId: 'gallery', featureId: 'gallery-management', route: '/admin/gallery/upload', session: 'planner', expectedText: 'Gallery Management', focusSelectors: ['main', 'body'] },
  { captureId: 'guests', featureId: 'guest-management', route: '/admin/guests', session: 'planner', expectedText: 'Guest Management', focusSelectors: ['main', 'body'] },
  { captureId: 'seating', featureId: 'seating-orchestrator', route: '/admin/weddings/[id]/seating', session: 'planner', expectedText: 'Seating Arrangement', focusSelectors: ['main', 'body'] },
  { captureId: 'guest-memories', featureId: 'guest-memories', route: '/couple/dashboard', session: 'couple', expectedText: 'Review queue', focusSelectors: ['main', 'body'], prepare: { role: 'button', name: 'Memories', exact: false } },
  { captureId: 'communications', featureId: 'inbox', route: '/admin/communications/inbox', session: 'planner', expectedText: 'Inbox', focusSelectors: ['main', 'body'] },
  { captureId: 'contracts', featureId: 'book-the-client', route: '/admin/vendors/contracts/[contractId]', session: 'planner', expectedText: 'Contract Information', focusSelectors: ['main', 'body'] },
  { captureId: 'payments', featureId: 'payments-autopilot', route: '/admin/money', session: 'planner', expectedText: 'Money', focusSelectors: ['main', 'body'] },
  { captureId: 'budget', featureId: 'budget', route: '/admin/budget', session: 'planner', expectedText: 'Budget Management', focusSelectors: ['main', 'body'] },
  { captureId: 'vendors', featureId: 'vendor-network', route: '/admin/vendors', session: 'planner', expectedText: 'Vendor Management', focusSelectors: ['main', 'body'] },
  { captureId: 'knowledge-base', featureId: 'knowledge-base', route: '/admin/support?tab=knowledge_base', session: 'planner', expectedText: 'Knowledge Base', focusSelectors: ['main', 'body'] },
  { captureId: 'forms', featureId: 'forms', route: '/admin/forms', session: 'planner', expectedText: 'Forms library', focusSelectors: ['main', 'body'] },
  { captureId: 'team', featureId: 'team', route: '/admin/planner/team', session: 'planner', expectedText: 'Team Management', focusSelectors: ['main', 'body'] },
] as const;

function readFixtures(filePath: string): CaptureFixtures {
  if (!fs.existsSync(filePath)) {
    throw new Error(`Capture fixtures file does not exist: ${filePath}. Run npm run demo:seed first.`);
  }
  return JSON.parse(fs.readFileSync(filePath, 'utf8')) as CaptureFixtures;
}

function resolveRoute(route: string, fixtures: CaptureFixtures): string {
  const routeParams: Record<string, string> = {
    id: fixtures.primaryWeddingId,
    slug: fixtures.primarySlug,
    uploadToken: fixtures.guestMemoriesUploadToken,
    contractId: fixtures.vendorContractId,
  };

  return route.replace(/\[([^\]]+)\]/g, (_, key: string) => {
    const value = routeParams[key];
    if (!value) throw new Error(`Product image route "${route}" requires fixture "${key}".`);
    return encodeURIComponent(value);
  });
}

function currentGitSha(): string {
  const result = spawnSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8', cwd: resolveFromRepo() });
  if (result.status !== 0) throw new Error('Cannot identify the git build used for product image capture.');
  return result.stdout.trim();
}

function assertLocalCaptureOrigin(baseUrl: string): void {
  const parsed = new URL(baseUrl);
  const localHostname = parsed.hostname === 'localhost'
    || parsed.hostname === '127.0.0.1'
    || parsed.hostname === '::1';
  if (!localHostname || !['http:', 'https:'].includes(parsed.protocol)) {
    throw new Error('Product image capture is restricted to the isolated local harness.');
  }
}

async function findFocusBounds(page: Page, selectors: readonly string[]) {
  for (const selector of selectors) {
    const locator = page.locator(selector).first();
    if (!(await locator.isVisible().catch(() => false))) continue;
    const box = await locator.boundingBox();
    if (box && box.width > 0 && box.height > 0) return box;
  }
  throw new Error('No declared product-image focus locator is visible.');
}

function clipAroundFocus(
  focus: { x: number; y: number; width: number; height: number },
  target: ProductImageTarget,
): ScreenshotClip {
  const centerX = focus.x + focus.width / 2;
  const desiredY = Math.max(0, focus.y);
  const x = Math.max(0, Math.min(VIEWPORT.width - target.width, centerX - target.width / 2));
  const y = Math.max(0, Math.min(VIEWPORT.height - target.height, desiredY));
  return { x: Math.round(x), y: Math.round(y), width: target.width, height: target.height };
}

async function visibleTextInsideClip(page: Page, clip: ScreenshotClip): Promise<string> {
  return page.evaluate(`(() => {
    const captureClip = ${JSON.stringify(clip)};
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const visibleText = [];
    let node = walker.nextNode();

    while (node) {
      const value = node.textContent?.replace(/\\s+/g, ' ').trim();
      const element = node.parentElement;
      if (value && element) {
        const style = window.getComputedStyle(element);
        const box = element.getBoundingClientRect();
        const intersects = box.right > captureClip.x
          && box.left < captureClip.x + captureClip.width
          && box.bottom > captureClip.y
          && box.top < captureClip.y + captureClip.height;
        if (intersects && style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0) {
          visibleText.push(value);
        }
      }
      node = walker.nextNode();
    }

    return visibleText.join('\\n');
  })()`);
}

function contextOptionsForSession(
  session: CaptureSession,
  plannerStorageState: string | undefined,
  coupleStorageState: string | undefined,
): BrowserContextOptions {
  const options: BrowserContextOptions = {
    viewport: VIEWPORT,
    deviceScaleFactor: VIEWPORT.deviceScaleFactor,
    locale: 'en-US',
    timezoneId: 'America/Chicago',
    colorScheme: 'light',
    reducedMotion: 'reduce',
  };

  const state = session === 'planner' ? plannerStorageState : session === 'couple' ? coupleStorageState : undefined;
  if (session !== 'public' && !state) {
    throw new Error(`${session} product captures require a dedicated --${session}-storage-state file.`);
  }
  if (state) options.storageState = path.resolve(state);
  return options;
}

function writeCaptureReceipt(filePath: string, receipt: ProductImageCaptureReceipt): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(receipt, null, 2)}\n`);
}

async function captureFeature(
  spec: ProductImageCaptureSpec,
  options: {
    baseUrl: string;
    fixtures: CaptureFixtures;
    outputRoot: string;
    receiptPath: string;
    receipt: ProductImageCaptureReceipt;
    plannerStorageState?: string;
    coupleStorageState?: string;
    ocrExecutable?: string;
  },
): Promise<void> {
  const browserOptions = contextOptionsForSession(
    spec.session,
    options.plannerStorageState,
    options.coupleStorageState,
  );
  const browser = await chromium.launch({ headless: true });
  let context: BrowserContext | undefined;
  let page: Page | undefined;
  let monitor: ReturnType<typeof createCaptureReadinessMonitor> | undefined;

  try {
    context = await browser.newContext(browserOptions);
    page = await context.newPage();
    monitor = createCaptureReadinessMonitor(page);
    await installCaptureStability(page);
    const route = resolveRoute(spec.route, options.fixtures);
    await page.goto(new URL(route, options.baseUrl).toString(), {
      waitUntil: 'domcontentloaded',
      timeout: 60_000,
    });
    let readiness = await waitForCaptureReady(page, { monitor, timeoutMs: 60_000 });
    if (spec.prepare) {
      await page.getByRole(spec.prepare.role, {
        name: spec.prepare.name,
        exact: spec.prepare.exact,
      }).click();
      readiness = await waitForCaptureReady(page, { monitor, timeoutMs: 60_000 });
    }
    const bodyText = await page.locator('body').innerText();
    if (spec.expectedText && !bodyText.includes(spec.expectedText)) {
      throw new Error(`Product surface ${spec.captureId} did not reach its declared content checkpoint.`);
    }

    const focus = await findFocusBounds(page, spec.focusSelectors);
    const featureReceipt: ProductImageFeatureReceipt = {
      captureId: spec.captureId,
      featureId: spec.featureId,
      routeTemplate: spec.route,
      checkpoint: 'stable-product-surface',
      readinessFrameSha256: readiness.frameSha256,
      artifacts: [],
    };
    options.receipt.features.push(featureReceipt);

    for (const target of PRODUCT_IMAGE_TARGETS) {
      const clip = clipAroundFocus(focus, target);
      const artifactPath = path.join(options.outputRoot, spec.featureId, `${target.name}.png`);
      fs.mkdirSync(path.dirname(artifactPath), { recursive: true });
      await page.screenshot({
        path: artifactPath,
        type: 'png',
        animations: 'disabled',
        caret: 'hide',
        clip,
      });

      const safety = scanCaptureArtifact(artifactPath, {
        visibleText: await visibleTextInsideClip(page, clip),
        ocrExecutable: options.ocrExecutable,
      });
      featureReceipt.artifacts.push({
        target: target.name,
        relativePath: path.relative(resolveFromRepo(), artifactPath),
        width: target.width,
        height: target.height,
        safety,
      });
      writeCaptureReceipt(options.receiptPath, options.receipt);

      if (!safety.safe) {
        throw new Error(
          `Product image ${spec.featureId}/${target.name} failed safety scan (${safety.findings.map((item) => item.code).join(', ')}).`,
        );
      }
    }
  } finally {
    monitor?.dispose();
    await page?.close().catch(() => undefined);
    await context?.close().catch(() => undefined);
    await browser.close().catch(() => undefined);
  }
}

export async function captureProductImages(argv: readonly string[]): Promise<ProductImageCaptureReceipt> {
  const args = parseCliArgs(argv);
  const baseUrl = args.values.get('base-url') ?? 'http://127.0.0.1:3100';
  const fixturesPath = args.values.get('fixtures')
    ?? resolveFromRepo('output', 'demo-videos', 'capture-fixtures.json');
  const outputRoot = args.values.get('output-root')
    ?? resolveFromRepo('output', 'demo-videos', 'product-images', 'review');
  const receiptPath = args.values.get('receipt')
    ?? resolveFromRepo('output', 'demo-videos', 'product-images', 'capture-receipt.json');
  const plannerStorageState = args.values.get('planner-storage-state') ?? args.values.get('storage-state');
  const coupleStorageState = args.values.get('couple-storage-state');
  const requestedFeatures = args.repeatedValues.get('feature');
  const specs = requestedFeatures?.length
    ? PRODUCT_IMAGE_CAPTURE_SPECS.filter(
      (spec) => requestedFeatures.includes(spec.captureId) || requestedFeatures.includes(spec.featureId),
    )
    : PRODUCT_IMAGE_CAPTURE_SPECS;

  if (specs.length === 0) {
    throw new Error(`No product image capture specs matched: ${requestedFeatures?.join(', ') ?? '(none)'}.`);
  }
  const unknownFeatures = requestedFeatures?.filter(
    (featureId) => !PRODUCT_IMAGE_FEATURE_IDS.includes(featureId as ProductImageFeatureId)
      && !MARKETING_CAPTURE_FEATURE_IDS.includes(featureId as MarketingCaptureFeatureId),
  ) ?? [];
  if (unknownFeatures.length > 0) {
    throw new Error(`Unsupported product image feature ids: ${unknownFeatures.join(', ')}.`);
  }
  assertLocalCaptureOrigin(baseUrl);
  if (plannerStorageState) assertPublicSafeStorageState(path.resolve(plannerStorageState));
  if (coupleStorageState) assertPublicSafeStorageState(path.resolve(coupleStorageState));
  if (
    plannerStorageState
    && coupleStorageState
    && path.resolve(plannerStorageState) === path.resolve(coupleStorageState)
  ) {
    throw new Error('Planner and couple product captures require separate least-privilege storage states.');
  }

  const receipt: ProductImageCaptureReceipt = {
    generatedAt: new Date().toISOString(),
    gitSha: currentGitSha(),
    viewport: VIEWPORT,
    approvalStatus: 'review-required',
    features: [],
  };
  writeCaptureReceipt(receiptPath, receipt);

  for (const spec of specs) {
    await captureFeature(spec, {
      baseUrl,
      fixtures: readFixtures(fixturesPath),
      outputRoot,
      receiptPath,
      receipt,
      plannerStorageState,
      coupleStorageState,
      ocrExecutable: args.values.get('ocr-executable'),
    });
  }

  return receipt;
}

async function main(): Promise<void> {
  const receipt = await captureProductImages(process.argv.slice(2));
  console.log(`Captured ${receipt.features.length} product surfaces; approval remains review-required.`);
}

const isMainModule = process.argv[1]
  ? path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url))
  : false;

if (isMainModule) {
  main().catch((error: unknown) => {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  });
}
