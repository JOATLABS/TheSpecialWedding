import fs from 'node:fs';
import path from 'node:path';

import { chromium, type BrowserContextOptions, type Page } from 'playwright';

import {
  getDemoVideoById,
  getDemoVideoProductionRequirementById,
  type DemoVideoCaptureSurface,
} from '../../app/data/demoVideoProduction';
import {
  getNumberValue,
  getRequiredValue,
  parseCliArgs,
  parseKeyValuePairs,
  resolveFromRepo,
} from './cli';

const SIDE_EFFECT_SURFACES = new Set<DemoVideoCaptureSurface>(['guest-token', 'payment-link', 'vendor-token']);

function resolveRoute(route: string, routeParams: Record<string, string>): string {
  return route.replace(/\[([^\]]+)\]/g, (_, key: string) => {
    const value = routeParams[key] ?? process.env[`DEMO_ROUTE_PARAM_${key.toUpperCase()}`];
    if (!value) {
      throw new Error(`Route "${route}" needs --route-param ${key}=... or DEMO_ROUTE_PARAM_${key.toUpperCase()}.`);
    }

    return value;
  });
}

function assertCaptureIsAllowed(options: {
  surfaces: readonly DemoVideoCaptureSurface[];
  smoke: boolean;
  storageState?: string;
  allowSideEffectFixtures: boolean;
}): void {
  const protectedSurfaces = options.surfaces.filter((surface) => surface !== 'public-site' && surface !== 'public-form');
  const riskySurfaces = options.surfaces.filter((surface) => SIDE_EFFECT_SURFACES.has(surface));

  if (!options.smoke && protectedSurfaces.length > 0 && !options.storageState) {
    throw new Error(
      `Production capture touches ${protectedSurfaces.join(', ')} and needs --storage-state with a seeded demo session. Use --smoke only for non-publishable export-path checks.`,
    );
  }

  if (!options.smoke && riskySurfaces.length > 0 && !options.allowSideEffectFixtures) {
    throw new Error(
      `Production capture touches ${riskySurfaces.join(', ')}. Pass --allow-side-effect-fixtures only after confirming test tokens, test payments, and demo media are loaded.`,
    );
  }
}

async function installVisibleCursor(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const install = () => {
      if (document.getElementById('demo-recording-cursor')) return;

      const cursor = document.createElement('div');
      cursor.id = 'demo-recording-cursor';
      cursor.style.position = 'fixed';
      cursor.style.left = '0';
      cursor.style.top = '0';
      cursor.style.width = '18px';
      cursor.style.height = '18px';
      cursor.style.marginLeft = '-9px';
      cursor.style.marginTop = '-9px';
      cursor.style.border = '2px solid white';
      cursor.style.borderRadius = '999px';
      cursor.style.background = 'rgba(212, 165, 165, 0.72)';
      cursor.style.boxShadow = '0 0 0 5px rgba(15, 23, 42, 0.28)';
      cursor.style.pointerEvents = 'none';
      cursor.style.zIndex = '2147483647';
      cursor.style.transform = 'translate3d(48px, 48px, 0)';
      cursor.style.transition = 'transform 90ms ease-out';
      document.body.appendChild(cursor);

      window.addEventListener(
        'mousemove',
        (event) => {
          cursor.style.transform = `translate3d(${event.clientX}px, ${event.clientY}px, 0)`;
        },
        { passive: true },
      );
    };

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', install, { once: true });
    } else {
      install();
    }
  });
}

async function moveLikeHuman(page: Page, durationSeconds: number): Promise<void> {
  const viewport = page.viewportSize() ?? { width: 1440, height: 900 };
  const waypoints = [
    { x: viewport.width * 0.18, y: viewport.height * 0.24 },
    { x: viewport.width * 0.62, y: viewport.height * 0.28 },
    { x: viewport.width * 0.72, y: viewport.height * 0.68 },
    { x: viewport.width * 0.34, y: viewport.height * 0.72 },
  ];
  const segmentDelay = Math.max(450, Math.floor((durationSeconds * 1000) / (waypoints.length * 2)));

  await page.mouse.move(48, 48, { steps: 12 });
  await page.waitForTimeout(600);

  for (let index = 0; index < waypoints.length; index += 1) {
    const waypoint = waypoints[index];
    await page.mouse.move(waypoint.x, waypoint.y, { steps: 28 });
    await page.waitForTimeout(segmentDelay);

    if (index < waypoints.length - 1) {
      await page.mouse.wheel(0, Math.round(viewport.height * 0.32));
      await page.waitForTimeout(segmentDelay);
    }
  }
}

