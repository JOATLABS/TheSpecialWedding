const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

function loadEnv(file) {
  const out = {};
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) {
      continue;
    }
    const idx = trimmed.indexOf('=');
    out[trimmed.slice(0, idx)] = trimmed.slice(idx + 1);
  }
  return out;
}

function allTruePermissions() {
  return {
    manage_guests: true,
    manage_budget: true,
    manage_gallery: true,
    manage_seating: true,
    manage_vendors: true,
    send_rsvp: true,
    send_reminders: true,
    manage_forms: true,
    view_analytics: true,
    manage_wedding_settings: true,
    manage_contracts: true,
    manage_packages: true,
    manage_couple_portal: true,
    message_couples: true,
  };
}

const EDITOR_PRESET = {
  manage_guests: true,
  manage_budget: true,
  manage_gallery: true,
  manage_seating: true,
  manage_vendors: false,
  send_rsvp: false,
  send_reminders: false,
  manage_forms: true,
  view_analytics: true,
  manage_wedding_settings: false,
  manage_contracts: false,
  manage_packages: false,
  manage_couple_portal: true,
  message_couples: false,
};

const VIEWER_PRESET = {
  manage_guests: false,
  manage_budget: false,
  manage_gallery: false,
  manage_seating: false,
  manage_vendors: false,
  send_rsvp: false,
  send_reminders: false,
  manage_forms: false,
  view_analytics: true,
  manage_wedding_settings: false,
  manage_contracts: false,
  manage_packages: false,
  manage_couple_portal: false,
  message_couples: false,
};

async function waitForAppReady(url, timeoutMs = 15000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        return;
      }
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`App not ready at ${url}`);
}

async function apiLogin(apiBase, email, password) {
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const response = await fetch(`${apiBase}/admin/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    if (response.ok) {
      return (await response.json()).access_token;
    }

    if (response.status === 429 && attempt < 3) {
      const retryAfter = Number(response.headers.get('retry-after') || '2');
      await new Promise((resolve) => setTimeout(resolve, retryAfter * 1000));
      continue;
    }

    throw new Error(
      `Login failed for ${email}: ${response.status} ${await response.text()}`
    );
  }

  throw new Error(`Login failed for ${email}: exhausted retries`);
}

async function apiGet(apiBase, pathname, token) {
  const response = await fetch(`${apiBase}${pathname}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error(
      `GET ${pathname} failed: ${response.status} ${await response.text()}`
    );
  }
  return response.json();
}

async function apiPatch(apiBase, pathname, token, body) {
  const response = await fetch(`${apiBase}${pathname}`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(
      `PATCH ${pathname} failed: ${response.status} ${await response.text()}`
    );
  }
  return response.json();
}

async function hasLink(page, href) {
  return (await page.locator(`a[href="${href}"]`).count()) > 0;
}

async function textVisible(page, text) {
  const locator = page.getByText(text, { exact: true }).first();
  try {
    return await locator.isVisible({ timeout: 1500 });
  } catch {
    return false;
  }
}

function getPagePath(page) {
  try {
    return new URL(page.url()).pathname;
  } catch {
    return '';
  }
}

async function waitForPathChange(page, fromPath, timeoutMs = 30000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (getPagePath(page) !== fromPath) {
      return;
    }
    await page.waitForTimeout(500);
  }

  throw new Error(`Timed out waiting to leave ${fromPath}; still on ${getPagePath(page)}`);
}

async function openAuthenticatedAdminPage(browser, appBase, accessToken) {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1100 },
  });
  await context.addCookies([
    {
      name: 'admin_token',
      value: accessToken,
      url: appBase,
      httpOnly: true,
      sameSite: 'Strict',
    },
  ]);
  await context.addInitScript((token) => {
    window.__TSW_ADMIN_AUTH_TOKEN__ = token;
    window.__TSW_ADMIN_REMEMBER_ME__ = true;
  }, accessToken);
  const page = await context.newPage();
  await page.waitForTimeout(2500);
  await page.goto(`${appBase}/admin/planner`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);
  return { context, page };
}

