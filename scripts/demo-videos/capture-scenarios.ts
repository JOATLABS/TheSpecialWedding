import type { Locator, Page } from 'playwright';

import {
  createCaptureReadinessMonitor,
  type CaptureReadinessMonitor,
  type CaptureReadinessReceipt,
  waitForCaptureReady,
} from './wait-for-capture-ready';

export type CaptureLocator =
  | { by: 'css'; value: string; index?: number }
  | { by: 'label'; value: string; exact?: boolean; index?: number }
  | { by: 'placeholder'; value: string; exact?: boolean; index?: number }
  | { by: 'role'; role: 'button' | 'heading' | 'link' | 'main' | 'navigation' | 'region'; name?: string; exact?: boolean; index?: number }
  | { by: 'test-id'; value: string; index?: number }
  | { by: 'text'; value: string; exact?: boolean; index?: number };

export type DemoCaptureStep =
  | { kind: 'goto'; route: string }
  | { kind: 'click'; locator: CaptureLocator }
  | { kind: 'fill'; locator: CaptureLocator; value: string }
  | { kind: 'press'; locator: CaptureLocator; key: string }
  | { kind: 'drag'; locator: CaptureLocator; target: CaptureLocator }
  | { kind: 'assert-visible'; locator: CaptureLocator }
  | { kind: 'checkpoint'; name: string; readyLocator?: CaptureLocator; holdMs?: number };

export type DemoCaptureScenario = {
  demoId: string;
  session: 'planner' | 'couple' | 'public';
  steps: readonly DemoCaptureStep[];
};

export type ExecuteDemoCaptureScenarioOptions = {
  baseUrl: string;
  routeParams?: Readonly<Record<string, string>>;
  routeOverride?: string;
  monitor?: CaptureReadinessMonitor;
  readinessTimeoutMs?: number;
};

export type DemoCaptureCheckpointReceipt = {
  name: string;
  readiness: CaptureReadinessReceipt;
};

const role = (
  roleName: Extract<CaptureLocator, { by: 'role' }>['role'],
  name?: string,
  index?: number,
): CaptureLocator => ({ by: 'role', role: roleName, name, exact: name !== undefined, index });

const text = (value: string, index?: number): CaptureLocator => ({ by: 'text', value, exact: true, index });
const placeholder = (value: string, index?: number): CaptureLocator => ({
  by: 'placeholder',
  value,
  exact: true,
  index,
});
const testId = (value: string): CaptureLocator => ({ by: 'test-id', value });

