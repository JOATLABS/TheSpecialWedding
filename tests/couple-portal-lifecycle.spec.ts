import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import path from 'node:path';

const ROOT = process.cwd();
const PYTHON = process.env.PLAYWRIGHT_FIXTURE_PYTHON
  ?? (process.env.VIRTUAL_ENV
    ? path.join(
        process.env.VIRTUAL_ENV,
        process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
      )
    : 'python3');
const FIXTURE_SCRIPT = path.join(ROOT, 'scripts/testing/couple_portal_lifecycle_fixture.py');

const FIXTURE = {
  weddingId: process.env.PLAYWRIGHT_FIXTURE_WEDDING_ID ?? 'wedding_1775700014748',
  plannerEmail: process.env.PLAYWRIGHT_FIXTURE_PLANNER_EMAIL ?? 'test_planner2@thespecialwedding.io',
  plannerPassword: process.env.PLAYWRIGHT_FIXTURE_PLANNER_PASSWORD ?? 'testPass123!',
  plannerId: process.env.PLAYWRIGHT_FIXTURE_PLANNER_ID ?? '69d705077174afc30187a408',
  coupleEmail: process.env.PLAYWRIGHT_FIXTURE_COUPLE_EMAIL ?? 'qa_pr2_frontend@thespecialwedding.io',
  couplePassword: process.env.PLAYWRIGHT_FIXTURE_COUPLE_PASSWORD ?? 'QaCouplePass123!!',
  eventLabel: process.env.PLAYWRIGHT_FIXTURE_EVENT_LABEL ?? 'PR2 Timeline Event',
  formTitle: process.env.PLAYWRIGHT_FIXTURE_FORM_TITLE ?? 'PR2 Archived QA Form',
  meetingTitle: process.env.PLAYWRIGHT_FIXTURE_MEETING_TITLE ?? 'PR2 Planning Session',
} as const;

type CoupleState = 'active' | 'archived' | 'owner_cancelled';

function runPythonJson(code: string) {
  const raw = execFileSync(PYTHON, [FIXTURE_SCRIPT, ...code.split('\u0000')], {
    cwd: ROOT,
    encoding: 'utf8',
    env: process.env,
  });
  return JSON.parse(raw.trim() || '{}');
}

function seedFixture(state: CoupleState) {
  return runPythonJson(`seed\u0000--state\u0000${state}\u0000--fixture\u0000${JSON.stringify(FIXTURE)}`) as {
    formId: string;
    meetingId: string;
  };
}

function cleanupFixture() {
  return runPythonJson(`cleanup\u0000--fixture\u0000${JSON.stringify(FIXTURE)}`);
}

async function loginAdmin(page: import('@playwright/test').Page) {
  await page.goto('/admin/login');
  await page.getByLabel('Work email').fill(FIXTURE.plannerEmail);
  await page.getByLabel('Password').fill(FIXTURE.plannerPassword);
  await page.getByRole('button', { name: /log in|sign in/i }).click();
  await page.waitForURL((url) => url.pathname.startsWith('/admin') && url.pathname !== '/admin/login');
}

async function loginCouple(page: import('@playwright/test').Page) {
  await page.goto('/couple/login');
  await page.getByLabel('Email').fill(FIXTURE.coupleEmail);
  await page.getByLabel('Password').fill(FIXTURE.couplePassword);
  await page.getByRole('button', { name: /sign in/i }).click();
  await page.waitForURL(/\/couple\/dashboard/);
}

function coupleRow(page: import('@playwright/test').Page, email: string) {
  return page
    .locator(`p:text-is("${email}")`)
    .locator('xpath=ancestor::div[contains(@class, "rounded-xl")][1]');
}