async function waitForDemoPage(page: Page, url: string): Promise<void> {
  const navigationTimeoutMs = Number.parseInt(process.env.DEMO_RECORD_NAVIGATION_TIMEOUT_MS ?? '60000', 10);
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: navigationTimeoutMs });
  } catch (error) {
    if (!(error instanceof Error) || !error.message.includes('Timeout') || page.url() !== url) {
      throw error;
    }
    console.warn(`Navigation reached ${url} but did not report DOMContentLoaded before ${navigationTimeoutMs}ms; continuing with visible-body checks.`);
  }
  await page.locator('body').waitFor({ state: 'visible', timeout: 15_000 });
  await page.waitForLoadState('load', { timeout: 15_000 }).catch(() => undefined);
  await page.waitForTimeout(1_200);
}

async function main(): Promise<void> {
  const args = parseCliArgs(process.argv.slice(2));
  const demoId = getRequiredValue(args, 'demo');
  const demo = getDemoVideoById(demoId);
  const requirement = getDemoVideoProductionRequirementById(demoId);

  if (!demo || !requirement) {
    throw new Error(`Unknown demo "${demoId}".`);
  }

  const smoke = args.flags.has('smoke');
  const baseUrl = args.values.get('base-url') ?? 'http://127.0.0.1:3100';
  const routeParams = parseKeyValuePairs(args.repeatedValues.get('route-param') ?? []);
  const routes = args.flags.has('route-plan') && !args.values.has('route')
    ? demo.routePlan.map((item) => resolveRoute(item, routeParams))
    : [args.values.get('route') ?? resolveRoute(demo.routePlan[0], routeParams)];
  const maxSeconds = getNumberValue(args, 'max-seconds', smoke ? 10 : demo.durationSeconds);
  const width = getNumberValue(args, 'width', 1440);
  const height = getNumberValue(args, 'height', 900);
  const storageState = args.values.get('storage-state');

  assertCaptureIsAllowed({
    surfaces: requirement.captureSurfaces,
    smoke,
    storageState,
    allowSideEffectFixtures: args.flags.has('allow-side-effect-fixtures'),
  });

  const rawDir = resolveFromRepo('public', 'demo-videos', 'raw');
  fs.mkdirSync(rawDir, { recursive: true });

  const contextOptions: BrowserContextOptions = {
    viewport: { width, height },
    recordVideo: {
      dir: rawDir,
      size: { width, height },
    },
  };

  if (storageState) {
    contextOptions.storageState = path.resolve(storageState);
  }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext(contextOptions);
  const page = await context.newPage();
  await installVisibleCursor(page);

  const routeLabel = routes.join(' -> ');
  console.log(`Recording ${demoId} from ${routeLabel}${smoke ? ' (smoke capture)' : ''}`);

  const secondsPerRoute = Math.max(6, Math.floor(maxSeconds / routes.length));
  for (const route of routes) {
    const url = new URL(route, baseUrl).toString();
    await waitForDemoPage(page, url);
    await moveLikeHuman(page, secondsPerRoute);
  }

  const video = page.video();
  await page.close();
  await context.close();
  await browser.close();

  const temporaryPath = await video?.path();
  if (!temporaryPath) {
    throw new Error('Playwright did not produce a recording.');
  }

  const outputPath = resolveFromRepo('public', requirement.rawRecordingPath);
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.rmSync(outputPath, { force: true });
  fs.renameSync(temporaryPath, outputPath);

  console.log(`Raw recording written to public/${requirement.rawRecordingPath}`);
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
