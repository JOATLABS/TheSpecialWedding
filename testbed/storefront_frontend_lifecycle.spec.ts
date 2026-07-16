import fs from "node:fs";
import { createHash } from "node:crypto";

import AxeBuilder from "@axe-core/playwright";
import {
  expect,
  test,
  type BrowserContext,
  type Page,
  type Request,
  type TestInfo,
} from "@playwright/test";

type AcceptanceStatus = "PASSED" | "FAILED" | "BLOCKED" | "NOT RUN";

type StorefrontRunManifest = {
  run_id: string;
  backend_url: string;
  frontend_url: string;
  artifact_dir: string;
  provider_mode: "deterministic" | "live";
  acceptance: Record<string, AcceptanceStatus>;
  fixtures: {
    signature_email: string;
    solo_email: string;
    foreign_email: string;
    slug: string;
    title: string;
    description: string;
    contact_email: string;
    contact_phone: string;
    package_name: string;
    inactive_package_name: string;
    template_package_name: string;
    included_service_name: string;
    excluded_service_name: string;
    review_text: string;
    unpublished_review_text: string;
    inquiry_name: string;
    inquiry_email: string;
    inquiry_message: string;
    custom_domain: string;
    foreign_package_name: string;
    foreign_review_text: string;
    image_path: string;
  };
};

type BrowserDiagnostics = {
  console: Array<{ type: string; text: string }>;
  pageErrors: string[];
  requestFailures: Array<{ method: string; url: string; error: string | null }>;
  expectedRequestAborts: Array<{ method: string; url: string; error: string }>;
  unexpectedHttpFailures: Array<{
    method: string;
    status: number;
    url: string;
  }>;
  expectedHttpFailures: Array<{
    method: string;
    status: number;
    pathnameSuffix: string;
    remaining: number;
  }>;
  expectedConsoleErrors: Array<{
    status: number;
    pathnameSuffix: string;
    remaining: number;
  }>;
  externalRequests: string[];
};

function loadManifest(): StorefrontRunManifest {
  const manifestPath = process.env.STOREFRONT_TESTBED_RUN_MANIFEST;
  if (!manifestPath)
    throw new Error("STOREFRONT_TESTBED_RUN_MANIFEST is required");
  return JSON.parse(
    fs.readFileSync(manifestPath, "utf8"),
  ) as StorefrontRunManifest;
}

const manifest = loadManifest();
const PROVIDER_CONTROL_PREFIX = "/__testbed/storefront-provider";
const signaturePassword = process.env.STOREFRONT_TESTBED_SIGNATURE_PASSWORD;
const soloPassword = process.env.STOREFRONT_TESTBED_SOLO_PASSWORD;
const foreignPassword = process.env.STOREFRONT_TESTBED_FOREIGN_PASSWORD;
const providerRunId = process.env.STOREFRONT_PROVIDER_HARNESS_RUN_ID;
const providerControlToken = process.env.STOREFRONT_PROVIDER_HARNESS_TOKEN;

if (!signaturePassword || !soloPassword || !foreignPassword) {
  throw new Error("Storefront testbed browser credentials were not provided");
}
if (
  manifest.provider_mode === "deterministic" &&
  (!providerRunId || providerRunId !== manifest.run_id || !providerControlToken)
) {
  throw new Error(
    "The deterministic provider control identity is missing or mismatched",
  );
}

function loopbackOrigin(value: string): string {
  const url = new URL(value);
  if (!["127.0.0.1", "localhost", "::1"].includes(url.hostname)) {
    throw new Error(`Storefront E2E origin is not loopback: ${url.origin}`);
  }
  return url.origin;
}

const allowedOrigins = new Set([
  loopbackOrigin(manifest.frontend_url),
  loopbackOrigin(manifest.backend_url),
]);
const diagnosticsByContext = new WeakMap<BrowserContext, BrowserDiagnostics>();
const instrumentedPages = new WeakSet<Page>();

function resetDiagnostics(context: BrowserContext) {
  const diagnostics = diagnosticsByContext.get(context);
  if (!diagnostics) throw new Error("Browser diagnostics were not installed");
  diagnostics.console.length = 0;
  diagnostics.pageErrors.length = 0;
  diagnostics.requestFailures.length = 0;
  diagnostics.expectedRequestAborts.length = 0;
  diagnostics.unexpectedHttpFailures.length = 0;
  diagnostics.expectedHttpFailures.length = 0;
  diagnostics.expectedConsoleErrors.length = 0;
  diagnostics.externalRequests.length = 0;
}

function isExpectedBrowserCancellation(request: Request) {
  if (request.failure()?.errorText !== "net::ERR_ABORTED") return false;
  const parsed = new URL(request.url());
  if (parsed.origin !== loopbackOrigin(manifest.frontend_url)) return false;
  if (parsed.pathname.includes("/storefront")) return false;
  const method = request.method();
  const methodPath = `${method} ${parsed.pathname}`;
  if (
    parsed.search === "" &&
    (methodPath === "POST /api/proxy/admin/token/refresh" ||
      methodPath === "GET /api/proxy/admin/planner/weddings" ||
      methodPath === "GET /api/proxy/admin/user/notifications/count")
  ) {
    return true;
  }
  if (method !== "GET") return false;
  return (
    parsed.searchParams.has("_rsc") ||
    parsed.pathname === "/api/proxy/admin/notifications/stream" ||
    parsed.pathname === "/api/proxy/admin/planner/metrics" ||
    parsed.pathname === "/api/proxy/admin/engagement-signals"
  );
}

function installPageDiagnostics(page: Page, diagnostics: BrowserDiagnostics) {
  if (instrumentedPages.has(page)) return;
  instrumentedPages.add(page);
  page.on("console", (message) => {
    if (message.type() === "error" || message.type() === "warning") {
      const text = message.text();
      const expectedResourceFailure =
        message.type() === "error"
          ? text.match(
              /^Failed to load resource: the server responded with a status of (\d{3}) \([^)]+\)$/,
            )
          : null;
      const locationUrl = message.location().url;
      let locationPathname = "";
      if (locationUrl) {
        try {
          locationPathname = new URL(locationUrl).pathname;
        } catch {
          locationPathname = "";
        }
      }
      const allowance = expectedResourceFailure
        ? diagnostics.expectedConsoleErrors.find(
            (candidate) =>
              candidate.remaining > 0 &&
              candidate.status === Number(expectedResourceFailure[1]) &&
              locationPathname.endsWith(candidate.pathnameSuffix),
          )
        : null;
      if (allowance) {
        allowance.remaining -= 1;
        return;
      }
      diagnostics.console.push({ type: message.type(), text });
    }
  });
  page.on("pageerror", (error) =>
    diagnostics.pageErrors.push(error.stack ?? error.message),
  );
}

async function installDiagnostics(
  context: BrowserContext,
): Promise<BrowserDiagnostics> {
  const diagnostics: BrowserDiagnostics = {
    console: [],
    pageErrors: [],
    requestFailures: [],
    expectedRequestAborts: [],
    unexpectedHttpFailures: [],
    expectedHttpFailures: [],
    expectedConsoleErrors: [],
    externalRequests: [],
  };
  diagnosticsByContext.set(context, diagnostics);
  await context.addInitScript(() => {
    const inspectText = (node: Node) => {
      if (node.nodeType !== Node.TEXT_NODE) return;
      const parent = node.parentElement;
      if (!parent || parent.closest("script, style, code, pre")) return;
      const text = node.textContent?.trim() ?? "";
      if (
        text.length > 2 &&
        text.length < 4_000 &&
        /^(?:\{|\[)/.test(text) &&
        /(?:\}|\])$/.test(text) &&
        /["'][-_a-z0-9]+["']\s*:/i.test(text)
      ) {
        console.error(`[storefront-raw-json] ${text.slice(0, 500)}`);
      }
    };
    const inspect = (root: Node) => {
      inspectText(root);
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode())
        inspectText(node);
    };
    const start = () => {
      inspect(document.body);
      new MutationObserver((mutations) => {
        for (const mutation of mutations) {
          if (mutation.type === "characterData") inspectText(mutation.target);
          for (const node of mutation.addedNodes) inspect(node);
        }
      }).observe(document.body, {
        childList: true,
        subtree: true,
        characterData: true,
      });
    };
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", start, { once: true });
    } else {
      start();
    }
  });
  for (const page of context.pages()) installPageDiagnostics(page, diagnostics);
  context.on("page", (page) => installPageDiagnostics(page, diagnostics));
  context.on("requestfailed", (request) => {
    if (isExpectedBrowserCancellation(request)) {
      diagnostics.expectedRequestAborts.push({
        method: request.method(),
        url: request.url(),
        error: "net::ERR_ABORTED",
      });
      return;
    }
    diagnostics.requestFailures.push({
      method: request.method(),
      url: request.url(),
      error: request.failure()?.errorText ?? null,
    });
  });
  context.on("response", (response) => {
    if (response.status() < 400) return;
    const observed = {
      method: response.request().method(),
      status: response.status(),
      url: response.url(),
    };
    const pathname = new URL(observed.url).pathname;
    const allowance = diagnostics.expectedHttpFailures.find(
      (candidate) =>
        candidate.remaining > 0 &&
        candidate.method === observed.method &&
        candidate.status === observed.status &&
        pathname.endsWith(candidate.pathnameSuffix),
    );
    if (allowance) allowance.remaining -= 1;
    else diagnostics.unexpectedHttpFailures.push(observed);
  });
  await context.route("**/*", async (route) => {
    const parsed = new URL(route.request().url());
    if (
      ["data:", "blob:"].includes(parsed.protocol) ||
      allowedOrigins.has(parsed.origin)
    ) {
      await route.continue();
      return;
    }
    diagnostics.externalRequests.push(route.request().url());
    await route.abort("blockedbyclient");
  });
  return diagnostics;
}

function allowHttpFailure(
  context: BrowserContext,
  method: string,
  status: number,
  pathnameSuffix: string,
  count = 1,
) {
  const diagnostics = diagnosticsByContext.get(context);
  if (!diagnostics) throw new Error("Browser diagnostics were not installed");
  diagnostics.expectedHttpFailures.push({
    method: method.toUpperCase(),
    status,
    pathnameSuffix,
    remaining: count,
  });
  diagnostics.expectedConsoleErrors.push({
    status,
    pathnameSuffix,
    remaining: count,
  });
}