test.describe('PR2 couple portal lifecycle alignment', () => {
  test.describe.configure({ mode: 'serial' });

  test.afterAll(() => {
    cleanupFixture();
  });

  test('archived couples get read-only dashboard, timeline, and forms UX', async ({ page, browserName }) => {
    test.skip(browserName !== 'chromium', 'Runs once with DB-backed fixture state.');

    const fixture = seedFixture('archived');
    await loginCouple(page);

    await expect(page.getByText('Your archived wedding portal is available in read-only mode.')).toBeVisible();
    await expect(page.getByText('Read-only wedding portal')).toBeVisible();

    await page.getByRole('button', { name: 'Timeline' }).click();
    await expect(page).toHaveURL(/section=timeline/);
    await page.getByRole('button', { name: /View run of show/i }).click();
    await expect(page.getByText('Timeline notes are read-only because this wedding has been archived.')).toBeVisible();
    await expect(page.getByText('Notes are view-only for archived weddings.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Add a note' })).toHaveCount(0);
    await expect(page.getByTitle('Leave a note for your planner')).toHaveCount(0);

    await page.getByRole('button', { name: 'Forms' }).click();
    await expect(page).toHaveURL(/section=forms/);
    await expect(page.getByText('Forms are view-only because this wedding has been archived.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'View Response' })).toBeVisible();

    await page.getByRole('button', { name: 'Meetings' }).click();
    await expect(page).toHaveURL(/section=meetings/);
    await expect(page.getByText('This wedding is archived, so meeting scheduling is paused. Archived portals do not show active meeting links.')).toBeVisible();
    await expect(page.getByText('No active meetings are available for this archived wedding.')).toBeVisible();

    await page.goto(`/couple/forms/${fixture.formId}`);
    await expect(page.getByText('This wedding has been archived. Forms are view-only.')).toBeVisible();
    await expect(page.getByText('This form is view-only. New submissions and edits are disabled for archived weddings.')).toBeVisible();
    await expect(page.getByRole('button', { name: /submit/i })).toHaveCount(0);
  });

  test('meeting destination and admin lifecycle badges match the backend state', async ({ page, browserName }) => {
    test.skip(browserName !== 'chromium', 'Runs once with DB-backed fixture state.');

    seedFixture('active');
    await loginCouple(page);
    await page.goto('/couple/dashboard?section=meetings');
    await expect(page.getByRole('heading', { name: 'Meetings' })).toBeVisible();
    await expect(page.getByText(FIXTURE.meetingTitle)).toBeVisible();
    await expect(page.locator('a[href="https://meet.example.com/pr2-playwright"]')).toBeVisible();

    await loginAdmin(page);
    await page.goto(`/admin/weddings/${FIXTURE.weddingId}`);
    await page.getByRole('button', { name: 'Couple' }).click();
    const activeRow = coupleRow(page, FIXTURE.coupleEmail);
    await expect(activeRow).toContainText(FIXTURE.coupleEmail);
    await expect(activeRow).toContainText('Active');
    await expect(activeRow).toContainText('Revoke Access');

    seedFixture('owner_cancelled');
    await page.reload();
    await page.getByRole('button', { name: 'Couple' }).click();
    const ownerCancelledRow = coupleRow(page, FIXTURE.coupleEmail);
    await expect(ownerCancelledRow).toContainText('Planner Inactive');
    await expect(ownerCancelledRow).toContainText('Planner subscription inactive');
    await expect(ownerCancelledRow.getByRole('button', { name: /Revoke Access/i })).toHaveCount(0);
    await expect(ownerCancelledRow.getByRole('button', { name: /Restore Access/i })).toHaveCount(0);

    seedFixture('archived');
    await page.reload();
    await page.getByRole('button', { name: 'Couple' }).click();
    const archivedRow = coupleRow(page, FIXTURE.coupleEmail);
    await expect(archivedRow).toContainText('Archived Read-Only');
    await expect(archivedRow).toContainText('Archived portal');
    await expect(archivedRow.getByRole('button', { name: /Revoke Access/i })).toHaveCount(0);
    await expect(archivedRow.getByRole('button', { name: /Restore Access/i })).toHaveCount(0);
  });
});
