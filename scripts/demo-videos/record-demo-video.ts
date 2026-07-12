import fs from 'node:fs';
import path from 'node:path';

import { chromium, type BrowserContextOptions, type Page, type Video } from 'playwright';

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
import { executeDemoCaptureScenario, getDemoCaptureScenario } from './capture-scenarios';
import { assertPublicSafeStorageState } from './public-safe-storage';
import { createCaptureReadinessMonitor, installCaptureStability } from './wait-for-capture-ready';

const SIDE_EFFECT_SURFACES = new Set<DemoVideoCaptureSurface>(['guest-token', 'payment-link', 'vendor-token']);

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
  await page.addInitScript({
    content: `(() => {
      const installRecordingCursor = () => {
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
        document.body.appendChild(cursor);
        window.addEventListener('mousemove', (event) => {
          cursor.style.transform = 'translate3d(' + event.clientX + 'px, ' + event.clientY + 'px, 0)';
        }, { passive: true });
      };
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', installRecordingCursor, { once: true });
      } else {
        installRecordingCursor();
      }
    })();`,
  });
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
  const maxSeconds = getNumberValue(args, 'max-seconds', smoke ? 10 : demo.durationSeconds);
  const width = getNumberValue(args, 'width', 1440);
  const height = getNumberValue(args, 'height', 900);
  const storageState = args.values.get('storage-state');

  if (storageState && !args.flags.has('allow-personal-state')) {
    assertPublicSafeStorageState(path.resolve(storageState));
  }

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
  const monitor = createCaptureReadinessMonitor(page);
  let video: Video | null = null;

  try {
    await installCaptureStability(page);
    await installVisibleCursor(page);

    const scenario = getDemoCaptureScenario(demoId);
    console.log(
      `Recording ${demoId} with explicit ${scenario.session} actions${smoke ? ' (smoke capture)' : ''}`,
    );
    page.setDefaultTimeout(Math.max(30_000, maxSeconds * 1_000));
    await executeDemoCaptureScenario(page, demoId, {
      baseUrl,
      routeParams,
      routeOverride: args.values.get('route'),
      monitor,
      readinessTimeoutMs: Math.max(30_000, maxSeconds * 1_000),
    });
    video = page.video();
  } finally {
    monitor.dispose();
    await page.close().catch(() => undefined);
    await context.close().catch(() => undefined);
    await browser.close().catch(() => undefined);
  }

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
