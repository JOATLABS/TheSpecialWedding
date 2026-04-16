import { execFileSync } from 'node:child_process';
import path from 'node:path';

import { expect, test } from '@playwright/test';

const ROOT = process.cwd();
const SAMPLE_IMAGE = path.join(ROOT, 'output/playwright/codex-test.png');
const ROOT_ADMIN_EMAIL =
  process.env.PLAYWRIGHT_ROOT_ADMIN_EMAIL ?? 'thedeveloper@thespecialwedding.io';
const ROOT_ADMIN_PASSWORD = process.env.PLAYWRIGHT_ROOT_ADMIN_PASSWORD;
const PLANNER_EMAIL =
  process.env.PLAYWRIGHT_MEDIA_PLANNER_EMAIL ?? 'test_planner2@thespecialwedding.io';
const PLANNER_PASSWORD =
  process.env.PLAYWRIGHT_MEDIA_PLANNER_PASSWORD ?? 'testPass123!';
const PUBLIC_GALLERY_SLUG =
  process.env.PLAYWRIGHT_PUBLIC_GALLERY_SLUG ?? 'james-and-mel';
const GUEST_UPLOAD_PATH =
  process.env.PLAYWRIGHT_GUEST_UPLOAD_PATH ??
  '/james-and-mel/upload/CTRs-7THUiw30jiMrJXqi7HyQTdXgomQOZWJFWxonHg'; // pragma: allowlist secret
const PYTHON =
  process.env.PLAYWRIGHT_FIXTURE_PYTHON ??
  path.join(
    '/Users/emmanuelakinwale/Desktop/WeddingWebApp/.venv',
    process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
  );