const SUPPORTED_DEMO_CAPTURE_SCENARIOS = {
  'planner-command-center-walkthrough': {
    demoId: 'planner-command-center-walkthrough',
    session: 'planner',
    steps: [
      { kind: 'goto', route: '/admin/planner' },
      { kind: 'assert-visible', locator: role('heading', 'Your Weddings') },
      { kind: 'click', locator: role('button', 'Manage', 0) },
      { kind: 'assert-visible', locator: role('heading', 'Event Details') },
      { kind: 'checkpoint', name: 'wedding-source-record', readyLocator: role('heading', 'Event Details') },
      { kind: 'goto', route: '/couple/dashboard' },
      { kind: 'click', locator: role('button', 'Timeline') },
      { kind: 'assert-visible', locator: role('heading', 'Timeline') },
      { kind: 'checkpoint', name: 'couple-timeline', readyLocator: role('heading', 'Timeline') },
      { kind: 'goto', route: '/admin/guests' },
      { kind: 'click', locator: { by: 'label', value: 'Show declined guests', exact: true } },
      { kind: 'assert-visible', locator: role('button', 'Clear Filters') },
      { kind: 'checkpoint', name: 'guest-filter', readyLocator: role('button', 'Clear Filters') },
      { kind: 'goto', route: '/admin/weddings/[id]/seating' },
      { kind: 'click', locator: { by: 'label', value: 'Open seating setup guide', exact: true } },
      { kind: 'assert-visible', locator: testId('seating-guide-panel') },
      { kind: 'checkpoint', name: 'seating-guide', readyLocator: testId('seating-guide-panel') },
      { kind: 'goto', route: '/admin/vendors' },
      { kind: 'click', locator: { by: 'role', role: 'button', name: 'Contracts', exact: false } },
      { kind: 'assert-visible', locator: role('heading', 'Your Contracts') },
      { kind: 'checkpoint', name: 'vendor-contracts', readyLocator: role('heading', 'Your Contracts') },
      { kind: 'goto', route: '/admin/budget' },
      { kind: 'press', locator: { by: 'css', value: 'body' }, key: 'Home' },
      { kind: 'assert-visible', locator: text('Budget Management') },
      { kind: 'checkpoint', name: 'budget-overview', readyLocator: text('Budget Management') },
    ],
  },
  'morning-view-demo': {
    demoId: 'morning-view-demo',
    session: 'planner',
    steps: [
      { kind: 'goto', route: '/admin/planner' },
      { kind: 'assert-visible', locator: role('heading', 'Your Weddings') },
      { kind: 'click', locator: role('button', 'Manage', 0) },
      { kind: 'assert-visible', locator: role('heading', 'Event Details') },
      { kind: 'checkpoint', name: 'next-wedding-action', readyLocator: role('heading', 'Event Details') },
    ],
  },
  'couple-portal-demo': {
    demoId: 'couple-portal-demo',
    session: 'couple',
    steps: [
      { kind: 'goto', route: '/couple/dashboard' },
      { kind: 'assert-visible', locator: role('navigation', 'Portal sections') },
      { kind: 'click', locator: role('button', 'Timeline') },
      { kind: 'assert-visible', locator: role('heading', 'Timeline') },
      { kind: 'checkpoint', name: 'couple-timeline', readyLocator: role('heading', 'Timeline') },
    ],
  },
  'microsite-auto-publishes-demo': {
    demoId: 'microsite-auto-publishes-demo',
    session: 'planner',
    steps: [
      { kind: 'goto', route: '/admin/weddings/[id]' },
      { kind: 'click', locator: { by: 'role', role: 'button', name: 'theme', exact: false } },
      { kind: 'assert-visible', locator: role('heading', 'Theme Configuration') },
      { kind: 'checkpoint', name: 'microsite-theme-source', readyLocator: role('heading', 'Theme Configuration') },
      { kind: 'goto', route: '/[slug]' },
      { kind: 'press', locator: { by: 'css', value: 'body' }, key: 'Home' },
      { kind: 'assert-visible', locator: { by: 'css', value: 'main' } },
      { kind: 'checkpoint', name: 'published-microsite', readyLocator: { by: 'css', value: 'main' } },
    ],
  },
  'guest-management-demo': {
    demoId: 'guest-management-demo',
    session: 'planner',
    steps: [
      { kind: 'goto', route: '/admin/guests' },
      { kind: 'assert-visible', locator: text('Guest Management') },
      { kind: 'click', locator: { by: 'label', value: 'Show declined guests', exact: true } },
      { kind: 'assert-visible', locator: role('button', 'Clear Filters') },
      { kind: 'checkpoint', name: 'declined-guest-filter', readyLocator: role('button', 'Clear Filters') },
    ],
  },
  'seating-orchestrator-demo': {
    demoId: 'seating-orchestrator-demo',
    session: 'planner',
    steps: [
      { kind: 'goto', route: '/admin/weddings/[id]/seating' },
      { kind: 'assert-visible', locator: text('Seating Arrangement') },
      { kind: 'click', locator: { by: 'label', value: 'Open seating setup guide', exact: true } },
      { kind: 'assert-visible', locator: testId('seating-guide-panel') },
      { kind: 'checkpoint', name: 'layout-guide', readyLocator: testId('seating-guide-panel') },
    ],
  },
  'contract-sign-pay-demo': {
    demoId: 'contract-sign-pay-demo',
    session: 'planner',
    steps: [
      { kind: 'goto', route: '/admin/vendors' },
      { kind: 'assert-visible', locator: text('Vendor Management') },
      { kind: 'click', locator: { by: 'role', role: 'button', name: 'Contracts', exact: false } },
      { kind: 'assert-visible', locator: role('heading', 'Your Contracts') },
      { kind: 'click', locator: role('button', 'Open Contract Canvas') },
      { kind: 'assert-visible', locator: role('heading', 'Contract Canvas') },
      { kind: 'checkpoint', name: 'contract-canvas', readyLocator: role('heading', 'Contract Canvas') },
    ],
  },
  'vendor-directory-crm-demo': {
    demoId: 'vendor-directory-crm-demo',
    session: 'public',
    steps: [
      { kind: 'goto', route: '/vendors' },
      { kind: 'assert-visible', locator: role('heading', 'Find the perfect vendors for every wedding.') },
      { kind: 'fill', locator: placeholder('Search vendors...'), value: 'photographer' },
      { kind: 'assert-visible', locator: { by: 'css', value: 'main' } },
      { kind: 'checkpoint', name: 'vendor-search', readyLocator: { by: 'css', value: 'main' } },
    ],
  },
} as const satisfies Record<string, DemoCaptureScenario>;

export const DEMO_CAPTURE_SCENARIOS: Readonly<Record<string, DemoCaptureScenario>> =
  SUPPORTED_DEMO_CAPTURE_SCENARIOS;

function resolveLocator(page: Page, descriptor: CaptureLocator): Locator {
  let locator: Locator;
  switch (descriptor.by) {
    case 'css':
      locator = page.locator(descriptor.value);
      break;
    case 'label':
      locator = page.getByLabel(descriptor.value, { exact: descriptor.exact });
      break;
    case 'placeholder':
      locator = page.getByPlaceholder(descriptor.value, { exact: descriptor.exact });
      break;
    case 'role':
      locator = page.getByRole(descriptor.role, {
        name: descriptor.name,
        exact: descriptor.exact,
      });
      break;
    case 'test-id':
      locator = page.getByTestId(descriptor.value);
      break;
    case 'text':
      locator = page.getByText(descriptor.value, { exact: descriptor.exact });
      break;
    default: {
      const unsupported: never = descriptor;
      throw new Error(`Unsupported capture locator: ${JSON.stringify(unsupported)}`);
    }
  }

  return descriptor.index === undefined ? locator : locator.nth(descriptor.index);
}

