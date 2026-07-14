import fs from 'node:fs';
import path from 'node:path';

import { chromium } from 'playwright';

import { DEMO_VIDEO_PRODUCTION_CATALOG } from '../../app/data/demoVideos';
import { parseCliArgs, resolveFromRepo } from './cli';
import { assertPublicSafeStorageState } from './public-safe-storage';

type CaptureFixtures = {
  primaryWeddingId: string;
  primarySlug: string;
  guestMemoriesUploadToken: string;
  formId: string;
  coupleFormId: string;
  vendorProfileId: string;
  vendorContractId: string;
  vendorContractToken: string;
  vendorPortalToken: string;
};

type RouteReceipt = {
  demoId: string;
  session: 'planner' | 'couple' | 'public';
  route: string;
  resolvedRoute: string;
  url: string;
  ok: boolean;
  text: string;
  networkIssues: NetworkIssue[];
  runtimeIssues: string[];
};

type NetworkIssue = {
  status?: number;
  method: string;
  url: string;
  failure?: string;
};

const BAD_PAGE_PATTERN =
  /planner portal welcome back sign in|couple portal welcome back|portal not available|invalid|expired|unable to load|not found|not currently available|isn.t available|failed to load|error loading|something went wrong|forbidden/i;

function readFixtures(filePath: string): CaptureFixtures {
  if (!fs.existsSync(filePath)) {
    throw new Error(`Capture fixtures file does not exist: ${filePath}. Run npm run demo:seed first.`);
  }
  return JSON.parse(fs.readFileSync(filePath, 'utf8')) as CaptureFixtures;
}

function resolveRoute(route: string, routeParams: Record<string, string>): string {
  return route.replace(/\[([^\]]+)\]/g, (_, key: string) => {
    const value = routeParams[key];
    if (!value) {
      throw new Error(`Route "${route}" needs route param ${key}.`);
    }
    return value;
  });
}

function routeParamsForDemo(demoId: string, fixtures: CaptureFixtures): Record<string, string> {
  const common = {
    id: fixtures.primaryWeddingId,
    weddingId: fixtures.primaryWeddingId,
    slug: fixtures.primarySlug,
    uploadToken: fixtures.guestMemoriesUploadToken,
    token: fixtures.vendorPortalToken,
    formId: fixtures.coupleFormId,
  };

  if (demoId === 'forms-canvas-demo') {
    return { ...common, id: fixtures.formId, formId: fixtures.coupleFormId };
  }

  if (demoId === 'contract-sign-pay-demo') {
    return {
      ...common,
      id: fixtures.vendorContractId,
      token: fixtures.vendorContractToken,
      vendorProfileId: fixtures.vendorProfileId,
    };
  }

  return common;
}

function shouldInspectNetworkUrl(requestUrl: string, baseUrl: string): boolean {
  const parsedUrl = new URL(requestUrl);
  const parsedBaseUrl = new URL(baseUrl);

  if (parsedUrl.origin !== parsedBaseUrl.origin) return false;
  if (parsedUrl.pathname.startsWith('/_next/')) return false;
  if (parsedUrl.pathname === '/favicon.ico') return false;
  if (/\.(avif|css|gif|ico|jpg|jpeg|js|map|mp4|png|svg|webm|woff2?)$/i.test(parsedUrl.pathname)) {
    return false;
  }

  return true;
}

function isBadNetworkStatus(status: number): boolean {
  return status >= 400;
}

function sessionForRoute(route: string): RouteReceipt['session'] {
  if (route.startsWith('/admin')) return 'planner';
  if (route.startsWith('/couple')) return 'couple';
  return 'public';
}

function networkKey(issue: NetworkIssue): string {
  return `${issue.method} ${issue.url}`;
}

function filterBenignNetworkIssues(
  issues: readonly NetworkIssue[],
  successfulRequests: ReadonlySet<string>,
): NetworkIssue[] {
  return issues.filter((issue) => {
    if (
      issue.failure === 'net::ERR_ABORTED'
      && successfulRequests.has(networkKey(issue))
    ) {
      return false;
    }

    return true;
  });
}