async function main() {
  const env = {
    ...process.env,
    ...loadEnv(path.join(process.cwd(), '.env')),
  };
  const apiBase = process.env.TEAM_MATRIX_API_BASE || 'http://127.0.0.1:8000';
  const appBase = process.env.TEAM_MATRIX_APP_BASE || 'http://127.0.0.1:3001';
  const plannerEmail = env.TEST_PLANNER_WITH_PACKAGE_EMAIL;
  const plannerPassword = env.TEST_PLANNER_WITH_PACKAGE_PASSWORD;
  const teamEmail =
    process.env.TEAM_MATRIX_EMAIL || 'browser.matrix.team@thespecialwedding.io';
  const teamPassword =
    process.env.TEAM_MATRIX_PASSWORD || 'BrowserMatrix123!';
  const outputDir = path.join(
    process.cwd(),
    'output',
    'playwright',
    'team-permission-matrix'
  );
  fs.mkdirSync(outputDir, { recursive: true });

  await waitForAppReady(`${appBase}/admin/login`);

  const plannerToken = await apiLogin(apiBase, plannerEmail, plannerPassword);
  const teamToken = await apiLogin(apiBase, teamEmail, teamPassword);
  const weddings = await apiGet(apiBase, '/admin/planner/weddings', plannerToken);
  const memberPayload = await apiGet(apiBase, '/admin/team/members', plannerToken);
  const teamMembers = memberPayload.members || memberPayload;
  const teamMember = teamMembers.find((member) => member.email === teamEmail);

  if (!teamMember) {
    throw new Error(`Team member fixture not found for ${teamEmail}`);
  }

  let weddingWithCouple = null;
  let weddingWithoutCouple = null;

  for (const wedding of weddings) {
    const couples = await apiGet(
      apiBase,
      `/admin/couple-portal/couples?wedding_id=${encodeURIComponent(wedding._id)}`,
      plannerToken
    );
    if (!weddingWithCouple && couples.count > 0) {
      weddingWithCouple = wedding;
    }
    if (!weddingWithoutCouple && couples.count === 0) {
      weddingWithoutCouple = wedding;
    }
  }

  if (!weddingWithCouple || !weddingWithoutCouple) {
    throw new Error(
      'Need one wedding with a couple and one without to run the permission matrix'
    );
  }

  const browser = await chromium.launch({ headless: true });

  const scenarios = [
    {
      name: 'owner-baseline',
      session: 'planner',
      run: async (page) => {
        const out = {};
        out.hasWeddingsNav = await hasLink(page, '/admin/weddings');
        out.hasCommunicationsNav = await hasLink(page, '/admin/communications');
        await page.goto(`${appBase}/admin/weddings/${weddingWithCouple._id}`, {
          waitUntil: 'domcontentloaded',
        });
        await page.waitForTimeout(3000);
        out.hasCoupleTab =
          (await page.getByRole('button', { name: 'Couple' }).count()) > 0;
        if (out.hasCoupleTab) {
          await page.getByRole('button', { name: 'Couple' }).click();
          await page.waitForTimeout(500);
        }
        out.hasCoupleAccessSection = await textVisible(page, 'Couple Access');
        await page.screenshot({
          path: path.join(outputDir, 'owner-baseline.png'),
          fullPage: true,
        });
        return out;
      },
      expect: (result) =>
        result.hasWeddingsNav &&
        result.hasCommunicationsNav &&
        result.hasCoupleTab &&
        result.hasCoupleAccessSection,
    },
    {
      name: 'team-admin-default',
      patch: {
        role: 'admin',
        custom_permissions: allTruePermissions(),
        wedding_access: 'all',
        assigned_wedding_ids: [],
      },
      session: 'team',
      run: async (page) => {
        const out = {};
        out.hasWeddingsNav = await hasLink(page, '/admin/weddings');
        out.hasCommunicationsNav = await hasLink(page, '/admin/communications');
        await page.goto(`${appBase}/admin/weddings/${weddingWithCouple._id}`, {
          waitUntil: 'domcontentloaded',
        });
        await page.waitForTimeout(3000);
        out.hasCoupleTab =
          (await page.getByRole('button', { name: 'Couple' }).count()) > 0;
        await page.goto(`${appBase}/admin/communications/inbox`, {
          waitUntil: 'domcontentloaded',
        });
        await page.waitForTimeout(2000);
        out.inboxDenied = await textVisible(page, 'No inbox access');
        out.hasCoupleConversation = await textVisible(page, 'James & Mel');
        await page.screenshot({
          path: path.join(outputDir, 'team-admin-default.png'),
          fullPage: true,
        });
        return out;
      },
      expect: (result) =>
        result.hasWeddingsNav &&
        result.hasCommunicationsNav &&
        result.hasCoupleTab &&
        !result.inboxDenied &&
        result.hasCoupleConversation,
    },
    {
      name: 'team-editor-default',
      patch: {
        role: 'editor',
        custom_permissions: EDITOR_PRESET,
        wedding_access: 'all',
        assigned_wedding_ids: [],
      },
      session: 'team',
      run: async (page) => {
        const out = {};
        out.hasWeddingsNav = await hasLink(page, '/admin/weddings');
        out.hasCommunicationsNav = await hasLink(page, '/admin/communications');
        await page.goto(`${appBase}/admin/weddings/${weddingWithCouple._id}`, {
          waitUntil: 'domcontentloaded',
        });
        await page.waitForTimeout(3000);
        out.hasCoupleTab =
          (await page.getByRole('button', { name: 'Couple' }).count()) > 0;
        await page.goto(`${appBase}/admin/communications/inbox`, {
          waitUntil: 'domcontentloaded',
        });
        await page.waitForTimeout(2000);
        out.inboxDenied = await textVisible(page, 'No inbox access');
        await page.screenshot({
          path: path.join(outputDir, 'team-editor-default.png'),
          fullPage: true,
        });
        return out;
      },
      expect: (result) =>
        result.hasWeddingsNav &&
        !result.hasCommunicationsNav &&
        result.hasCoupleTab &&
        result.inboxDenied,
    },
    {
      name: 'team-viewer-default',
      patch: {
        role: 'viewer',
        custom_permissions: VIEWER_PRESET,
        wedding_access: 'all',
        assigned_wedding_ids: [],
      },
      session: 'team',
      run: async (page) => {
        const out = {};
        out.hasWeddingsNav = await hasLink(page, '/admin/weddings');
        out.hasCommunicationsNav = await hasLink(page, '/admin/communications');
        await page.goto(`${appBase}/admin/weddings`, {
          waitUntil: 'domcontentloaded',
        });
        await page.waitForTimeout(2000);
        out.weddingsDenied = await textVisible(page, 'Failed to load weddings');
        await page.goto(`${appBase}/admin/weddings/${weddingWithCouple._id}`, {
          waitUntil: 'domcontentloaded',
        });
        await page.waitForTimeout(2500);
        out.weddingDetailDenied =
          (await textVisible(page, 'Failed to load wedding details')) ||
          (await textVisible(page, 'Wedding Not Found'));
        await page.screenshot({
          path: path.join(outputDir, 'team-viewer-default.png'),
          fullPage: true,
        });
        return out;
      },
      expect: (result) =>
        !result.hasWeddingsNav &&
        !result.hasCommunicationsNav &&
        result.weddingsDenied &&
        result.weddingDetailDenied,
    },
    {
      name: 'wedding-settings-only',
      patch: {
        role: 'viewer',
        custom_permissions: {
          ...VIEWER_PRESET,
          view_analytics: false,
          manage_wedding_settings: true,
        },
        wedding_access: 'all',
        assigned_wedding_ids: [],
      },
      session: 'team',
      run: async (page) => {
        const out = {};
        out.hasWeddingsNav = await hasLink(page, '/admin/weddings');
        out.hasCommunicationsNav = await hasLink(page, '/admin/communications');
        await page.goto(`${appBase}/admin/weddings`, {
          waitUntil: 'domcontentloaded',
        });
        await page.waitForTimeout(2000);
        out.hasProgramButton = await textVisible(page, 'Program');
        await page.goto(`${appBase}/admin/weddings/${weddingWithCouple._id}`, {
          waitUntil: 'domcontentloaded',
        });
        await page.waitForTimeout(2500);
        out.hasCoupleTab =
          (await page.getByRole('button', { name: 'Couple' }).count()) > 0;
        await page.screenshot({
          path: path.join(outputDir, 'wedding-settings-only.png'),
          fullPage: true,
        });
        return out;
      },
      expect: (result) =>
        result.hasWeddingsNav &&
        !result.hasCommunicationsNav &&
        !result.hasProgramButton &&
        !result.hasCoupleTab,
    },
    {
      name: 'guest-communications-only',
      patch: {
        role: 'viewer',
        custom_permissions: {
          ...VIEWER_PRESET,
          view_analytics: false,
          send_reminders: true,
        },
        wedding_access: 'all',
        assigned_wedding_ids: [],
      },
      session: 'team',
      run: async (page) => {
        const out = {};
        out.hasWeddingsNav = await hasLink(page, '/admin/weddings');
        out.hasCommunicationsNav = await hasLink(page, '/admin/communications');
        await page.goto(`${appBase}/admin/communications/inbox`, {
          waitUntil: 'domcontentloaded',
        });
        await page.waitForTimeout(2000);
        out.hasCoupleConversation = await textVisible(page, 'James & Mel');
        out.hasInvitesTab =
          (await page.locator('a[href="/admin/communications/invites"]').count()) > 0;
        out.hasRemindersTab =
          (await page.locator('a[href="/admin/communications/reminders"]').count()) > 0;
        out.hasIndividualTab =
          (await page.locator('a[href="/admin/communications/individual"]').count()) > 0;
        out.hasHistoryTab =
          (await page.locator('a[href="/admin/communications/history"]').count()) > 0;
        await page.goto(`${appBase}/admin/communications/invites`, {
          waitUntil: 'domcontentloaded',
        });
        await page.waitForTimeout(1200);
        out.invitesRestricted = await textVisible(page, 'Access restricted');
        await page.screenshot({
          path: path.join(outputDir, 'guest-communications-only.png'),
          fullPage: true,
        });
        return out;
      },
      expect: (result) =>
        !result.hasWeddingsNav &&
        result.hasCommunicationsNav &&
        !result.hasCoupleConversation &&
        !result.hasInvitesTab &&
        result.hasRemindersTab &&
        result.hasIndividualTab &&
        result.hasHistoryTab &&
        result.invitesRestricted,
    },
    {
      name: 'couple-messaging-only',
      patch: {
        role: 'viewer',
        custom_permissions: {
          ...VIEWER_PRESET,
          view_analytics: false,
          message_couples: true,
        },
        wedding_access: 'all',
        assigned_wedding_ids: [],
      },
      session: 'team',
      run: async (page) => {
        const out = {};
        out.hasWeddingsNav = await hasLink(page, '/admin/weddings');
        out.hasCommunicationsNav = await hasLink(page, '/admin/communications');
        await page.goto(`${appBase}/admin/communications/inbox`, {
          waitUntil: 'domcontentloaded',
        });
        await page.waitForTimeout(2000);
        out.hasCoupleConversation = await textVisible(page, 'James & Mel');
        out.hasInvitesTab =
          (await page.locator('a[href="/admin/communications/invites"]').count()) > 0;
        out.hasRemindersTab =
          (await page.locator('a[href="/admin/communications/reminders"]').count()) > 0;
        out.hasIndividualTab =
          (await page.locator('a[href="/admin/communications/individual"]').count()) > 0;
        out.hasHistoryTab =
          (await page.locator('a[href="/admin/communications/history"]').count()) > 0;
        await page.goto(`${appBase}/admin/communications/invites`, {
          waitUntil: 'domcontentloaded',
        });
        await page.waitForTimeout(1200);
        out.invitesRestricted = await textVisible(page, 'Access restricted');
        await page.screenshot({
          path: path.join(outputDir, 'couple-messaging-only.png'),
          fullPage: true,
        });
        return out;
      },
      expect: (result) =>
        !result.hasWeddingsNav &&
        result.hasCommunicationsNav &&
        result.hasCoupleConversation &&
        !result.hasInvitesTab &&
        !result.hasRemindersTab &&
        !result.hasIndividualTab &&
        !result.hasHistoryTab &&
        result.invitesRestricted,
    },
    {
      name: 'assigned-only-couple-team',
      patch: {
        role: 'viewer',
        custom_permissions: {
          ...VIEWER_PRESET,
          view_analytics: false,
          manage_couple_portal: true,
          message_couples: true,
        },
        wedding_access: 'assigned',
        assigned_wedding_ids: [weddingWithoutCouple.id || weddingWithoutCouple._id],
      },
      session: 'team',
      run: async (page) => {
        const out = {};
        out.hasWeddingsNav = await hasLink(page, '/admin/weddings');
        out.hasCommunicationsNav = await hasLink(page, '/admin/communications');
        await page.goto(`${appBase}/admin/weddings`, {
          waitUntil: 'domcontentloaded',
        });
        await page.waitForTimeout(2000);
        out.seesAssignedWedding = await textVisible(
          page,
          weddingWithoutCouple.couple_names
        );
        out.seesUnassignedWedding = await textVisible(
          page,
          weddingWithCouple.couple_names
        );
        await page.goto(`${appBase}/admin/weddings/${weddingWithCouple._id}`, {
          waitUntil: 'domcontentloaded',
        });
        await page.waitForTimeout(2500);
        out.unassignedWeddingDenied =
          (await textVisible(page, 'Failed to load wedding details')) ||
          (await textVisible(page, 'Wedding Not Found'));
        await page.goto(`${appBase}/admin/communications/inbox`, {
          waitUntil: 'domcontentloaded',
        });
        await page.waitForTimeout(2000);
        out.hasCoupleConversation = await textVisible(page, 'James & Mel');
        await page.screenshot({
          path: path.join(outputDir, 'assigned-only-couple-team.png'),
          fullPage: true,
        });
        return out;
      },
      expect: (result) =>
        result.hasWeddingsNav &&
        result.hasCommunicationsNav &&
        result.seesAssignedWedding &&
        !result.seesUnassignedWedding &&
        result.unassignedWeddingDenied &&
        !result.hasCoupleConversation,
    },
  ];

  const results = [];

  try {
    for (const scenario of scenarios) {
      const result = {
        name: scenario.name,
        passed: false,
        details: null,
        error: null,
      };

      try {
        if (scenario.patch) {
          await apiPatch(
            apiBase,
            `/admin/team/members/${teamMember.id || teamMember._id}`,
            plannerToken,
            scenario.patch
          );
        }

        const { context, page } = await openAuthenticatedAdminPage(
          browser,
          appBase,
          scenario.session === 'planner' ? plannerToken : teamToken
        );

        try {
          const details = await scenario.run(page);
          result.details = details;
          result.passed = scenario.expect(details);
        } finally {
          await context.close();
        }
      } catch (error) {
        result.error = error instanceof Error ? error.message : String(error);
      }

      results.push(result);
    }
  } finally {
    await browser.close();
  }

  const outputPath = path.join(outputDir, 'results.json');
  fs.writeFileSync(outputPath, JSON.stringify(results, null, 2));
  console.log(JSON.stringify(results, null, 2));

  if (results.some((result) => !result.passed)) {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