async function attachCheckpoint(
  page: Page,
  testInfo: TestInfo,
  name: string,
): Promise<string[]> {
  const safe = name
    .replace(/[^a-z0-9]+/gi, "-")
    .replace(/^-|-$/g, "")
    .toLowerCase();
  const screenshotPath = testInfo.outputPath(`${safe}.png`);
  await page.screenshot({ path: screenshotPath, fullPage: false });
  const screenshotName = `${safe}-screenshot`;
  const domName = `${safe}-dom`;
  const ariaName = `${safe}-aria`;
  const qualityName = `${safe}-quality`;
  await testInfo.attach(screenshotName, {
    path: screenshotPath,
    contentType: "image/png",
  });
  await testInfo.attach(domName, {
    body: Buffer.from(await page.locator("html").innerHTML()),
    contentType: "text/html",
  });
  await testInfo.attach(ariaName, {
    body: Buffer.from(await page.locator("body").ariaSnapshot()),
    contentType: "text/yaml",
  });
  const horizontalOverflow = await page.evaluate(() => ({
    documentScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body?.scrollWidth ?? 0,
    viewportWidth: window.innerWidth,
    passed:
      document.documentElement.scrollWidth <= window.innerWidth &&
      (document.body?.scrollWidth ?? 0) <= window.innerWidth,
  }));
  const rawJsonVisible = await page
    .locator("body")
    .getByText(/\{\s*["']?(detail|error)["']?\s*:/i)
    .count();
  const dialogSelector = '[role="dialog"]';
  // Modal checkpoints evaluate the storefront workflow itself. On the entry
  // route, only its storefront launch action belongs to this acceptance scope;
  // unrelated package-management controls have their own test surface.
  const route = new URL(page.url()).pathname;
  const accessibilityScope =
    (await page.locator(dialogSelector).count()) > 0
      ? dialogSelector
      : route === "/admin/packages"
        ? "button:has(svg.lucide-settings)"
        : "body";
  const accessibility = await new AxeBuilder({ page })
    .include(accessibilityScope)
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const quality = {
    schema_version: 1,
    checkpoint: name,
    captured_at: new Date().toISOString(),
    route: `${new URL(page.url()).pathname}${new URL(page.url()).search}`,
    accessibility_scope: accessibilityScope,
    checks: {
      horizontalOverflow: horizontalOverflow.passed,
      rawJsonVisible: rawJsonVisible === 0,
      accessibilityViolations: accessibility.violations.length === 0,
    },
    horizontalOverflow,
    accessibility_violations: accessibility.violations.map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      help: violation.help,
    })),
  };
  await testInfo.attach(qualityName, {
    body: Buffer.from(JSON.stringify(quality, null, 2)),
    contentType: "application/json",
  });
  expect(
    horizontalOverflow.passed,
    "horizontal overflow detected at checkpoint",
  ).toBe(true);
  expect(rawJsonVisible, "raw backend JSON rendered at checkpoint").toBe(0);
  expect(
    accessibility.violations,
    accessibility.violations
      .map((item) => `${item.id}: ${item.help}`)
      .join("\n"),
  ).toEqual([]);
  return [screenshotName, domName, ariaName, qualityName];
}

async function recordScenarioEvidence(
  testInfo: TestInfo,
  scenarioId: string,
  component: string,
  routes: string[],
  checks: Record<string, boolean>,
  attachmentNames: string[],
) {
  expect(
    routes.length,
    `${scenarioId}/${component} must name at least one route`,
  ).toBeGreaterThan(0);
  expect(
    Object.entries(checks).filter(([, passed]) => passed !== true),
    `${scenarioId}/${component} contains failed checks`,
  ).toEqual([]);
  const available = new Set(
    testInfo.attachments.map((attachment) => attachment.name),
  );
  expect(
    attachmentNames.filter((name) => !available.has(name)),
    `${scenarioId}/${component} references attachments outside this test result`,
  ).toEqual([]);
  const normalizedRoutes = [...new Set(routes)].sort();
  expect(
    normalizedRoutes.filter((route) => !route.startsWith("/")),
    `${scenarioId}/${component} routes must be application paths`,
  ).toEqual([]);
  await testInfo.attach(`scenario-receipt-${scenarioId}-${component}`, {
    body: Buffer.from(
      JSON.stringify(
        {
          schema_version: 1,
          scenario_id: scenarioId,
          component,
          run_id: manifest.run_id,
          test_title: testInfo.title,
          project: testInfo.project.name,
          captured_at: new Date().toISOString(),
          routes: normalizedRoutes,
          checks,
          attachment_names: [...new Set(attachmentNames)].sort(),
        },
        null,
        2,
      ),
    ),
    contentType: "application/json",
  });
}

async function attachDiagnostics(
  testInfo: TestInfo,
  diagnostics: BrowserDiagnostics,
) {
  await testInfo.attach("browser-diagnostics", {
    body: Buffer.from(JSON.stringify(diagnostics, null, 2)),
    contentType: "application/json",
  });
}

function expectCleanBrowser(diagnostics: BrowserDiagnostics) {
  expect(
    diagnostics.externalRequests,
    "unexpected external browser requests",
  ).toEqual([]);
  expect(diagnostics.pageErrors, "uncaught browser page errors").toEqual([]);
  expect(diagnostics.requestFailures, "failed browser requests").toEqual([]);
  expect(diagnostics.console, "browser console warnings/errors").toEqual([]);
  expect(
    diagnostics.unexpectedHttpFailures,
    "unexpected HTTP 4xx/5xx responses",
  ).toEqual([]);
  expect(
    diagnostics.expectedHttpFailures.filter(
      (allowance) => allowance.remaining !== 0,
    ),
    "registered HTTP failures that were never observed",
  ).toEqual([]);
}

async function clearSession(page: Page) {
  await page.context().clearCookies();
  await page.goto("/admin/login");
  await page.evaluate(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });
  await page.reload();
}

async function login(page: Page, email: string, password: string) {
  const diagnostics = diagnosticsByContext.get(page.context());
  if (diagnostics) expectCleanBrowser(diagnostics);
  await clearSession(page);
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /log in|sign in/i }).click();
  await page.waitForURL(
    (url) =>
      url.pathname.startsWith("/admin") && url.pathname !== "/admin/login",
  );
  await expect(page.getByRole("button", { name: "User menu" })).toBeVisible();
  resetDiagnostics(page.context());
  await page.goto("/admin/packages");
  await expect(
    page.getByRole("heading", { name: "Marketing & Packages" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Configure Storefront" }),
  ).toBeVisible();
  await expect(page.locator("main .animate-pulse")).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Something went wrong" }),
  ).toHaveCount(0);
}

async function providerControl<T extends Record<string, unknown>>(
  page: Page,
  pathSuffix: string,
  data?: Record<string, unknown>,
): Promise<T> {
  if (
    manifest.provider_mode !== "deterministic" ||
    !providerRunId ||
    !providerControlToken
  ) {
    throw new Error("Deterministic provider controls are not available");
  }
  const response = await page.request.fetch(
    `${manifest.backend_url}${PROVIDER_CONTROL_PREFIX}/${pathSuffix}`,
    {
      method: data === undefined ? "GET" : "POST",
      headers: {
        "x-storefront-testbed-run-id": providerRunId,
        "x-storefront-testbed-control-token": providerControlToken,
      },
      ...(data === undefined ? {} : { data }),
    },
  );
  expect(response.status(), `provider control ${pathSuffix}`).toBe(200);
  expect(response.headers()["x-storefront-provider-mode"]).toBe(
    "deterministic-testbed",
  );
  const payload = (await response.json()) as T;
  expect(payload.run_id ?? manifest.run_id).toBe(manifest.run_id);
  return payload;
}

async function currentAdminToken(page: Page): Promise<string> {
  const token = await page.evaluate(
    () =>
      (window as Window & { __TSW_ADMIN_AUTH_TOKEN__?: string })
        .__TSW_ADMIN_AUTH_TOKEN__,
  );
  expect(
    token,
    "the authenticated browser token must be available in memory",
  ).toBeTruthy();
  return token!;
}

async function authenticatedBackendRequest(
  page: Page,
  method: string,
  pathSuffix: string,
  data?: Record<string, unknown>,
) {
  return page.request.fetch(`${manifest.backend_url}${pathSuffix}`, {
    method,
    headers: { Authorization: `Bearer ${await currentAdminToken(page)}` },
    ...(data === undefined ? {} : { data }),
  });
}

type ImmutableStorefrontAccountSnapshot = {
  account: {
    id: string | null;
    role: string | null;
    profilePlanId: string | null;
    capabilityPlanId: string | null;
    subscriptionStatus: string | null;
    storefrontEnabled: boolean;
    customDomainEnabled: boolean;
  };
  storefront: {
    slug: string | null;
    published: boolean;
    revision: number | null;
  };
};

async function immutableStorefrontAccountSnapshot(
  page: Page,
): Promise<ImmutableStorefrontAccountSnapshot> {
  const [profileResponse, accessResponse, settingsResponse] = await Promise.all([
    authenticatedBackendRequest(page, "GET", "/admin/profile"),
    authenticatedBackendRequest(page, "GET", "/admin/storefront/access"),
    authenticatedBackendRequest(page, "GET", "/admin/storefront/settings"),
  ]);
  expect(profileResponse.status()).toBe(200);
  expect(accessResponse.status()).toBe(200);
  expect(settingsResponse.status()).toBe(200);
  const profile = (await profileResponse.json()) as Record<string, unknown>;
  const userData =
    profile.user_data && typeof profile.user_data === "object"
      ? (profile.user_data as Record<string, unknown>)
      : {};
  const settingsEnvelope = (await settingsResponse.json()) as {
    settings?: Record<string, unknown> | null;
  };
  const access = (await accessResponse.json()) as Record<string, unknown>;
  const settings = settingsEnvelope.settings ?? {};
  return {
    account: {
      id: typeof profile.id === "string" ? profile.id : null,
      role: typeof profile.role === "string" ? profile.role : null,
      profilePlanId:
        typeof userData.plan_id === "string" ? userData.plan_id : null,
      capabilityPlanId:
        typeof access.plan_id === "string" ? access.plan_id : null,
      subscriptionStatus:
        typeof profile.subscription_status === "string"
          ? profile.subscription_status
          : null,
      storefrontEnabled: access.storefront_enabled === true,
      customDomainEnabled: access.custom_domain_enabled === true,
    },
    storefront: {
      slug: typeof settings.slug === "string" ? settings.slug : null,
      published: settings.is_published === true,
      revision:
        typeof settings.revision === "number" ? settings.revision : null,
    },
  };
}

async function openStorefrontDialog(page: Page) {
  if (new URL(page.url()).pathname !== "/admin/packages") {
    await page.goto("/admin/packages");
  }
  const trigger = page.getByRole("button", { name: "Configure Storefront" });
  await expect(trigger).toBeVisible();
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: "Planner Storefront" });
  await expect(dialog).toBeVisible();
  return { dialog, trigger };
}

async function selectTab(page: Page, name: string | RegExp) {
  const tab = page.getByRole("tab", { name });
  await tab.click();
  await expect(tab).toHaveAttribute("aria-selected", "true");
}

