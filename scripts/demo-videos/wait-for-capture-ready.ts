import { createHash } from 'node:crypto';

import type { Page, Request, Response } from 'playwright';

export type CaptureReadinessMonitor = {
  readonly consoleErrorDigests: string[];
  readonly pageErrorDigests: string[];
  readonly failedRequestDigests: string[];
  readonly pendingRequests: Set<Request>;
  lastNetworkActivityAt: number;
  dispose: () => void;
};

export type WaitForCaptureReadyOptions = {
  monitor: CaptureReadinessMonitor;
  readyLocator?: string;
  timeoutMs?: number;
  networkQuietMs?: number;
  stableFrameSamples?: number;
  stableFrameIntervalMs?: number;
};

export type CaptureReadinessReceipt = {
  frameSha256: string;
  stableFrameSamples: number;
  networkQuietMs: number;
};

const CAPTURE_STABILITY_CSS = `
  *, *::before, *::after {
    animation-delay: 0s !important;
    animation-duration: 0s !important;
    animation-iteration-count: 1 !important;
    caret-color: transparent !important;
    scroll-behavior: auto !important;
    transition-delay: 0s !important;
    transition-duration: 0s !important;
  }
`;

const BLOCKING_TEXT_PATTERN =
  /^(?:loading|please wait|something went wrong|unable to load|failed to (?:load|fetch)|error loading|forbidden|not found)\b/i;

function digest(value: string | Buffer): string {
  return createHash('sha256').update(value).digest('hex');
}

function shouldTrackRequest(request: Request): boolean {
  const resourceType = request.resourceType();
  if (!['document', 'fetch', 'xhr'].includes(resourceType)) return false;

  const pathname = new URL(request.url()).pathname;
  return !/(?:\/analytics(?:\/|$)|\/events(?:\/|$)|\/stream(?:\/|$)|\/poll(?:\/|$))/.test(pathname);
}

export function createCaptureReadinessMonitor(page: Page): CaptureReadinessMonitor {
  const consoleErrorDigests: string[] = [];
  const pageErrorDigests: string[] = [];
  const failedRequestDigests: string[] = [];
  const pendingRequests = new Set<Request>();

  const monitor: CaptureReadinessMonitor = {
    consoleErrorDigests,
    pageErrorDigests,
    failedRequestDigests,
    pendingRequests,
    lastNetworkActivityAt: Date.now(),
    dispose: () => {
      page.off('console', onConsole);
      page.off('pageerror', onPageError);
      page.off('request', onRequest);
      page.off('requestfinished', onRequestFinished);
      page.off('requestfailed', onRequestFailed);
      page.off('response', onResponse);
    },
  };

  const onConsole = (message: { type: () => string; text: () => string }) => {
    if (message.type() === 'error') consoleErrorDigests.push(digest(message.text()));
  };
  const onPageError = (error: Error) => pageErrorDigests.push(digest(error.message));
  const onRequest = (request: Request) => {
    if (!shouldTrackRequest(request)) return;
    pendingRequests.add(request);
    monitor.lastNetworkActivityAt = Date.now();
  };
  const onRequestFinished = (request: Request) => {
    if (!pendingRequests.delete(request)) return;
    monitor.lastNetworkActivityAt = Date.now();
  };
  const onRequestFailed = (request: Request) => {
    if (!shouldTrackRequest(request)) return;
    pendingRequests.delete(request);
    monitor.lastNetworkActivityAt = Date.now();
    const failure = request.failure()?.errorText ?? 'request-failed';
    if (failure !== 'net::ERR_ABORTED') failedRequestDigests.push(digest(failure));
  };
  const onResponse = (response: Response) => {
    if (!shouldTrackRequest(response.request()) || response.status() < 400) return;
    failedRequestDigests.push(digest(`http-status:${response.status()}`));
  };

  page.on('console', onConsole);
  page.on('pageerror', onPageError);
  page.on('request', onRequest);
  page.on('requestfinished', onRequestFinished);
  page.on('requestfailed', onRequestFailed);
  page.on('response', onResponse);

  return monitor;
}

export async function installCaptureStability(page: Page): Promise<void> {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.addInitScript({
    content: `(() => {
      const installCaptureStability = () => {
        if (document.getElementById('demo-capture-stability')) return;
        const style = document.createElement('style');
        style.id = 'demo-capture-stability';
        style.textContent = ${JSON.stringify(CAPTURE_STABILITY_CSS)};
        document.documentElement.appendChild(style);
      };
      if (document.documentElement) installCaptureStability();
      else document.addEventListener('DOMContentLoaded', installCaptureStability, { once: true });
    })();`,
  });
}

async function waitForFontsAndImages(page: Page): Promise<void> {
  await page.evaluate(`(async () => {
    await document.fonts?.ready;
    const images = Array.from(document.images).filter((image) => {
      const style = window.getComputedStyle(image);
      return style.display !== 'none' && style.visibility !== 'hidden';
    });
    await Promise.all(images.map(async (image) => {
      if (!image.complete) {
        await new Promise((resolve, reject) => {
          image.addEventListener('load', () => resolve(), { once: true });
          image.addEventListener('error', () => reject(new Error('visible-image-failed')), { once: true });
        });
      }
      if (image.naturalWidth === 0) throw new Error('visible-image-failed');
      if (image.decode) await image.decode();
    }));
  })()`);
}