async function loginAdmin(page: import('@playwright/test').Page, email: string, password: string) {
  await page.goto('/admin/login');
  await page.getByLabel('Work email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: /log in|sign in/i }).click();
  await page.waitForURL((url) => url.pathname.startsWith('/admin') && url.pathname !== '/admin/login');
}

async function logoutAdmin(page: import('@playwright/test').Page) {
  await page.goto('/admin');
  const logoutButton = page.getByRole('button', { name: /logout/i });
  if (await logoutButton.count()) {
    await logoutButton.click();
    await page.waitForURL(/\/admin\/login/);
  }
}

function cleanupBlogAsset(publicUrl: string | null) {
  if (!publicUrl) return;

  const cleanupScript = `
from urllib.parse import urlparse
import sys

from app.services.media_storage import MediaStorage, StorageTarget

url = sys.argv[1]
key = urlparse(url).path.lstrip("/")
if key:
    MediaStorage().delete_object(StorageTarget.BLOG_ASSETS, key)
`;

  execFileSync(PYTHON, ['-c', cleanupScript, publicUrl], {
    cwd: ROOT,
    env: process.env,
    stdio: 'pipe',
  });
}

test.describe('media storage centralization browser verification', () => {
  test.describe.configure({ mode: 'serial' });

  test('guest memories upload completes from the real public upload flow', async ({ page }) => {
    await page.goto(GUEST_UPLOAD_PATH);
    await page.getByLabel('Your display name').fill('Codex QA');
    await page.getByRole('button', { name: 'Continue' }).click();
    await page.getByRole('button', { name: /Traditional February 13, 2027/i }).click();
    await page.getByRole('button', { name: 'Add media' }).click();

    const guestFileInput = page.locator('input[type="file"]').first();
    await guestFileInput.setInputFiles(SAMPLE_IMAGE);
    await expect(page.getByText(/1 selected/i)).toBeVisible();
    await page.getByRole('button', { name: 'Share with the couple' }).click();
    await expect(page.getByRole('heading', { name: 'Thank you for sharing the moment.' })).toBeVisible();
  });

  test('public gallery loads through the real frontend without gallery API failures', async ({ page }) => {
    const galleryResponses: Array<{ url: string; status: number }> = [];

    page.on('response', (response) => {
      if (response.url().includes('/gallery') && response.request().method() === 'GET') {
        galleryResponses.push({ url: response.url(), status: response.status() });
      }
    });

    await page.goto(`/${PUBLIC_GALLERY_SLUG}/gallery`);
    await expect(page.getByRole('heading', { name: /gallery/i })).toBeVisible();
    await page.waitForTimeout(1500);

    expect(
      galleryResponses.some(
        (response) =>
          response.status === 200 &&
          response.url.includes(`wedding_slug=${PUBLIC_GALLERY_SLUG}`),
      ),
    ).toBeTruthy();
    await expect(page.locator('body')).not.toContainText('Gallery access requires guest verification');
  });

  test('planner gallery upload/manage and profile image upload/delete work from the frontend', async ({ page }) => {
    await loginAdmin(page, PLANNER_EMAIL, PLANNER_PASSWORD);

    await page.goto('/admin/gallery/upload');
    const weddingSelect = page.locator('select').first();
    await expect(weddingSelect).toBeVisible();

    const weddingValue = await weddingSelect.evaluate((select: HTMLSelectElement) => {
      const option = Array.from(select.options).find((item) => item.value);
      return option?.value ?? '';
    });
    expect(weddingValue).toBeTruthy();
    await weddingSelect.selectOption(weddingValue);

    await page.getByRole('button', { name: 'Manage Gallery' }).click();
    await page.waitForTimeout(1000);
    const beforeCount = await page.locator('img[alt^="Gallery image"]').count();

    await page.getByRole('button', { name: 'Upload Images' }).click();
    const galleryFileInput = page.locator('input[type="file"]').first();
    await galleryFileInput.setInputFiles(SAMPLE_IMAGE);
    await expect(page.getByText(/Ready to upload/i)).toBeVisible();
    await page.getByRole('button', { name: /^Upload Images$/ }).nth(1).click();
    await expect(page.getByText(/Successfully uploaded/i)).toBeVisible();

    await page.getByRole('button', { name: 'Manage Gallery' }).click();
    await expect
      .poll(async () => await page.locator('img[alt^="Gallery image"]').count())
      .toBeGreaterThan(beforeCount);

    page.once('dialog', async (dialog) => {
      await dialog.accept();
    });
    await page.getByRole('button', { name: 'Delete' }).first().click({ force: true });
    await expect(page.getByText(/Image deleted successfully/i)).toBeVisible();
    await expect
      .poll(async () => await page.locator('img[alt^="Gallery image"]').count())
      .toBe(beforeCount);

    await page.goto('/admin/profile');
    const profileInput = page.locator('input#profile-image-upload');
    await profileInput.setInputFiles(SAMPLE_IMAGE);
    await expect(page.getByText(/Profile image updated!/i)).toBeVisible();
    await expect(page.getByRole('button', { name: 'Remove' })).toBeVisible();

    page.once('dialog', async (dialog) => {
      await dialog.accept();
    });
    await page.getByRole('button', { name: 'Remove' }).click();
    await expect(page.getByText(/Profile image removed/i)).toBeVisible();
  });

  test('root admin knowledge-base image upload works from the real editor UI', async ({ page }) => {
    test.skip(!ROOT_ADMIN_PASSWORD, 'Set PLAYWRIGHT_ROOT_ADMIN_PASSWORD to verify root-admin KB image uploads.');

    let uploadedCardUrl: string | null = null;

    try {
      await loginAdmin(page, ROOT_ADMIN_EMAIL, ROOT_ADMIN_PASSWORD!);
      await page.goto('/admin/support');
      await page.getByRole('button', { name: 'Knowledge Base' }).click();
      await page.getByRole('button', { name: 'Write Article' }).click();

      await expect(page.getByRole('heading', { name: 'Write New Article' })).toBeVisible();

      const kbCardInput = page.locator('#kb-card-image-upload');
      await kbCardInput.setInputFiles(SAMPLE_IMAGE);

      const kbCardUrlInput = page.locator('#kb-card-image-url');
      await expect
        .poll(async () => await kbCardUrlInput.inputValue(), { timeout: 15000 })
        .toContain('/kb/cards/');
      uploadedCardUrl = await kbCardUrlInput.inputValue();
      await expect(page.locator('img[alt="Card"]')).toBeVisible();
      expect(uploadedCardUrl).toContain('/kb/cards/');
    } finally {
      cleanupBlogAsset(uploadedCardUrl);
      await logoutAdmin(page);
    }
  });
});