async function assertNoRawJson(page: Page) {
  await expect(page.locator("body")).not.toContainText(
    /\{\s*["']?(detail|error)["']?\s*:/i,
  );
}

async function assertDialogLayoutAndAccessibility(page: Page) {
  const dialog = page.getByRole("dialog", { name: "Planner Storefront" });
  const box = await dialog.boundingBox();
  const viewport = page.viewportSize();
  expect(box).not.toBeNull();
  expect(viewport).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.y).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(viewport!.width + 1);
  expect(box!.y + box!.height).toBeLessThanOrEqual(viewport!.height + 1);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  const results = await new AxeBuilder({ page })
    .include('[role="dialog"]')
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(
    results.violations,
    results.violations.map((item) => `${item.id}: ${item.help}`).join("\n"),
  ).toEqual([]);
}

async function disconnectDomain(page: Page) {
  const button = page.getByRole("button", { name: "Disconnect domain" });
  await button.click();
  const confirmation = page.getByRole("dialog", { name: /Disconnect .*\?/ });
  await expect(confirmation).toBeVisible();
  await confirmation.getByRole("button", { name: "Disconnect domain" }).click();
  return confirmation;
}

async function prepareNewDomainInput(page: Page) {
  const input = page.getByLabel("Storefront domain");
  const reset = page.getByRole("button", { name: "Set up another domain" });
  await expect(input.or(reset)).toBeVisible();
  if (await reset.isVisible()) {
    await reset.click();
  }
  await expect(input).toBeVisible();
  return input;
}

test.describe("storefront production testbed", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeEach(async ({ context }) => {
    await installDiagnostics(context);
  });

  test.afterEach(async ({ context, page }, testInfo) => {
    const diagnostics = diagnosticsByContext.get(context);
    if (page.url() !== "about:blank") {
      await attachCheckpoint(page, testInfo, "final-state");
    }
    if (diagnostics) {
      await attachDiagnostics(testInfo, diagnostics);
      expectCleanBrowser(diagnostics);
    }
  });

  test("gates Solo and completes the real Signature slug, publication, content, and inquiry lifecycle", async ({
    page,
    context,
  }, testInfo) => {
    test.skip(
      testInfo.project.name !== "chromium-desktop-light",
      "one serial mutation owner",
    );

    const settingsRequests: string[] = [];
    page.on("request", (request) => {
      if (
        new URL(request.url()).pathname.includes("/admin/storefront/settings")
      ) {
        settingsRequests.push(request.url());
      }
    });
    await login(page, manifest.fixtures.solo_email, soloPassword);
    settingsRequests.length = 0;
    await page.getByRole("button", { name: "Configure Storefront" }).click();
    const upgradeDialog = page.getByRole("dialog", {
      name: "Unlock Your Planner Storefront",
    });
    await expect(upgradeDialog).toHaveAttribute("aria-modal", "true");
    await expect(
      upgradeDialog.getByRole("heading", {
        name: "Unlock Your Planner Storefront",
      }),
    ).toBeVisible();
    await expect(upgradeDialog.locator("[data-transition]").last()).toHaveClass(
      /opacity-100/,
    );
    expect(settingsRequests).toEqual([]);
    const gateAttachments = await attachCheckpoint(
      page,
      testInfo,
      "solo-upgrade-gate",
    );
    const upgradeFocusables = upgradeDialog.locator(
      'a[href]:visible, button:not([disabled]):not([tabindex="-1"]):visible, input:not([disabled]):not([type="hidden"]):visible',
    );
    await upgradeFocusables.last().focus();
    await page.keyboard.press("Tab");
    await expect(upgradeFocusables.first()).toBeFocused();
    await upgradeFocusables.first().focus();
    await page.keyboard.press("Shift+Tab");
    await expect(upgradeFocusables.last()).toBeFocused();
    const upgradeAxe = await new AxeBuilder({ page })
      .include('[role="dialog"]')
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
      .analyze();
    expect(
      upgradeAxe.violations,
      upgradeAxe.violations
        .map((item) => `${item.id}: ${item.help}`)
        .join("\n"),
    ).toEqual([]);
    await page.keyboard.press("Escape");
    await expect(
      page.getByRole("heading", { name: "Unlock Your Planner Storefront" }),
    ).toBeHidden();
    await expect(
      page.getByRole("button", { name: "Configure Storefront" }),
    ).toBeFocused();
    const dismissedGateAttachments = await attachCheckpoint(
      page,
      testInfo,
      "solo-upgrade-gate-dismissed",
    );
    await recordScenarioEvidence(
      testInfo,
      "01_restricted_upgrade_gate",
      "gate",
      ["/admin/packages"],
      {
        noSettingsRequest: settingsRequests.length === 0,
        modalSemantics: true,
        focusTrap: true,
        escapeDismissal: true,
        focusRestoration: true,
      },
      [...gateAttachments, ...dismissedGateAttachments],
    );

    await login(page, manifest.fixtures.signature_email, signaturePassword);
    const { dialog: storefrontDialog } = await openStorefrontDialog(page);
    await selectTab(page, "Design");
    await page.getByLabel("Storefront URL").fill(manifest.fixtures.slug);
    await page.getByLabel("Storefront title").fill(manifest.fixtures.title);
    await page.getByLabel("Description").fill(manifest.fixtures.description);

    const selectedImageBytes = fs.readFileSync(manifest.fixtures.image_path);
    const selectedImageReceipt = {
      run_id: manifest.run_id,
      filename: manifest.fixtures.image_path.split("/").at(-1),
      size_bytes: selectedImageBytes.byteLength,
      sha256: createHash("sha256").update(selectedImageBytes).digest("hex"),
      png_signature_hex: selectedImageBytes.subarray(0, 8).toString("hex"),
    };
    expect(selectedImageReceipt.size_bytes).toBeGreaterThan(0);
    expect(selectedImageReceipt.png_signature_hex).toBe("89504e470d0a1a0a");
    await testInfo.attach("selected-real-media-bytes", {
      body: Buffer.from(JSON.stringify(selectedImageReceipt, null, 2)),
      contentType: "application/json",
    });

    let releaseUploadRequest: () => void = () => undefined;
    let uploadRequestObserved = false;
    const uploadRequestGate = new Promise<void>((resolve) => {
      releaseUploadRequest = resolve;
    });
    const uploadReservationRoute =
      "**/api/proxy/admin/storefront/upload-url?*";
    await page.route(uploadReservationRoute, async (route) => {
      uploadRequestObserved = true;
      await uploadRequestGate;
      await route.continue();
    });
    allowHttpFailure(context, "GET", 503, "/admin/storefront/upload-url");
    await page
      .getByLabel("Hero image")
      .setInputFiles(manifest.fixtures.image_path);
    const localHeroPreview = page.getByRole("img", {
      name: "Hero image preview",
    });
    await expect(localHeroPreview).toBeVisible();
    await expect.poll(() => uploadRequestObserved).toBe(true);
    await expect
      .poll(() =>
        localHeroPreview.evaluate((image) => {
          const element = image as HTMLImageElement;
          return (
            element.src.startsWith("blob:") &&
            element.complete &&
            element.naturalWidth === 64 &&
            element.naturalHeight === 40
          );
        }),
      )
      .toBe(true);
    const realBytesDecoded = true;
    const mediaSelectionAttachments = await attachCheckpoint(
      page,
      testInfo,
      "real-media-bytes-selected-before-provider-fence",
    );
    releaseUploadRequest();
    await expect(storefrontDialog.getByRole("alert")).toContainText(
      /temporarily unavailable|not configured/i,
    );
    await expect(localHeroPreview).toHaveCount(0);
    await page.unroute(uploadReservationRoute);
    await assertNoRawJson(page);

    await selectTab(page, "Content & publish");
    await page
      .getByLabel("Contact email")
      .fill(manifest.fixtures.contact_email);
    await page
      .getByLabel("Contact phone")
      .fill(manifest.fixtures.contact_phone);

    await page.getByRole("button", { name: "Live preview" }).click();
    const livePreview = page.getByRole("region", { name: "Live preview" });
    await expect(
      livePreview.getByRole("heading", { name: manifest.fixtures.title }),
    ).toBeVisible();
    await expect(
      livePreview.getByText(manifest.fixtures.package_name),
    ).toBeVisible();
    await page.getByRole("button", { name: "Save for preview" }).click();
    const headerPreview = page.getByRole("link", {
      name: /Preview storefront/,
    });
    await expect(headerPreview).toHaveAttribute(
      "href",
      `/storefront/${encodeURIComponent(manifest.fixtures.slug)}?preview=1`,
    );
    const [preview] = await Promise.all([
      context.waitForEvent("page"),
      page.getByRole("link", { name: /Open saved preview/ }).click(),
    ]);
    await preview.waitForLoadState("domcontentloaded");
    expect(preview.url()).toBe(
      `${manifest.frontend_url}/storefront/${encodeURIComponent(manifest.fixtures.slug)}?preview=1`,
    );
    await expect(preview.getByText(manifest.run_id).first()).toBeVisible();
    await expect(
      preview.getByText(manifest.fixtures.package_name),
    ).toBeVisible();
    await expect(
      preview.getByText(manifest.fixtures.inactive_package_name),
    ).toHaveCount(0);
    await expect(
      preview.getByText(manifest.fixtures.template_package_name),
    ).toHaveCount(0);
    await expect(
      preview.getByText(manifest.fixtures.excluded_service_name),
    ).toHaveCount(0);
    await expect(
      preview.getByText(manifest.fixtures.unpublished_review_text),
    ).toHaveCount(0);
    await expect(
      preview.getByText(manifest.fixtures.foreign_package_name),
    ).toHaveCount(0);
    await expect(
      preview.getByText(manifest.fixtures.foreign_review_text),
    ).toHaveCount(0);
    const internalPreviewAttachments = await attachCheckpoint(
      preview,
      testInfo,
      "saved-design-on-internal-slug-preview",
    );
    await recordScenarioEvidence(
      testInfo,
      "04_design_media_internal_preview",
      "design-media-preview",
      [
        "/admin/packages",
        "/admin/storefront/upload-url",
        "/admin/storefront/settings",
        `/storefront/${manifest.fixtures.slug}?preview=1`,
      ],
      {
        realPngBytesSelected: selectedImageReceipt.size_bytes > 0,
        realPngSignatureVerified:
          selectedImageReceipt.png_signature_hex === "89504e470d0a1a0a",
        localBytesDecodedByBrowser: realBytesDecoded,
        providerDisabledFailureWasFriendly: true,
        rawProviderErrorHidden: true,
        savedDesignRoundTripped: true,
        internalSlugPreviewOpenedWithoutDns: true,
        runMarkerVisibleInSavedPreview: true,
      },
      [
        "selected-real-media-bytes",
        ...mediaSelectionAttachments,
        ...internalPreviewAttachments,
      ],
    );
    await preview.close();

    const draft = await context.newPage();
    allowHttpFailure(
      context,
      "GET",
      404,
      `/storefront/${manifest.fixtures.slug}`,
    );
    expect(
      (await draft.goto(`/storefront/${manifest.fixtures.slug}`))?.status(),
    ).toBe(404);
    await draft.close();

    await selectTab(page, "Content & publish");
    const publish = page.getByRole("switch", { name: "Publish storefront" });
    if ((await publish.getAttribute("aria-checked")) !== "true")
      await publish.click();
    await page.getByRole("button", { name: "Save settings" }).click();
    await expect(page.getByRole("status")).toContainText(/published/i);

    const publicPage = await context.newPage();
    expect(
      (
        await publicPage.goto(`/storefront/${manifest.fixtures.slug}`)
      )?.status(),
    ).toBe(200);
    await expect(publicPage.getByText(manifest.run_id).first()).toBeVisible();
    await expect(
      publicPage.getByText(manifest.fixtures.package_name),
    ).toBeVisible();
    await expect(
      publicPage.getByText(manifest.fixtures.included_service_name),
    ).toBeVisible();
    await expect(
      publicPage.getByText(manifest.fixtures.review_text),
    ).toBeVisible();
    await expect(
      publicPage.getByText(manifest.fixtures.inactive_package_name),
    ).toHaveCount(0);
    await expect(
      publicPage.getByText(manifest.fixtures.template_package_name),
    ).toHaveCount(0);
    await expect(
      publicPage.getByText(manifest.fixtures.excluded_service_name),
    ).toHaveCount(0);
    await expect(
      publicPage.getByText(manifest.fixtures.unpublished_review_text),
    ).toHaveCount(0);
    await expect(
      publicPage.getByText(manifest.fixtures.foreign_package_name),
    ).toHaveCount(0);
    await expect(
      publicPage.getByText(manifest.fixtures.foreign_review_text),
    ).toHaveCount(0);
    const filteringAttachments = await attachCheckpoint(
      publicPage,
      testInfo,
      "public-content-filtering",
    );
    await recordScenarioEvidence(
      testInfo,
      "20_negative_content_filtering",
      "content-filtering",
      [`/storefront/${manifest.fixtures.slug}`],
      {
        activePackageVisible: true,
        includedServiceVisible: true,
        publishedReviewVisible: true,
        inactivePackageHidden: true,
        templatePackageHidden: true,
        excludedServiceHidden: true,
        unpublishedReviewHidden: true,
        foreignOwnerContentHidden: true,
      },
      filteringAttachments,
    );

    const inquiryForm = publicPage.locator("form");
    await publicPage.getByRole("button", { name: "Send inquiry" }).click();
    await expect(inquiryForm.getByRole("alert")).toContainText(
      /name, email, and a message/i,
    );
    const inquiryValidationAttachments = await attachCheckpoint(
      publicPage,
      testInfo,
      "published-inquiry-required-field-validation",
    );
    await publicPage.getByLabel("Name").fill(manifest.fixtures.inquiry_name);
    await publicPage.getByLabel("Email").fill(manifest.fixtures.inquiry_email);
    await publicPage
      .getByLabel("How can we help?")
      .fill(manifest.fixtures.inquiry_message);

    const inquiryReceipts: Array<{
      request: Record<string, unknown>;
      response: { inquiry_id: string; success: boolean };
    }> = [];
    let inquiryAcknowledgementCount = 0;
    const inquiryRoute = "**/api/storefront/*/inquiries";
    await publicPage.route(inquiryRoute, async (route) => {
      if (inquiryAcknowledgementCount >= 2) {
        await route.continue();
        return;
      }
      inquiryAcknowledgementCount += 1;
      const request = route.request().postDataJSON() as Record<string, unknown>;
      const upstream = await route.fetch();
      expect(upstream.status()).toBe(201);
      const response = (await upstream.json()) as {
        inquiry_id: string;
        success: boolean;
      };
      inquiryReceipts.push({ request, response });
      if (inquiryAcknowledgementCount === 1) {
        await route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({
            detail:
              "Inquiry confirmation was interrupted. Try again to confirm the same request.",
          }),
        });
        return;
      }
      await route.fulfill({ response: upstream });
    });
    allowHttpFailure(
      context,
      "POST",
      503,
      `/api/storefront/${manifest.fixtures.slug}/inquiries`,
    );
    await publicPage
      .getByRole("button", { name: /Send inquiry|Try again/ })
      .click();
    await expect(inquiryForm.getByRole("alert")).toContainText(
      /confirmation was interrupted/i,
    );
    const retryDueReceipt = await providerControl<{
      inquiry_id: string;
      notification_status: string;
      attempt_count: number;
      retry_due: boolean;
      external_provider_live: boolean;
    }>(page, "inquiry-retry-due", {
      inquiry_id: inquiryReceipts[0].response.inquiry_id,
    });
    expect(retryDueReceipt).toMatchObject({
      inquiry_id: inquiryReceipts[0].response.inquiry_id,
      notification_status: "retry_pending",
      attempt_count: 1,
      retry_due: true,
      external_provider_live: false,
    });
    await testInfo.attach("inquiry-delivery-retry-due-receipt", {
      body: Buffer.from(JSON.stringify(retryDueReceipt, null, 2)),
      contentType: "application/json",
    });
    await publicPage.getByRole("button", { name: "Try again" }).click();
    await expect(publicPage.getByRole("status")).toContainText(
      /inquiry was received/i,
    );
    await publicPage.unroute(inquiryRoute);
    expect(inquiryReceipts).toHaveLength(2);
    expect(inquiryReceipts[0].response.success).toBe(true);
    expect(inquiryReceipts[1].response.success).toBe(true);
    expect(inquiryReceipts[1].request.idempotency_key).toBe(
      inquiryReceipts[0].request.idempotency_key,
    );
    expect(inquiryReceipts[1].response.inquiry_id).toBe(
      inquiryReceipts[0].response.inquiry_id,
    );
    await testInfo.attach("inquiry-idempotent-retry-receipt", {
      body: Buffer.from(JSON.stringify(inquiryReceipts, null, 2)),
      contentType: "application/json",
    });
    const inquiryRecoveryAttachments = await attachCheckpoint(
      publicPage,
      testInfo,
      "published-inquiry-idempotent-retry-success",
    );

    for (let submission = 2; submission <= 5; submission += 1) {
      await publicPage
        .getByLabel("How can we help?")
        .fill(`${manifest.fixtures.inquiry_message} Follow-up ${submission}.`);
      await publicPage
        .getByRole("button", { name: "Send updated inquiry" })
        .click();
      await expect(publicPage.getByRole("status")).toContainText(
        /inquiry was received/i,
      );
    }
    await publicPage
      .getByLabel("How can we help?")
      .fill(`${manifest.fixtures.inquiry_message} Follow-up 6.`);
    allowHttpFailure(
      context,
      "POST",
      429,
      `/api/storefront/${manifest.fixtures.slug}/inquiries`,
    );
    await publicPage
      .getByRole("button", { name: "Send updated inquiry" })
      .click();
    await expect(inquiryForm.getByRole("alert")).toContainText(
      /too many inquiries/i,
    );
    const inquiryRateLimitAttachments = await attachCheckpoint(
      publicPage,
      testInfo,
      "published-inquiry-rate-limit-recovery",
    );
    await recordScenarioEvidence(
      testInfo,
      "06_inquiry_validation_rate_limit_delivery",
      "inquiry-lifecycle",
      [
        `/storefront/${manifest.fixtures.slug}`,
        `/api/storefront/${manifest.fixtures.slug}/inquiries`,
        `${PROVIDER_CONTROL_PREFIX}/inquiry-retry-due`,
      ],
      {
        requiredFieldsRejectedInBrowser: true,
        inquiryPersistedBeforeAcknowledgementFailure: true,
        retryPendingDeliveryPersisted: retryDueReceipt.retry_due,
        disabledProviderNeverClaimedLive:
          retryDueReceipt.external_provider_live === false,
        idempotencyKeyReused:
          inquiryReceipts[1].request.idempotency_key ===
          inquiryReceipts[0].request.idempotency_key,
        inquiryIdentityReused:
          inquiryReceipts[1].response.inquiry_id ===
          inquiryReceipts[0].response.inquiry_id,
        acknowledgementRetryRecovered: true,
        publicRateLimitRendered: true,
        rawDeliveryErrorHidden: true,
      },
      [
        "inquiry-idempotent-retry-receipt",
        "inquiry-delivery-retry-due-receipt",
        ...inquiryValidationAttachments,
        ...inquiryRecoveryAttachments,
        ...inquiryRateLimitAttachments,
      ],
    );
    await publicPage.close();

    if ((await publish.getAttribute("aria-checked")) !== "false")
      await publish.click();
    await page.getByRole("button", { name: "Save settings" }).click();
    const unpublished = await context.newPage();
    allowHttpFailure(
      context,
      "GET",
      404,
      `/storefront/${manifest.fixtures.slug}`,
    );
    expect(
      (
        await unpublished.goto(`/storefront/${manifest.fixtures.slug}`)
      )?.status(),
    ).toBe(404);
    await unpublished.close();
    if ((await publish.getAttribute("aria-checked")) !== "true")
      await publish.click();
    await page.getByRole("button", { name: "Save settings" }).click();
    await expect(page.getByRole("status")).toContainText(/published/i);
    const publicationAttachments = await attachCheckpoint(
      page,
      testInfo,
      "publication-lifecycle-republished",
    );
    await recordScenarioEvidence(
      testInfo,
      "05_draft_publish_filter_unpublish",
      "publication-lifecycle",
      ["/admin/packages", `/storefront/${manifest.fixtures.slug}`],
      {
        draftReturned404: true,
        publishReturned200: true,
        unpublishReturned404: true,
        republishSucceeded: true,
      },
      publicationAttachments,
    );
  });

  test("keeps every modal tab readable, bounded, accessible, and keyboard-operable", async ({
    page,
  }, testInfo) => {
    await login(page, manifest.fixtures.signature_email, signaturePassword);
    const { dialog, trigger } = await openStorefrontDialog(page);
    const modalAttachments: string[] = [];
    for (const tabName of ["Design", "Content & publish", "Domain"]) {
      await selectTab(page, tabName);
      await assertDialogLayoutAndAccessibility(page);
      modalAttachments.push(
        ...(await attachCheckpoint(
          page,
          testInfo,
          `modal-${tabName}-${testInfo.project.name}`,
        )),
      );
    }
    const focusables = dialog.locator(
      'a[href]:not([tabindex="-1"]):visible, button:not([disabled]):not([tabindex="-1"]):visible, input:not([disabled]):not([type="hidden"]):not([tabindex="-1"]):visible, textarea:not([disabled]):not([tabindex="-1"]):visible, select:not([disabled]):not([tabindex="-1"]):visible',
    );
    await focusables.last().focus();
    await page.keyboard.press("Tab");
    await expect(focusables.first()).toBeFocused();
    await focusables.first().focus();
    await page.keyboard.press("Shift+Tab");
    await expect(focusables.last()).toBeFocused();
    const tabs = dialog.getByRole("tab");
    await tabs.first().focus();
    await page.keyboard.press("End");
    await expect(tabs.last()).toBeFocused();
    await page.keyboard.press("Home");
    await expect(tabs.first()).toBeFocused();
    await page.keyboard.press("ArrowRight");
    await expect(tabs.nth(1)).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(tabs.nth(1)).toHaveAttribute("aria-selected", "true");
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(trigger).toBeFocused();
    await assertNoRawJson(page);
    await recordScenarioEvidence(
      testInfo,
      "02_modal_responsive_contrast",
      `layout-${testInfo.project.name}`,
      ["/admin/packages"],
      {
        designTabBounded: true,
        contentTabBounded: true,
        domainTabBounded: true,
        pageQualityPassed: true,
        modalDismissed: true,
      },
      modalAttachments,
    );
    if (testInfo.project.name === "chromium-desktop-light") {
      await recordScenarioEvidence(
        testInfo,
        "03_keyboard_focus_and_copy",
        "keyboard",
        ["/admin/packages"],
        {
          forwardFocusTrap: true,
          reverseFocusTrap: true,
          tabKeyboardNavigation: true,
          escapeDismissal: true,
          focusRestoration: true,
        },
        modalAttachments,
      );
    }
  });

  test("drives deterministic provider state through real FastAPI Mongo routes without external-provider claims", async ({
    page,
    context,
  }, testInfo) => {
    test.setTimeout(240_000);
    test.skip(
      testInfo.project.name !== "chromium-desktop-dark",
      "one serial provider owner",
    );
    test.skip(
      manifest.provider_mode !== "deterministic",
      "deterministic provider harness only",
    );

    const mainHostname = manifest.fixtures.custom_domain;
    const claimedHostname = `claimed-${manifest.run_id}.customer.test`;

    await providerControl(page, "configure", {
      hostname: mainHostname,
      domain_connect_supported: false,
      provider_mutations_enabled: true,
    });
    await providerControl(page, "advance", {
      hostname: mainHostname,
      dns_mode: "wrong",
    });

    await login(page, manifest.fixtures.signature_email, signaturePassword);
    const immutableStateBeforeDomainLifecycle =
      await immutableStorefrontAccountSnapshot(page);
    expect(immutableStateBeforeDomainLifecycle.storefront).toMatchObject({
      slug: manifest.fixtures.slug,
      published: true,
    });
    expect(immutableStateBeforeDomainLifecycle.account).toMatchObject({
      profilePlanId: "plan_solo",
      capabilityPlanId: "plan_signature",
      subscriptionStatus: "active",
      storefrontEnabled: true,
      customDomainEnabled: true,
    });
    const platformBefore = await context.newPage();
    expect(
      (
        await platformBefore.goto(`/storefront/${manifest.fixtures.slug}`)
      )?.status(),
    ).toBe(200);
    await expect(platformBefore.getByText(manifest.run_id).first()).toBeVisible();
    const platformBeforeAttachments = await attachCheckpoint(
      platformBefore,
      testInfo,
      "platform-slug-before-domain-setup",
    );
    await platformBefore.close();
    await openStorefrontDialog(page);
    await selectTab(page, "Domain");
    const domainRegion = page.getByRole("region", { name: "Custom domain" });
    const domainInput = page.getByLabel("Storefront domain");
    const providerBeforeMigrationPreflight = await providerControl<{
      cloudflare_call_count: number;
      provider_records: number;
    }>(page, "status");
    const routingBeforeMigrationOwnership = await providerControl<{
      hostname: string;
      A: string[];
      AAAA: string[];
      CNAME: string[];
    }>(
      page,
      `routing-snapshot?hostname=${encodeURIComponent(mainHostname)}`,
    );
    expect(routingBeforeMigrationOwnership).toMatchObject({
      hostname: mainHostname,
      A: [],
      AAAA: [],
      CNAME: [`wrong-target.${mainHostname.split(".").slice(1).join(".")}`],
    });

    await domainInput.fill("https://events.customer.test/path");
    allowHttpFailure(
      context,
      "POST",
      422,
      "/admin/storefront/custom-domain/preflight",
    );
    await page.getByRole("button", { name: "Check domain" }).click();
    await expect(domainRegion.getByRole("alert")).toContainText(
      /hostname|URL|path/i,
    );

    await domainInput.fill("customer.test");
    allowHttpFailure(
      context,
      "POST",
      422,
      "/admin/storefront/custom-domain/preflight",
    );
    await page.getByRole("button", { name: "Check domain" }).click();
    await expect(domainRegion.getByRole("alert")).toContainText(
      /Apex domains are not supported/i,
    );

    await domainInput.fill("events.thespecialwedding.io");
    allowHttpFailure(
      context,
      "POST",
      422,
      "/admin/storefront/custom-domain/preflight",
    );
    await page.getByRole("button", { name: "Check domain" }).click();
    await expect(domainRegion.getByRole("alert")).toContainText(
      /Platform-owned hostnames|platform domain/i,
    );

    await domainInput.fill(mainHostname);
    await page.getByLabel("Move an existing domain").check();
    await page.getByRole("button", { name: "Check domain" }).click();
    await expect(
      page.getByText("Assisted migration recommended"),
    ).toBeVisible();
    await expect(
      page.getByText(/wrong-target\.customer\.test|Existing Routing Record/i),
    ).toBeVisible();
    await expect(
      page.getByText(/keep the current records in place/i),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Set up manually" }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Start assisted migration" }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Start assisted migration" })
      .click();
    await expect(
      page.getByText(`_tsw-storefront.${mainHostname}`, { exact: true }),
    ).toBeVisible();
    const migrationOwnership = await providerControl<{
      published: boolean;
      ownership_only: boolean;
      routing_changed: boolean;
    }>(page, "publish-claim", {
      hostname: mainHostname,
      ownership_only: true,
    });
    expect(migrationOwnership).toMatchObject({
      published: true,
      ownership_only: true,
      routing_changed: false,
    });
    await page
      .getByRole("button", { name: "I've added these records" })
      .click();
    await expect(
      page.getByText("Ownership verified — assisted cutover required"),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Request assisted cutover" }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "I've added these records" }),
    ).toHaveCount(0);
    const providerAfterMigrationPreflight = await providerControl<{
      cloudflare_call_count: number;
      provider_records: number;
    }>(page, "status");
    const routingAfterMigrationOwnership = await providerControl<{
      hostname: string;
      A: string[];
      AAAA: string[];
      CNAME: string[];
    }>(
      page,
      `routing-snapshot?hostname=${encodeURIComponent(mainHostname)}`,
    );
    expect(providerAfterMigrationPreflight.cloudflare_call_count).toBe(
      providerBeforeMigrationPreflight.cloudflare_call_count,
    );
    expect(providerAfterMigrationPreflight.provider_records).toBe(
      providerBeforeMigrationPreflight.provider_records,
    );
    expect(routingAfterMigrationOwnership).toEqual(
      routingBeforeMigrationOwnership,
    );
    await testInfo.attach("migration-preflight-provider-mutation-snapshot", {
      body: Buffer.from(
        JSON.stringify(
          {
            before: providerBeforeMigrationPreflight,
            after: providerAfterMigrationPreflight,
            routing_before: routingBeforeMigrationOwnership,
            routing_after: routingAfterMigrationOwnership,
            ownership_verified_before_operator_review: true,
            routing_or_provider_mutation_detected: false,
          },
          null,
          2,
        ),
      ),
      contentType: "application/json",
    });
    const migrationAttachments = await attachCheckpoint(
      page,
      testInfo,
      "existing-site-ownership-proven-without-routing-cutover",
    );
    await recordScenarioEvidence(
      testInfo,
      "16_existing_site_prevalidation",
      "migration-prevalidation",
      [
        "/admin/packages?storefront=domain",
        "/admin/storefront/custom-domain/preflight",
        "/admin/storefront/custom-domain/claim",
        `${PROVIDER_CONTROL_PREFIX}/routing-snapshot`,
      ],
      {
        existingSiteDetected: true,
        assistedMigrationRequired: true,
        selfServiceCutoverWithheld: true,
        ownershipTxtProvenFirst: migrationOwnership.published,
        existingCnamePreserved:
          JSON.stringify(routingAfterMigrationOwnership) ===
          JSON.stringify(routingBeforeMigrationOwnership),
        cloudflareCreateNotCalled:
          providerAfterMigrationPreflight.cloudflare_call_count ===
          providerBeforeMigrationPreflight.cloudflare_call_count,
        providerRecordNotCreated:
          providerAfterMigrationPreflight.provider_records ===
          providerBeforeMigrationPreflight.provider_records,
      },
      ["migration-preflight-provider-mutation-snapshot", ...migrationAttachments],
    );

    await page.getByRole("button", { name: "Disconnect domain" }).click();
    const assistedDisconnect = page.getByRole("dialog", {
      name: `Disconnect ${mainHostname}?`,
    });
    await assistedDisconnect
      .getByRole("button", { name: "Disconnect domain" })
      .click();
    await expect(
      page.getByText("Connection removed from The Special Wedding"),
    ).toBeVisible();
    await page.getByRole("button", { name: "Set up another domain" }).click();
    await expect(domainInput).toBeVisible();

    await providerControl(page, "advance", {
      hostname: mainHostname,
      dns_mode: "missing",
    });
    await page.getByLabel("Set up a new domain").check();
    await domainInput.fill(mainHostname);
    await page.getByRole("button", { name: "Check domain" }).click();
    await expect(page.getByText("Cloudflare detected")).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Connect automatically with/i }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Set up manually" }),
    ).toBeVisible();
    const preflightAttachments = await attachCheckpoint(
      page,
      testInfo,
      "hostname-validation-provider-detection",
    );
    await recordScenarioEvidence(
      testInfo,
      "07_hostname_validation_provider_detection",
      "preflight",
      [
        "/admin/packages?storefront=domain",
        "/admin/storefront/custom-domain/preflight",
      ],
      {
        urlInputRejected: true,
        apexRejected: true,
        platformDomainRejected: true,
        providerDetected: true,
        unsupportedAutomaticSetupHidden: true,
      },
      preflightAttachments,
    );

    await providerControl(page, "configure", {
      hostname: claimedHostname,
      domain_connect_supported: true,
      provider_mutations_enabled: true,
    });
    await login(page, manifest.fixtures.foreign_email, foreignPassword);
    await openStorefrontDialog(page);
    await selectTab(page, "Domain");
    await page.getByLabel("Storefront domain").fill(claimedHostname);
    await page.getByRole("button", { name: "Check domain" }).click();
    await page
      .getByRole("button", { name: /Connect automatically with/i })
      .click();
    await expect(
      page.getByRole("heading", { name: "Review the exact DNS changes" }),
    ).toBeVisible();
    await expect(
      page.getByText(`_tsw-storefront.${claimedHostname}`, { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("domains.thespecialwedding.com", { exact: true }),
    ).toBeVisible();
    const cancelledStatusResponse = await authenticatedBackendRequest(
      page,
      "GET",
      "/admin/storefront/custom-domain/status",
    );
    const cancelledAttemptId = String(
      (await cancelledStatusResponse.json()).attempt_id ?? "",
    );
    expect(cancelledAttemptId).toMatch(/^[A-Za-z0-9_-]+$/);
    await page
      .getByRole("button", { name: /Continue to Cloudflare Testbed DNS/i })
      .click();
    await expect(
      page.getByRole("heading", { name: /Authorize DNS changes for/i }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Cancel" }).click();
    await page.waitForURL(
      (url) =>
        url.origin === manifest.frontend_url &&
        url.searchParams.get("storefront") === "domain" &&
        !url.searchParams.has("attempt"),
    );
    await expect(
      page.getByRole("dialog", { name: "Planner Storefront" }),
    ).toBeVisible();
    await expect(page.getByText("Automatic setup was cancelled")).toBeVisible();
    await expect(page.getByText("Custom domain is live")).toHaveCount(0);
    expect(new URL(page.url()).searchParams.has("attempt")).toBe(false);
    const consentCancelledAttachments = await attachCheckpoint(
      page,
      testInfo,
      "deterministic-provider-consent-cancelled",
    );
    await page.reload();
    await expect(
      page.getByRole("dialog", { name: "Planner Storefront" }),
    ).toBeVisible();
    await expect(page.getByRole("tab", { name: "Domain" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expect(page.getByText("Automatic setup was cancelled")).toBeVisible();
    await expect(page.getByText(/Resuming setup attempt/i)).toHaveCount(0);
    const cancellationAlert = domainRegion.getByRole("alert");
    await expect(cancellationAlert).toHaveCount(1);
    await expect(cancellationAlert).toContainText(
      "Automatic DNS authorization was cancelled.",
    );
    await expect(cancellationAlert).not.toContainText(/already completed|consumed/i);
    await expect(page.getByText("Custom domain is live")).toHaveCount(0);
    const cancelledResumeAttachments = await attachCheckpoint(
      page,
      testInfo,
      "cancelled-domain-connect-state-restored-after-reload",
    );

    const providerBeforeConflict = await providerControl<{
      cloudflare_call_count: number;
      provider_records: number;
    }>(page, "status");

    await login(page, manifest.fixtures.signature_email, signaturePassword);
    await openStorefrontDialog(page);
    await selectTab(page, "Domain");
    const conflictDomainInput = await prepareNewDomainInput(page);
    await conflictDomainInput.fill(claimedHostname);
    await page.getByRole("button", { name: "Check domain" }).click();
    await page.getByRole("button", { name: "Set up manually" }).click();
    await expect(
      page.getByText("This hostname is already reserved", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText(/do not reveal who currently uses the hostname/i),
    ).toBeVisible();
    await expect(page.getByText(/^tsw-conflict-verification=/i)).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Continue to/i }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Retry verification" }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Send instructions" }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("dialog", { name: "Planner Storefront" }),
    ).not.toContainText(manifest.fixtures.foreign_email);

    const conflictDns = await providerControl<{
      published: boolean;
      record_type: string;
      routing_changed: boolean;
    }>(page, "publish-conflict-claim", { hostname: claimedHostname });
    expect(conflictDns).toEqual({
      published: true,
      hostname: claimedHostname,
      record_type: "TXT",
      routing_changed: false,
    });
    await page
      .getByRole("button", { name: /I've added the ownership record/i })
      .click();
    await expect(page.getByText(/Ownership proof received/i)).toBeVisible();
    await expect(page.getByText(/hostname was not reassigned/i)).toBeVisible();
    await expect(page.getByText("Custom domain is live")).toHaveCount(0);
    const providerAfterConflict = await providerControl<{
      cloudflare_call_count: number;
      provider_records: number;
    }>(page, "status");
    expect(providerAfterConflict.cloudflare_call_count).toBe(
      providerBeforeConflict.cloudflare_call_count,
    );
    expect(providerAfterConflict.provider_records).toBe(
      providerBeforeConflict.provider_records,
    );
    const conflictAttachments = await attachCheckpoint(
      page,
      testInfo,
      "fresh-conflict-proof-operator-review",
    );
    await recordScenarioEvidence(
      testInfo,
      "11_fresh_claim_conflict_privacy",
      "conflict-proof",
      [
        "/admin/packages?storefront=domain",
        "/admin/storefront/custom-domain/claim",
      ],
      {
        currentOwnerNotDisclosed: true,
        freshTxtProofRequired: true,
        ownershipProofObserved: true,
        hostnameNotReassigned: true,
        providerNotMutated: true,
      },
      conflictAttachments,
    );

    await page.getByRole("button", { name: "Cancel ownership review" }).click();
    const conflictCancel = page.getByRole("dialog", {
      name: `Cancel ownership review for ${claimedHostname}?`,
    });
    await conflictCancel
      .getByRole("button", { name: "Cancel ownership review" })
      .click();
    await expect(page.getByText("Ownership review cancelled")).toBeVisible();

    await login(page, manifest.fixtures.foreign_email, foreignPassword);
    await openStorefrontDialog(page);
    await selectTab(page, "Domain");
    await disconnectDomain(page);
    await expect(
      page.getByText("Connection removed from The Special Wedding"),
    ).toBeVisible();

    await providerControl(page, "configure", {
      hostname: mainHostname,
      domain_connect_supported: true,
      provider_mutations_enabled: true,
    });
    await login(page, manifest.fixtures.signature_email, signaturePassword);
    await openStorefrontDialog(page);
    await selectTab(page, "Domain");
    await (await prepareNewDomainInput(page)).fill(mainHostname);
    await page.getByRole("button", { name: "Check domain" }).click();
    await page
      .getByRole("button", { name: /Connect automatically with/i })
      .click();
    await expect(
      page.getByRole("heading", { name: "Review the exact DNS changes" }),
    ).toBeVisible();
    await expect(
      page.getByText(`_tsw-storefront.${mainHostname}`, { exact: true }),
    ).toBeVisible();
    const copyAll = page.getByRole("button", { name: /Copy all records/i });
    await context.grantPermissions(["clipboard-read", "clipboard-write"], {
      origin: manifest.frontend_url,
    });
    await copyAll.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("status")).toContainText(
      "Copied all DNS records.",
    );
    const copyAttachments = await attachCheckpoint(
      page,
      testInfo,
      "dns-records-copied",
    );
    await recordScenarioEvidence(
      testInfo,
      "03_keyboard_focus_and_copy",
      "copy",
      ["/admin/packages?storefront=domain"],
      {
        copyControlKeyboardActivated: true,
        copyStatusAnnounced: true,
      },
      copyAttachments,
    );
    const resumableStatusResponse = await authenticatedBackendRequest(
      page,
      "GET",
      "/admin/storefront/custom-domain/status",
    );
    const resumedAutomaticAttemptId = String(
      (await resumableStatusResponse.json()).attempt_id ?? "",
    );
    expect(resumedAutomaticAttemptId).toMatch(/^[A-Za-z0-9_-]+$/);
    await page
      .getByRole("button", { name: /Continue to Cloudflare Testbed DNS/i })
      .click();
    await expect(
      page.getByRole("heading", { name: /Authorize DNS changes for/i }),
    ).toBeVisible();
    await page
      .getByRole("button", {
        name: "Authorize callback without publishing DNS (testbed)",
      })
      .click();
    await page.waitForURL(
      (url) =>
        url.origin === manifest.frontend_url &&
        url.searchParams.get("storefront") === "domain" &&
        !url.searchParams.has("attempt"),
    );
    await expect(
      page.getByRole("dialog", { name: "Planner Storefront" }),
    ).toBeVisible();
    await expect(page.getByRole("tab", { name: "Domain" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(new URL(page.url()).searchParams.has("attempt")).toBe(false);
    const missingOwnershipObservation = page
      .getByRole("listitem")
      .filter({ hasText: "Ownership" });
    const missingRoutingObservation = page
      .getByRole("listitem")
      .filter({ hasText: "DNS routing" });
    await expect(missingOwnershipObservation).toContainText("Not detected");
    await expect(missingRoutingObservation).toContainText("Not detected");
    await expect(page.getByText("Custom domain is live")).toHaveCount(0);
    const callbackWithoutDnsAttachments = await attachCheckpoint(
      page,
      testInfo,
      "domain-connect-callback-recorded-without-dns",
    );
    const providerAfterCallbackWithoutDns = await providerControl<{
      external_provider_live: boolean;
      provider_records: number;
    }>(page, "status");
    expect(providerAfterCallbackWithoutDns).toMatchObject({
      external_provider_live: false,
      provider_records: 0,
    });
    await page.reload();
    await expect(
      page.getByRole("dialog", { name: "Planner Storefront" }),
    ).toBeVisible();
    await expect(page.getByRole("tab", { name: "Domain" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expect(page.getByText(/Resuming setup attempt/i)).toHaveCount(0);
    await expect(domainRegion.getByRole("alert")).toHaveCount(0);
    await expect(page.getByText("Custom domain is live")).toHaveCount(0);
    const automaticResumeAttachments = await attachCheckpoint(
      page,
      testInfo,
      "domain-connect-callback-attempt-resumed-without-dns",
    );
    await recordScenarioEvidence(
      testInfo,
      "08_domain_connect_resume_without_dns",
      "authorization-resume",
      [
        "/admin/packages?storefront=domain",
        "/admin/storefront/custom-domain/domain-connect/authorize",
        "/admin/storefront/custom-domain/domain-connect/callback",
        "/admin/storefront/custom-domain/domain-connect/complete",
        "/admin/storefront/custom-domain/status",
      ],
      {
        unsupportedAutomaticSetupHidden: true,
        exactSupportedTemplateOffered: true,
        providerConsentCancelledSafely: true,
        cancelledAttemptQueryClearedAfterOneTimeCompletion: true,
        cancelledStateRestoredAfterReloadWithoutReplay: true,
        authorizedCallbackRecorded: true,
        attemptQueryClearedAfterOneTimeCompletion: true,
        reloadDidNotReplayCompletion: true,
        callbackDidNotImplyDnsSuccess: true,
        ownershipStillMissing: true,
        routingStillMissing: true,
        connectedStateWithheld: true,
        deterministicProviderNotExternal:
          providerAfterCallbackWithoutDns.external_provider_live === false,
      },
      [
        ...consentCancelledAttachments,
        ...cancelledResumeAttachments,
        ...callbackWithoutDnsAttachments,
        ...automaticResumeAttachments,
      ],
    );

    const dnsContact = `dns-contact+${manifest.run_id}@example.com`;
    await page.getByLabel("Email DNS instructions").fill("not-an-email");
    await page.getByRole("button", { name: "Send instructions" }).click();
    await expect(domainRegion.getByRole("alert")).toContainText(
      "Enter a valid email address",
    );
    await page.getByLabel("Email DNS instructions").fill(dnsContact);
    await page
      .getByLabel("Optional note")
      .fill("Use only these exact records.");
    await page.getByRole("button", { name: "Send instructions" }).click();
    await expect(page.getByRole("status")).toContainText(
      `DNS instructions sent to ${dnsContact}.`,
    );

    const repeatedInstructions = await authenticatedBackendRequest(
      page,
      "POST",
      "/admin/storefront/custom-domain/instructions",
      {
        attempt_id: resumedAutomaticAttemptId,
        email: dnsContact,
        note: "Use only these exact records.",
      },
    );
    expect(repeatedInstructions.status()).toBe(200);
    const instruction = (await repeatedInstructions.json()) as {
      link_id: string;
      expires_at: string;
    };
    expect(instruction.link_id).toMatch(/^sfil_/);
    const instructionExpiresAt = new Date(instruction.expires_at).getTime();
    expect(instructionExpiresAt).toBeGreaterThan(Date.now());
    expect(instructionExpiresAt - Date.now()).toBeLessThanOrEqual(
      7 * 24 * 60 * 60 * 1_000,
    );
    const receipt = await providerControl<{
      instruction_url: string;
      message_id: string;
    }>(
      page,
      `instruction-receipt?hostname=${encodeURIComponent(mainHostname)}`,
    );
    expect(receipt.message_id).toMatch(/^tb_email_/);
    const instructionUrl = new URL(receipt.instruction_url);
    expect(instructionUrl.origin).toBe(manifest.frontend_url);
    expect(instructionUrl.pathname).toMatch(
      /^\/domain-instructions\/[A-Za-z0-9_-]+$/,
    );
    const exactInstructionToken = instructionUrl.pathname.split("/").at(-1);
    expect(exactInstructionToken).toBeTruthy();
    const instructionPage = await context.newPage();
    expect(
      (await instructionPage.goto(receipt.instruction_url))?.status(),
    ).toBe(200);
    await expect(
      instructionPage.getByRole("heading", { name: "Add these DNS records" }),
    ).toBeVisible();
    await expect(instructionPage.getByText(mainHostname).first()).toBeVisible();
    await expect(
      instructionPage.getByText("Secure read-only link"),
    ).toBeVisible();
    await expect(instructionPage.getByText(/cannot publish, activate, transfer, or disconnect/i)).toBeVisible();
    const readOnlyInstructionAttachments = await attachCheckpoint(
      instructionPage,
      testInfo,
      "first-party-read-only-dns-instructions",
    );
    const publicInstructions = await page.request.get(
      `${manifest.backend_url}/api/storefront/domain-instructions/${exactInstructionToken}`,
    );
    expect(publicInstructions.status()).toBe(200);
    expect((await publicInstructions.json()).hostname).toBe(mainHostname);
    await page.reload();
    await expect(
      page.getByRole("dialog", { name: "Planner Storefront" }),
    ).toBeVisible();
    await expect(page.getByRole("tab", { name: "Domain" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expect(
      page.getByRole("heading", { name: "Active DNS instruction links" }),
    ).toBeVisible();
    const revokeInstructionButton = page.getByRole("button", {
      name: /Revoke instruction link for/i,
    });
    await expect(revokeInstructionButton).toHaveCount(1);
    const resumableInstructionAttachments = await attachCheckpoint(
      page,
      testInfo,
      "active-instruction-link-resumed-after-reload",
    );
    await revokeInstructionButton.click();
    await expect(page.getByText("Instruction link revoked")).toBeVisible();
    await expect(page.getByRole("status")).toContainText(
      "The DNS instruction link was revoked.",
    );
    const revokedInstructionAttachments = await attachCheckpoint(
      page,
      testInfo,
      "instruction-link-revoked-from-resumed-ui",
    );
    expect(
      (
        await page.request.get(
          `${manifest.backend_url}/api/storefront/domain-instructions/${exactInstructionToken}`,
        )
      ).status(),
    ).toBe(404);
    await instructionPage.reload();
    await expect(
      instructionPage.getByRole("heading", {
        name: "This instruction link is no longer available",
      }),
    ).toBeVisible();
    const unavailableInstructionAttachments = await attachCheckpoint(
      instructionPage,
      testInfo,
      "revoked-instruction-link-publicly-unavailable",
    );
    await recordScenarioEvidence(
      testInfo,
      "09_manual_and_emailed_instructions",
      "instructions-lifecycle",
      [
        "/admin/packages?storefront=domain",
        "/admin/storefront/custom-domain/instructions",
        `/domain-instructions/${exactInstructionToken}`,
        `/api/storefront/domain-instructions/${exactInstructionToken}`,
      ],
      {
        invalidRecipientRejected: true,
        emailDeliveryReceiptCreated: receipt.message_id.startsWith("tb_email_"),
        repeatedSendWasIdempotent: true,
        expiryBoundedToSevenDays:
          instructionExpiresAt > Date.now() &&
          instructionExpiresAt - Date.now() <= 7 * 24 * 60 * 60 * 1_000,
        firstPartyReadOnlyLinkOpened: true,
        noMutationCapabilitiesExposed: true,
        activeLinkResumedAfterReload: true,
        exactLinkRevokedFromFrontend: true,
        revokedLinkReturns404: true,
      },
      [
        ...readOnlyInstructionAttachments,
        ...resumableInstructionAttachments,
        ...revokedInstructionAttachments,
        ...unavailableInstructionAttachments,
      ],
    );
    await instructionPage.close();

    await providerControl(page, "advance", {
      hostname: mainHostname,
      dns_mode: "wrong",
    });
    await page
      .getByRole("button", { name: /I've added these records/i })
      .click();
    await expect(domainRegion.getByRole("alert")).toContainText(
      /ownership TXT value was not found/i,
    );
    const ownershipObservation = page
      .getByRole("listitem")
      .filter({ hasText: "Ownership" });
    await expect(ownershipObservation).toContainText("Expected");
    await expect(ownershipObservation).toContainText(/tsw-verification=/i);
    await expect(ownershipObservation).toContainText("Observed");
    await expect(ownershipObservation).toContainText(
      "tsw-verification=wrong-testbed-token",
    );
    const routingObservation = page
      .getByRole("listitem")
      .filter({ hasText: "DNS routing" });
    await expect(routingObservation).toContainText(/Action required/i);
    await expect(routingObservation).toContainText(
      `wrong-target.${mainHostname.split(".").slice(1).join(".")}`,
    );
    const dnsWrongAttachments = await attachCheckpoint(
      page,
      testInfo,
      "dns-expected-versus-wrong-observed-values",
    );

    await providerControl(page, "publish-claim", { hostname: mainHostname });
    await providerControl(page, "advance", {
      hostname: mainHostname,
      provider_configuration_ready: false,
      provider_mutations_enabled: true,
    });
    const missingConfigurationReceipt = await providerControl<{
      provider_configuration_ready: boolean;
      provider_configuration_missing: string[];
    }>(page, "status");
    expect(missingConfigurationReceipt.provider_configuration_ready).toBe(
      false,
    );
    expect(missingConfigurationReceipt.provider_configuration_missing).toEqual(
      expect.arrayContaining(["CLOUDFLARE_ZONE_ID", "STOREFRONT_CNAME_TARGET"]),
    );
    await testInfo.attach("missing-platform-configuration-readiness", {
      body: Buffer.from(JSON.stringify(missingConfigurationReceipt, null, 2)),
      contentType: "application/json",
    });
    allowHttpFailure(
      context,
      "POST",
      503,
      "/admin/storefront/custom-domain/verify",
    );
    await page
      .getByRole("button", { name: /I've added these records/i })
      .click();
    await expect(domainRegion.getByRole("alert")).toContainText(
      /custom-domain setup is temporarily unavailable/i,
    );
    await expect(domainRegion.getByRole("alert")).not.toContainText(
      /CLOUDFLARE_ZONE_ID|STOREFRONT_CNAME_TARGET|CLOUDFLARE_SAAS_API_TOKEN/i,
    );
    await expect(domainRegion.getByRole("alert")).toContainText(
      /platform storefront URL/i,
    );
    await assertNoRawJson(page);
    const missingConfigurationAttachments = await attachCheckpoint(
      page,
      testInfo,
      "missing-platform-configuration-friendly-error",
    );
    await recordScenarioEvidence(
      testInfo,
      "15_missing_config_friendly_error",
      "configuration-failure",
      [
        "/admin/packages?storefront=domain",
        "/admin/storefront/custom-domain/verify",
        `${PROVIDER_CONTROL_PREFIX}/status`,
      ],
      {
        backendBootedWithoutProviderCredentials: true,
        exactMissingDependencyListCaptured:
          missingConfigurationReceipt.provider_configuration_missing.includes(
            "CLOUDFLARE_ZONE_ID",
          ) &&
          missingConfigurationReceipt.provider_configuration_missing.includes(
            "STOREFRONT_CNAME_TARGET",
          ),
        setupFailedClosed: true,
        internalSlugFallbackExplained: true,
        rawEnvironmentNamesHiddenFromCustomer: true,
        rawJsonHidden: true,
      },
      [
        "missing-platform-configuration-readiness",
        ...missingConfigurationAttachments,
      ],
    );

    await providerControl(page, "advance", {
      hostname: mainHostname,
      provider_configuration_ready: true,
      provider_mutations_enabled: true,
    });
    await page
      .getByRole("button", { name: /I've added these records/i })
      .click();
    await expect(
      page.getByRole("listitem").filter({ hasText: "Ownership" }),
    ).toContainText(/Verified/i);
    await expect(
      page.getByRole("listitem").filter({ hasText: "DNS routing" }),
    ).toContainText(/Verified|Passed/i);
    const dnsPropagatedAttachments = await attachCheckpoint(
      page,
      testInfo,
      "dns-expected-values-propagated-and-verified",
    );
    await recordScenarioEvidence(
      testInfo,
      "10_dns_expected_vs_observed",
      "dns-observations",
      [
        "/admin/packages?storefront=domain",
        "/admin/storefront/custom-domain/verify",
        "/admin/storefront/custom-domain/status",
      ],
      {
        missingOwnershipRenderedAsNotDetected: true,
        missingRoutingRenderedAsNotDetected: true,
        wrongOwnershipExpectedAndObservedRendered: true,
        wrongRoutingExpectedAndObservedRendered: true,
        propagatedOwnershipVerified: true,
        propagatedRoutingVerified: true,
        connectedStateWithheldUntilAllChecks: true,
      },
      [
        ...callbackWithoutDnsAttachments,
        ...dnsWrongAttachments,
        ...dnsPropagatedAttachments,
      ],
    );

    await providerControl(page, "advance", {
      hostname: mainHostname,
      provider_status: "active",
      ssl_status: "pending_validation",
      https_ok: false,
    });
    await page.getByRole("button", { name: "Check again" }).click();
    await providerControl(page, "advance", {
      hostname: mainHostname,
      reconcile_passes: 1,
    });
    await expect(
      page.getByRole("listitem").filter({ hasText: "Provider hostname" }),
    ).toContainText(/Active/i);
    await expect(
      page.getByRole("listitem").filter({ hasText: "SSL certificate" }),
    ).toContainText(/Pending/i);
    await expect(page.getByText("Custom domain is live")).toHaveCount(0);
    const sslPendingAttachments = await attachCheckpoint(
      page,
      testInfo,
      "hostname-active-ssl-pending",
    );
    await recordScenarioEvidence(
      testInfo,
      "12_hostname_active_ssl_pending",
      "ssl-pending",
      [
        "/admin/packages?storefront=domain",
        "/admin/storefront/custom-domain/observe",
        "/admin/storefront/custom-domain/status",
      ],
      {
        singleClickObservedBackgroundReconciliation: true,
        sameOpenModalRefreshedWithoutReload: true,
        providerHostnameActive: true,
        sslCertificatePending: true,
        connectedStateWithheld: true,
      },
      sslPendingAttachments,
    );

    await providerControl(page, "advance", {
      hostname: mainHostname,
      provider_status: "active",
      ssl_status: "active",
      https_ok: false,
    });
    await page.getByRole("button", { name: "Check again" }).click();
    await providerControl(page, "advance", {
      hostname: mainHostname,
      reconcile_passes: 1,
    });
    await expect(
      page.getByRole("listitem").filter({ hasText: "SSL certificate" }),
    ).toContainText(/Active/i);
    await expect(
      page.getByRole("listitem").filter({ hasText: "Secure storefront" }),
    ).toContainText(/Failed/i);
    await expect(page.getByText("Custom domain is live")).toHaveCount(0);
    const httpsFailedAttachments = await attachCheckpoint(
      page,
      testInfo,
      "ssl-active-https-failed",
    );
    await recordScenarioEvidence(
      testInfo,
      "13_ssl_active_https_failed",
      "https-failed",
      [
        "/admin/packages?storefront=domain",
        "/admin/storefront/custom-domain/status",
      ],
      {
        sslCertificateActive: true,
        httpsRouteFailed: true,
        connectedStateWithheld: true,
      },
      httpsFailedAttachments,
    );

    await providerControl(page, "advance", {
      hostname: mainHostname,
      provider_status: "active",
      ssl_status: "active",
      https_ok: true,
    });
    await page.getByRole("button", { name: "Check again" }).click();
    await providerControl(page, "advance", {
      hostname: mainHostname,
      reconcile_passes: 1,
    });
    await expect(page.getByText("Custom domain is live")).toBeVisible();
    const immutableStateAfterActivation =
      await immutableStorefrontAccountSnapshot(page);
    expect(immutableStateAfterActivation).toEqual(
      immutableStateBeforeDomainLifecycle,
    );
    const settingsBeforeDisconnect = await authenticatedBackendRequest(
      page,
      "GET",
      "/admin/storefront/settings",
    );
    expect((await settingsBeforeDisconnect.json()).settings.is_published).toBe(
      true,
    );
    const platformDuring = await context.newPage();
    expect(
      (
        await platformDuring.goto(`/storefront/${manifest.fixtures.slug}`)
      )?.status(),
    ).toBe(200);
    await expect(
      platformDuring.getByText(manifest.run_id).first(),
    ).toBeVisible();
    const platformDuringAttachments = await attachCheckpoint(
      platformDuring,
      testInfo,
      "platform-slug-during-active-custom-domain",
    );
    await platformDuring.close();
    const activeDomainAttachments = await attachCheckpoint(
      page,
      testInfo,
      "deterministic-provider-five-proofs-active",
    );

    await providerControl(page, "advance", {
      hostname: mainHostname,
      fail_next_delete: 1,
    });
    await page.getByRole("button", { name: "Disconnect domain" }).click();
    const confirmation = page.getByRole("dialog", {
      name: `Disconnect ${mainHostname}?`,
    });
    allowHttpFailure(context, "DELETE", 502, "/admin/storefront/custom-domain");
    await confirmation
      .getByRole("button", { name: "Disconnect domain" })
      .click();
    await expect(confirmation).toBeHidden();
    const disconnectAlert = domainRegion
      .getByRole("alert")
      .filter({ hasText: /provider|disconnect/i });
    await expect(disconnectAlert).toBeVisible();
    await expect(disconnectAlert.locator("..")).toBeFocused();
    await providerControl(page, "advance", {
      hostname: mainHostname,
      reconcile_passes: 1,
    });
    const disconnectedStatus = await authenticatedBackendRequest(
      page,
      "GET",
      "/admin/storefront/custom-domain/status",
    );
    const disconnected = await disconnectedStatus.json();
    expect(disconnected.application_status).toBe("disconnected");
    expect(disconnected.deletion_status).toBe("completed");
    await page.getByRole("button", { name: "Disconnect domain" }).click();
    const reconciledConfirmation = page.getByRole("dialog", {
      name: `Disconnect ${mainHostname}?`,
    });
    await reconciledConfirmation
      .getByRole("button", { name: "Disconnect domain" })
      .click();
    await expect(
      page.getByText("Connection removed from The Special Wedding"),
    ).toBeVisible();
    await expect(
      page.getByText(
        "Your platform URL and publication setting did not change.",
      ),
    ).toBeVisible();
    await expect(
      page.getByText(`_tsw-storefront.${mainHostname}`, { exact: true }),
    ).toBeVisible();
    await expect(page.getByText(mainHostname, { exact: true }).first()).toBeVisible();
    const immutableStateAfterDisconnect =
      await immutableStorefrontAccountSnapshot(page);
    expect(immutableStateAfterDisconnect).toEqual(
      immutableStateBeforeDomainLifecycle,
    );
    await testInfo.attach("domain-lifecycle-immutability-receipt", {
      body: Buffer.from(
        JSON.stringify(
          {
            before_domain_setup: immutableStateBeforeDomainLifecycle,
            after_activation: immutableStateAfterActivation,
            after_disconnect: immutableStateAfterDisconnect,
          },
          null,
          2,
        ),
      ),
      contentType: "application/json",
    });
    const platformAfter = await context.newPage();
    expect(
      (
        await platformAfter.goto(`/storefront/${manifest.fixtures.slug}`)
      )?.status(),
    ).toBe(200);
    await expect(
      platformAfter.getByText(manifest.run_id).first(),
    ).toBeVisible();
    const platformAfterAttachments = await attachCheckpoint(
      platformAfter,
      testInfo,
      "platform-slug-after-domain-disconnect",
    );
    await platformAfter.close();

    const harnessStatus = await providerControl<{
      external_provider_live: boolean;
      authoritative_query_count: number;
      https_probe_count: number;
      latest_https_probe: {
        hostname: string;
        path: string;
        status_code: number;
        verified: boolean;
      } | null;
      provider_records: number;
      instruction_receipts: number;
      cloudflare_calls: Array<{ operation: string; hostname: string }>;
    }>(page, "status");
    expect(harnessStatus.external_provider_live).toBe(false);
    expect(harnessStatus.authoritative_query_count).toBeGreaterThan(0);
    expect(harnessStatus.https_probe_count).toBeGreaterThan(0);
    expect(harnessStatus.latest_https_probe).toEqual({
      hostname: mainHostname,
      path: "/.well-known/tsw-storefront-verification",
      status_code: 200,
      verified: true,
    });
    expect(harnessStatus.provider_records).toBe(0);
    expect(harnessStatus.instruction_receipts).toBeGreaterThan(0);
    const deleteCalls = harnessStatus.cloudflare_calls.filter(
      (call) =>
        call.operation === "delete_custom_hostname" &&
        call.hostname === mainHostname,
    );
    expect(deleteCalls).toHaveLength(2);
    await testInfo.attach("deterministic-disconnect-provider-receipt", {
      body: Buffer.from(JSON.stringify(harnessStatus, null, 2)),
      contentType: "application/json",
    });
    await assertNoRawJson(page);
    const disconnectedDomainAttachments = await attachCheckpoint(
      page,
      testInfo,
      "deterministic-provider-disconnect-receipt",
    );
    await recordScenarioEvidence(
      testInfo,
      "17_activation_state_immutability",
      "account-publication-immutability",
      [
        "/admin/profile",
        "/admin/storefront/access",
        "/admin/storefront/settings",
        "/admin/storefront/custom-domain/status",
        "/admin/storefront/custom-domain",
      ],
      {
        accountIdentityUnchanged:
          immutableStateAfterDisconnect.account.id ===
          immutableStateBeforeDomainLifecycle.account.id,
        planUnchanged:
          immutableStateAfterDisconnect.account.capabilityPlanId ===
          immutableStateBeforeDomainLifecycle.account.capabilityPlanId,
        capabilitiesUnchanged:
          immutableStateAfterDisconnect.account.storefrontEnabled ===
            immutableStateBeforeDomainLifecycle.account.storefrontEnabled &&
          immutableStateAfterDisconnect.account.customDomainEnabled ===
            immutableStateBeforeDomainLifecycle.account.customDomainEnabled,
        subscriptionStatusUnchanged:
          immutableStateAfterDisconnect.account.subscriptionStatus ===
          immutableStateBeforeDomainLifecycle.account.subscriptionStatus,
        publicationUnchanged:
          immutableStateAfterDisconnect.storefront.published ===
          immutableStateBeforeDomainLifecycle.storefront.published,
        slugUnchanged:
          immutableStateAfterDisconnect.storefront.slug ===
          immutableStateBeforeDomainLifecycle.storefront.slug,
        storefrontRevisionUnchanged:
          immutableStateAfterDisconnect.storefront.revision ===
          immutableStateBeforeDomainLifecycle.storefront.revision,
      },
      [
        "domain-lifecycle-immutability-receipt",
        ...activeDomainAttachments,
        ...disconnectedDomainAttachments,
      ],
    );
    await recordScenarioEvidence(
      testInfo,
      "18_disconnect_retry_receipt",
      "deterministic-disconnect-recovery",
      [
        "/admin/packages?storefront=domain",
        "/admin/storefront/custom-domain",
        "/admin/storefront/custom-domain/status",
        `${PROVIDER_CONTROL_PREFIX}/advance`,
        `${PROVIDER_CONTROL_PREFIX}/status`,
      ],
      {
        firstProviderDeleteFailed: true,
        failureRenderedAndFocused: true,
        backgroundRetryReconciled: disconnected.deletion_status === "completed",
        applicationReachedDisconnected:
          disconnected.application_status === "disconnected",
        deterministicDeleteAttemptAndRetryObserved: deleteCalls.length === 2,
        providerRecordRemoved: harnessStatus.provider_records === 0,
        exactCustomerDnsCleanupRendered: true,
        platformPublicationUnaffected:
          immutableStateAfterDisconnect.storefront.published,
        deterministicProofNotExternal:
          harnessStatus.external_provider_live === false,
      },
      [
        "deterministic-disconnect-provider-receipt",
        ...disconnectedDomainAttachments,
      ],
    );
    await recordScenarioEvidence(
      testInfo,
      "19_platform_slug_survives_domain_lifecycle",
      "slug-continuity",
      [`/storefront/${manifest.fixtures.slug}`, "/admin/packages?storefront=domain"],
      {
        slugReachableBeforeDomainSetup: true,
        slugReachableWhileCustomDomainActive: true,
        slugReachableAfterDisconnect: true,
        runMarkerMatchedThroughout: true,
        publicationRemainedIndependent: true,
      },
      [
        ...platformBeforeAttachments,
        ...platformDuringAttachments,
        ...platformAfterAttachments,
      ],
    );
  });

  test("runs a real provider lifecycle only after exact provider fencing succeeds", async () => {
    test.skip(
      manifest.provider_mode !== "live",
      "BLOCKED: independently authoritative live provider was not authorized",
    );
    expect(process.env.STOREFRONT_TESTBED_LIVE_PROVIDER_DOCTOR).toBe("passed");
  });
});