async function main(): Promise<void> {
  const args = parseCliArgs(process.argv.slice(2));
  const baseUrl = args.values.get('base-url') ?? 'http://localhost:3100';
  const fixturesPath = args.values.get('fixtures') ?? resolveFromRepo('output', 'demo-videos', 'capture-fixtures.json');
  const receiptPath = args.values.get('receipt') ?? resolveFromRepo('output', 'demo-videos', 'route-audit-receipt.json');
  const plannerStorageState = args.values.get('planner-storage-state')
    ?? resolveFromRepo('output', 'demo-videos', 'state', 'demo-planner.json');
  const coupleStorageState = args.values.get('couple-storage-state')
    ?? resolveFromRepo('output', 'demo-videos', 'state', 'demo-couple.json');
  const publicStorageState = args.values.get('public-storage-state')
    ?? resolveFromRepo('output', 'demo-videos', 'state', 'demo-public.json');
  const demoFilters = args.repeatedValues.get('demo');
  const fixtures = readFixtures(fixturesPath);
  if (!args.flags.has('allow-personal-state')) {
    for (const storageState of [plannerStorageState, coupleStorageState, publicStorageState]) {
      assertPublicSafeStorageState(storageState);
    }
  }
  const demos = demoFilters?.length
    ? DEMO_VIDEO_PRODUCTION_CATALOG.filter((demo) => demoFilters.includes(demo.id))
    : [...DEMO_VIDEO_PRODUCTION_CATALOG];

  if (demos.length === 0) {
    throw new Error(`No demos matched filters: ${demoFilters?.join(', ')}`);
  }

  const browser = await chromium.launch({ headless: true });
  const contexts = {
    planner: await browser.newContext({
      storageState: plannerStorageState,
      viewport: { width: 1440, height: 900 },
    }),
    couple: await browser.newContext({
      storageState: coupleStorageState,
      viewport: { width: 1440, height: 900 },
    }),
    public: await browser.newContext({
      storageState: publicStorageState,
      viewport: { width: 1440, height: 900 },
    }),
  };
  const receipts: RouteReceipt[] = [];

  for (const demo of demos) {
    const routeParams = routeParamsForDemo(demo.id, fixtures);
    for (const route of demo.routePlan) {
      const session = sessionForRoute(route);
      const context = contexts[session];
      const page = await context.newPage();
      const networkIssues: NetworkIssue[] = [];
      const runtimeIssues: string[] = [];
      const successfulRequests = new Set<string>();

      page.on('console', (message) => {
        if (message.type() === 'error') {
          runtimeIssues.push(`console error: ${message.text()}`);
        }
      });
      page.on('pageerror', (error) => {
        runtimeIssues.push(`page error: ${error.message}`);
      });

      page.on('response', (response) => {
        const request = response.request();
        const responseUrl = response.url();
        if (!shouldInspectNetworkUrl(responseUrl, baseUrl)) return;
        const status = response.status();
        const issue = {
          status,
          method: request.method(),
          url: responseUrl,
        };

        if (status >= 200 && status < 400) {
          successfulRequests.add(networkKey(issue));
          return;
        }

        if (!isBadNetworkStatus(status)) return;

        networkIssues.push(issue);
      });

      page.on('requestfailed', (request) => {
        const requestUrl = request.url();
        if (!shouldInspectNetworkUrl(requestUrl, baseUrl)) return;

        networkIssues.push({
          method: request.method(),
          url: requestUrl,
          failure: request.failure()?.errorText ?? 'request failed',
        });
      });

      const resolvedRoute = resolveRoute(route, routeParams);
      const url = new URL(resolvedRoute, baseUrl).toString();
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60_000 });
      await page.locator('body').waitFor({ state: 'visible', timeout: 20_000 });
      await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => undefined);
      await page.waitForTimeout(1_500);
      const fullText = (await page.locator('body').innerText()).replace(/\s+/g, ' ').trim();
      const text = fullText;
      const sample = text.slice(0, 700);
      const meaningfulNetworkIssues = filterBenignNetworkIssues(networkIssues, successfulRequests);
      const expectedUrl = new URL(resolvedRoute, baseUrl);
      const actualUrl = new URL(page.url());
      const finalRoute = `${actualUrl.pathname}${actualUrl.search}`;
      const expectedRoute = `${expectedUrl.pathname}${expectedUrl.search}`;
      if (actualUrl.origin !== expectedUrl.origin || finalRoute !== expectedRoute) {
        runtimeIssues.push(`final route ${finalRoute} did not match ${expectedRoute}`);
      }
      const visibleOk = text.length > 20 && text !== 'Loading...' && !BAD_PAGE_PATTERN.test(text);
      const ok = visibleOk
        && meaningfulNetworkIssues.length === 0
        && runtimeIssues.length === 0;
      receipts.push({
        demoId: demo.id,
        session,
        route,
        resolvedRoute,
        url: page.url(),
        ok,
        text: sample,
        networkIssues: meaningfulNetworkIssues,
        runtimeIssues,
      });
      console.log(
        `${ok ? 'OK' : 'BAD'} ${demo.id} ${session} ${resolvedRoute}${meaningfulNetworkIssues.length ? ` (${meaningfulNetworkIssues.length} network issue(s))` : ''}${runtimeIssues.length ? ` (${runtimeIssues.length} runtime issue(s))` : ''}`,
      );
      await page.close();
    }
  }

  await Promise.all(Object.values(contexts).map((context) => context.close()));
  await browser.close();

  fs.mkdirSync(path.dirname(receiptPath), { recursive: true });
  fs.writeFileSync(receiptPath, `${JSON.stringify({ generatedAt: new Date().toISOString(), receipts }, null, 2)}\n`);

  const failed = receipts.filter((entry) => !entry.ok);
  if (failed.length > 0) {
    console.error(`${failed.length} route(s) failed audit. Receipt: ${receiptPath}`);
    process.exitCode = 1;
    return;
  }

  console.log(`All demo routes passed. Receipt: ${receiptPath}`);
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