type BlockingVisualState = { kind: 'pending' | 'failure'; evidenceDigest: string };

async function findBlockingVisualState(page: Page): Promise<BlockingVisualState | undefined> {
  const busySelectors = [
    '[aria-busy="true"]',
    '[data-loading="true"]',
    '[data-testid*="loading" i]',
    '[data-testid*="skeleton" i]',
    '.animate-spin',
    '.animate-pulse',
  ];

  for (const selector of busySelectors) {
    const candidates = page.locator(selector);
    const count = await candidates.count();
    for (let index = 0; index < count; index += 1) {
      if (await candidates.nth(index).isVisible()) {
        return { kind: 'pending', evidenceDigest: digest(selector) };
      }
    }
  }

  const bodyText = await page.locator('body').innerText();
  const blockingLine = bodyText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .find((line) => line.length > 0 && line.length <= 160 && BLOCKING_TEXT_PATTERN.test(line));

  if (blockingLine) {
    if (/^(?:loading|please wait)\b/i.test(blockingLine)) {
      return { kind: 'pending', evidenceDigest: digest(blockingLine) };
    }
    return { kind: 'failure', evidenceDigest: digest(blockingLine) };
  }

  return undefined;
}

async function waitForNoBlockingVisualState(page: Page, deadline: number): Promise<void> {
  while (Date.now() < deadline) {
    const blocked = await findBlockingVisualState(page);
    if (!blocked) return;
    if (blocked.kind === 'failure') {
      throw new Error(`Capture blocked by visible failure state (${blocked.evidenceDigest}).`);
    }
    await page.waitForTimeout(Math.min(100, Math.max(1, deadline - Date.now())));
  }

  throw new Error('Capture readiness timed out waiting for visible loading state to clear.');
}

function assertMonitorIsClean(monitor: CaptureReadinessMonitor): void {
  const categories = [
    monitor.consoleErrorDigests.length ? 'console-error' : null,
    monitor.pageErrorDigests.length ? 'page-error' : null,
    monitor.failedRequestDigests.length ? 'request-failed' : null,
  ].filter(Boolean);

  if (categories.length > 0) {
    throw new Error(`Capture readiness failed (${categories.join(', ')}); details were redacted.`);
  }
}

async function waitForNetworkQuiet(
  page: Page,
  monitor: CaptureReadinessMonitor,
  quietMs: number,
  deadline: number,
): Promise<void> {
  while (Date.now() < deadline) {
    const quietForMs = Date.now() - monitor.lastNetworkActivityAt;
    if (monitor.pendingRequests.size === 0 && quietForMs >= quietMs) return;
    await page.waitForTimeout(Math.min(100, Math.max(1, deadline - Date.now())));
  }

  throw new Error(`Capture readiness timed out waiting for network quiet (${monitor.pendingRequests.size} pending).`);
}

async function waitForStableFrames(
  page: Page,
  requiredSamples: number,
  intervalMs: number,
  deadline: number,
): Promise<string> {
  let previousHash: string | undefined;
  let consecutiveSamples = 0;

  while (Date.now() < deadline) {
    const frameHash = digest(await page.screenshot({ animations: 'disabled', caret: 'hide' }));
    consecutiveSamples = frameHash === previousHash ? consecutiveSamples + 1 : 1;
    previousHash = frameHash;
    if (consecutiveSamples >= requiredSamples) return frameHash;
    await page.waitForTimeout(Math.min(intervalMs, Math.max(1, deadline - Date.now())));
  }

  throw new Error('Capture readiness timed out waiting for visually stable frames.');
}

export async function waitForCaptureReady(
  page: Page,
  options: WaitForCaptureReadyOptions,
): Promise<CaptureReadinessReceipt> {
  const timeoutMs = options.timeoutMs ?? 30_000;
  const networkQuietMs = options.networkQuietMs ?? 750;
  const stableFrameSamples = options.stableFrameSamples ?? 3;
  const stableFrameIntervalMs = options.stableFrameIntervalMs ?? 250;
  const deadline = Date.now() + timeoutMs;

  await page.locator('body').waitFor({ state: 'visible', timeout: timeoutMs });
  if (options.readyLocator) {
    await page.locator(options.readyLocator).first().waitFor({ state: 'visible', timeout: timeoutMs });
  }

  await Promise.race([
    waitForFontsAndImages(page),
    page.waitForTimeout(Math.max(1, deadline - Date.now())).then(() => {
      throw new Error('Capture readiness timed out waiting for visible fonts and images.');
    }),
  ]);
  await waitForNoBlockingVisualState(page, deadline);
  assertMonitorIsClean(options.monitor);
  await waitForNetworkQuiet(page, options.monitor, networkQuietMs, deadline);
  assertMonitorIsClean(options.monitor);

  const frameSha256 = await waitForStableFrames(
    page,
    stableFrameSamples,
    stableFrameIntervalMs,
    deadline,
  );
  const finalBlockingState = await findBlockingVisualState(page);
  if (finalBlockingState) {
    throw new Error(`Capture became visually unstable after frame sampling (${finalBlockingState.kind}).`);
  }
  assertMonitorIsClean(options.monitor);

  return { frameSha256, stableFrameSamples, networkQuietMs };
}