export function captureLocatorToSelector(locator: CaptureLocator): string | undefined {
  if (locator.by === 'css') return locator.value;
  if (locator.by === 'test-id') return `[data-testid="${locator.value}"]`;
  return undefined;
}

function resolveRoute(route: string, routeParams: Readonly<Record<string, string>>): string {
  return route.replace(/\[([^\]]+)\]/g, (_, key: string) => {
    const value = routeParams[key] ?? process.env[`DEMO_ROUTE_PARAM_${key.toUpperCase()}`];
    if (!value) throw new Error(`Capture route "${route}" requires route parameter "${key}".`);
    return encodeURIComponent(value);
  });
}

function assertScenarioContract(scenario: DemoCaptureScenario): void {
  let hasAnyProductAction = false;
  let pendingProductAction = false;
  let assertionAfterPendingAction = false;
  let checkpoints = 0;

  for (const step of scenario.steps) {
    if (['click', 'fill', 'drag', 'press'].includes(step.kind)) {
      hasAnyProductAction = true;
      pendingProductAction = true;
      assertionAfterPendingAction = false;
      continue;
    }
    if (step.kind === 'assert-visible' && pendingProductAction) {
      assertionAfterPendingAction = true;
      continue;
    }
    if (step.kind === 'checkpoint') {
      checkpoints += 1;
      if (!pendingProductAction || !assertionAfterPendingAction) {
        throw new Error(`Scenario ${scenario.demoId} checkpoint ${step.name} lacks a post-action assertion.`);
      }
      pendingProductAction = false;
      assertionAfterPendingAction = false;
    }
  }

  if (!hasAnyProductAction || checkpoints === 0) {
    throw new Error(`Scenario ${scenario.demoId} must contain a product action and checkpoint.`);
  }
}

for (const scenario of Object.values(SUPPORTED_DEMO_CAPTURE_SCENARIOS)) {
  assertScenarioContract(scenario);
}

export function getDemoCaptureScenario(demoId: string): DemoCaptureScenario {
  const scenario = DEMO_CAPTURE_SCENARIOS[demoId];
  if (!scenario) {
    throw new Error(
      `Demo capture scenario "${demoId}" is unsupported. Capture fails closed until an explicit action scenario is added.`,
    );
  }
  return scenario;
}

export async function executeDemoCaptureScenario(
  page: Page,
  demoId: string,
  options: ExecuteDemoCaptureScenarioOptions,
): Promise<DemoCaptureCheckpointReceipt[]> {
  const scenario = getDemoCaptureScenario(demoId);
  if (options.routeOverride && scenario.steps.filter((step) => step.kind === 'goto').length > 1) {
    throw new Error(
      `Scenario ${demoId} spans multiple routes; a single --route override would invalidate its assertions.`,
    );
  }
  const routeParams = options.routeParams ?? {};
  const ownedMonitor = options.monitor ? undefined : createCaptureReadinessMonitor(page);
  const monitor = options.monitor ?? ownedMonitor!;
  const checkpoints: DemoCaptureCheckpointReceipt[] = [];
  let usedRouteOverride = false;

  try {
    for (const step of scenario.steps) {
      switch (step.kind) {
        case 'goto': {
          const route = !usedRouteOverride && options.routeOverride
            ? options.routeOverride
            : resolveRoute(step.route, routeParams);
          usedRouteOverride = usedRouteOverride || Boolean(options.routeOverride);
          const url = new URL(route, options.baseUrl).toString();
          await page.goto(url, { waitUntil: 'domcontentloaded', timeout: options.readinessTimeoutMs ?? 60_000 });
          await waitForCaptureReady(page, { monitor, timeoutMs: options.readinessTimeoutMs });
          break;
        }
        case 'click':
          await resolveLocator(page, step.locator).click();
          break;
        case 'fill':
          await resolveLocator(page, step.locator).fill(step.value);
          break;
        case 'press':
          await resolveLocator(page, step.locator).press(step.key);
          break;
        case 'drag':
          await resolveLocator(page, step.locator).dragTo(resolveLocator(page, step.target));
          break;
        case 'assert-visible':
          await resolveLocator(page, step.locator).waitFor({ state: 'visible', timeout: options.readinessTimeoutMs ?? 30_000 });
          break;
        case 'checkpoint': {
          const readySelector = step.readyLocator ? captureLocatorToSelector(step.readyLocator) : undefined;
          const readiness = await waitForCaptureReady(page, {
            monitor,
            readyLocator: readySelector,
            timeoutMs: options.readinessTimeoutMs,
          });
          checkpoints.push({ name: step.name, readiness });
          await page.waitForTimeout(step.holdMs ?? 900);
          break;
        }
        default: {
          const unsupported: never = step;
          throw new Error(`Unsupported demo capture step: ${JSON.stringify(unsupported)}`);
        }
      }
    }
  } finally {
    ownedMonitor?.dispose();
  }

  return checkpoints;
}
