import { copyFileSync, existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import path from 'node:path';

import { config as loadDotEnv } from 'dotenv';
import { expect, test } from '@playwright/test';

const ROOT = process.cwd();
loadDotEnv({ path: path.join(ROOT, '.env') });
const SAMPLE_IMAGE = path.join(ROOT, 'output/playwright/codex-test.png');
const SAMPLE_IMAGE_REPLACEMENT = path.join(ROOT, 'output/playwright/codex-test-replace.png');
const VENDOR_FIXTURE_SCRIPT = path.join(ROOT, 'scripts/testing/vendor_ad_media_fixture.py');
const ROOT_ADMIN_EMAIL =
  process.env.ROOT_ADMIN_EMAIL ?? 'thedeveloper@thespecialwedding.io';
const ROOT_ADMIN_PASSWORD = process.env.ROOT_ADMIN_PASSWORD;
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
const DEFAULT_VENDOR_FIXTURE = {
  email: 'qa_vendor_media@thespecialwedding.io',
  password: 'QaVendorMediaPass123!', // pragma: allowlist secret
  businessName: 'QA Vendor Media',
  vendorCategory: 'photographer',
  vendorLocation: 'Austin, TX',
  campaignName: 'QA Vendor Media Draft Campaign',
};
const VENDOR_FIXTURE_JSON =
  process.env.PLAYWRIGHT_VENDOR_AD_FIXTURE_JSON ?? JSON.stringify(DEFAULT_VENDOR_FIXTURE);
const VENDOR_FIXTURE_CONFIG = JSON.parse(VENDOR_FIXTURE_JSON) as typeof DEFAULT_VENDOR_FIXTURE;

interface VendorFixtureSeed {
  ok: boolean;
  email: string;
  password: string;
  vendorId: string;
  campaignId: string;
}

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

async function loginVendor(page: import('@playwright/test').Page, email: string, password: string) {
  await page.goto('/portal/ads');
  await page.locator('input[type="email"]').fill(email);
  await page.locator('input[type="password"]').first().fill(password);
  await page.getByRole('button', { name: 'Sign In' }).click();
  await page.waitForURL((url) => url.pathname.startsWith('/portal/ads') && url.pathname !== '/portal/ads/signup');
  await expect(page.getByRole('button', { name: 'User menu' })).toBeVisible({ timeout: 15000 });
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible({ timeout: 15000 });
}

async function logoutVendor(page: import('@playwright/test').Page) {
  await page.goto('/portal/ads');
  await page.getByRole('button', { name: /sign out/i }).click();
  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible();
}

function ensureVendorReplacementImage() {
  if (!existsSync(SAMPLE_IMAGE_REPLACEMENT)) {
    copyFileSync(SAMPLE_IMAGE, SAMPLE_IMAGE_REPLACEMENT);
  }
}

function runVendorFixture(action: 'seed' | 'cleanup') {
  const args = [VENDOR_FIXTURE_SCRIPT, action, '--fixture', VENDOR_FIXTURE_JSON];
  const output = execFileSync(PYTHON, args, {
    cwd: ROOT,
    env: process.env,
    stdio: 'pipe',
    encoding: 'utf8',
  });
  return JSON.parse(output) as VendorFixtureSeed | { ok: boolean };
}

function cleanupBlogAssets(publicUrls: Array<string | null>) {
  const urls = publicUrls.filter((value): value is string => Boolean(value));
  if (urls.length === 0) return;

  const cleanupScript = `
from urllib.parse import urlparse
import sys

from app.services.media_storage import MediaStorage, StorageTarget

storage = MediaStorage()
for url in sys.argv[1:]:
    key = urlparse(url).path.lstrip("/")
    if key:
        storage.delete_object(StorageTarget.BLOG_ASSETS, key)
`;

  execFileSync(PYTHON, ['-c', cleanupScript, ...urls], {
    cwd: ROOT,
    env: process.env,
    stdio: 'pipe',
  });
}

async function waitForSurfaceToFinishLoading(page: import('@playwright/test').Page) {
  const loadingIndicator = page.getByText('Loading...');
  if (await loadingIndicator.count()) {
    await loadingIndicator.first().waitFor({ state: 'hidden', timeout: 15000 });
  }
}

test.describe('media storage centralization browser verification', () => {
  test.describe.configure({ mode: 'serial' });
  let vendorFixture: VendorFixtureSeed | null = null;

  test.beforeAll(() => {
    ensureVendorReplacementImage();
    vendorFixture = runVendorFixture('seed') as VendorFixtureSeed;
  });

  test.afterAll(() => {
    runVendorFixture('cleanup');
  });

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

    try {
      await page.goto('/admin/gallery/upload');
      await waitForSurfaceToFinishLoading(page);
      const weddingSelect = page.locator('select').first();
      await expect(weddingSelect).toBeVisible();

      await expect
        .poll(async () => {
          return await weddingSelect.evaluate((select: HTMLSelectElement) => {
            const option = Array.from(select.options).find((item) => item.value);
            return option?.value ?? '';
          });
        }, {
          timeout: 15000,
        })
        .not.toBe('');
      const selectedWeddingValue = await weddingSelect.evaluate((select: HTMLSelectElement) => {
        const option = Array.from(select.options).find((item) => item.value);
        return option?.value ?? '';
      });
      await weddingSelect.selectOption(selectedWeddingValue);

      await page.getByRole('button', { name: 'Manage Gallery' }).click();
      await waitForSurfaceToFinishLoading(page);
      const beforeCount = await page.locator('img[alt^="Gallery image"]').count();

      await page.getByRole('button', { name: 'Upload Images' }).click();
      const galleryFileInput = page.locator('input[type="file"]').first();
      await galleryFileInput.setInputFiles(SAMPLE_IMAGE);
      await expect(page.getByText(/Ready to upload/i)).toBeVisible();
      await page.getByRole('button', { name: /^Upload Images$/ }).nth(1).click();

      await page.getByRole('button', { name: 'Manage Gallery' }).click();
      await waitForSurfaceToFinishLoading(page);
      await expect
        .poll(async () => await page.locator('img[alt^="Gallery image"]').count(), {
          timeout: 15000,
        })
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
    } finally {
      await logoutAdmin(page);
    }
  });

  test('root admin knowledge-base card and og image uploads work from the real editor UI', async ({ page }) => {
    test.skip(!ROOT_ADMIN_PASSWORD, 'Set ROOT_ADMIN_PASSWORD to verify root-admin KB image uploads.');

    let uploadedCardUrl: string | null = null;
    let uploadedOgUrl: string | null = null;

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

      const kbOgInput = page.locator('#kb-og-image-upload');
      await kbOgInput.setInputFiles(SAMPLE_IMAGE);
      const kbOgUrlInput = page.locator('#kb-og-image-url');
      await expect
        .poll(async () => await kbOgUrlInput.inputValue(), { timeout: 15000 })
        .toContain('/kb/og/');
      uploadedOgUrl = await kbOgUrlInput.inputValue();
      await expect(page.locator('img[alt="OG"]')).toBeVisible();
      expect(uploadedOgUrl).toContain('/kb/og/');
    } finally {
      cleanupBlogAssets([uploadedCardUrl, uploadedOgUrl]);
      await logoutAdmin(page);
    }
  });

  test('root admin blog card and og image uploads work from the real editor UI', async ({ page }) => {
    test.skip(!ROOT_ADMIN_PASSWORD, 'Set ROOT_ADMIN_PASSWORD to verify root-admin blog image uploads.');

    let uploadedCardUrl: string | null = null;
    let uploadedOgUrl: string | null = null;

    try {
      await loginAdmin(page, ROOT_ADMIN_EMAIL, ROOT_ADMIN_PASSWORD!);
      await page.goto('/admin/support');
      await page.getByRole('button', { name: 'Blog' }).click();
      await page.getByRole('button', { name: 'New Article' }).click();

      await expect(page.getByRole('heading', { name: 'New Blog Article' })).toBeVisible();

      const blogCardInput = page.locator('#blog-card-image-upload');
      await blogCardInput.setInputFiles(SAMPLE_IMAGE);
      const blogCardUrlInput = page.locator('#blog-card-image-url');
      await expect
        .poll(async () => await blogCardUrlInput.inputValue(), { timeout: 15000 })
        .toContain('/blog/cards/');
      uploadedCardUrl = await blogCardUrlInput.inputValue();
      await expect(page.locator('img[alt="Card"]')).toBeVisible();
      expect(uploadedCardUrl).toContain('/blog/cards/');

      const blogOgInput = page.locator('#blog-og-image-upload');
      await blogOgInput.setInputFiles(SAMPLE_IMAGE);
      const blogOgUrlInput = page.locator('#blog-og-image-url');
      await expect
        .poll(async () => await blogOgUrlInput.inputValue(), { timeout: 15000 })
        .toContain('/blog/og/');
      uploadedOgUrl = await blogOgUrlInput.inputValue();
      await expect(page.locator('img[alt="OG"]')).toBeVisible();
      expect(uploadedOgUrl).toContain('/blog/og/');
    } finally {
      cleanupBlogAssets([uploadedCardUrl, uploadedOgUrl]);
      await logoutAdmin(page);
    }
  });

  test('vendor creatives upload, replace, and persist from the shared creatives workspace', async ({ page }) => {
    test.skip(!vendorFixture, 'Vendor media fixture did not seed correctly.');
    const initialHeadline = `QA Creative ${Date.now()}`;
    const updatedHeadline = `${initialHeadline} Updated`;

    await loginVendor(page, vendorFixture!.email, vendorFixture!.password);
    try {
      await page.goto('/portal/ads/creatives');
      await expect(page.getByRole('heading', { level: 1, name: 'Creatives' })).toBeVisible();
      await expect(page.getByText('Image URL', { exact: true })).toHaveCount(0);
      await page.getByRole('button', { name: 'New Creative' }).click();
      await expect(page.getByRole('heading', { level: 3, name: 'New Creative' })).toBeVisible();
      const createForm = page
        .getByRole('heading', { level: 3, name: 'New Creative' })
        .locator('xpath=ancestor::div[contains(@class,"rounded-2xl")]')
        .first();

      await page.locator('#vendor-creative-image-upload').setInputFiles(SAMPLE_IMAGE);
      await expect(page.getByRole('button', { name: 'Replace Image' })).toBeVisible();

      const createTextInputs = createForm.locator('input[type="text"]');
      await createTextInputs.nth(0).fill(initialHeadline);
      await createForm.locator('textarea').fill('Shared uploader creative coverage for the vendor portal.');
      await createForm.getByRole('button', { name: 'Create' }).click();
      await expect(page.getByText(/Creative created/i)).toBeVisible({ timeout: 15000 });

      const initialCardHeading = page.getByRole('heading', { name: initialHeadline }).first();
      await expect(initialCardHeading).toBeVisible();
      const initialCard = initialCardHeading
        .locator('xpath=ancestor::div[contains(@class,"rounded-2xl")]')
        .first();
      const initialSrc = await initialCard.locator('img').getAttribute('src');

      await initialCard.getByRole('button', { name: /edit/i }).click();
      await expect(page.getByRole('heading', { level: 3, name: 'Edit Creative' })).toBeVisible();
      const editForm = page
        .getByRole('heading', { level: 3, name: 'Edit Creative' })
        .locator('xpath=ancestor::div[contains(@class,"rounded-2xl")]')
        .first();
      await page.locator('#vendor-creative-image-upload').setInputFiles(SAMPLE_IMAGE_REPLACEMENT);
      await editForm.locator('input[type="text"]').nth(0).fill(updatedHeadline);
      await editForm.getByRole('button', { name: 'Update' }).click();
      await expect(page.getByText(/Creative updated/i)).toBeVisible({ timeout: 15000 });

      const updatedCardHeading = page.getByRole('heading', { name: updatedHeadline }).first();
      await expect(updatedCardHeading).toBeVisible({ timeout: 15000 });
      const updatedCard = updatedCardHeading
        .locator('xpath=ancestor::div[contains(@class,"rounded-2xl")]')
        .first();
      const updatedSrc = await updatedCard.locator('img').getAttribute('src');

      expect(initialSrc).toBeTruthy();
      expect(updatedSrc).toBeTruthy();
      expect(updatedSrc).not.toBe(initialSrc);
      expect(updatedSrc).toContain(`/ads/${vendorFixture!.vendorId}/`);

      await page.reload();
      await expect(page.getByRole('heading', { name: updatedHeadline }).first()).toBeVisible();
      await expect(updatedCard.locator('img')).toHaveAttribute('src', updatedSrc!);
    } finally {
      await logoutVendor(page);
    }
  });

  test('vendor campaign wizard uploads and persists campaign creative media', async ({ page }) => {
    test.skip(!vendorFixture, 'Vendor media fixture did not seed correctly.');
    const campaignName = `QA Wizard Campaign ${Date.now()}`;
    const creativeHeadline = `QA Wizard Creative ${Date.now()}`;

    await loginVendor(page, vendorFixture!.email, vendorFixture!.password);
    try {
      await page.goto('/portal/ads/campaigns/new');
      await expect(page.getByRole('heading', { name: 'Create New Campaign' })).toBeVisible();
      await page.getByPlaceholder('e.g. Spring Wedding Photography Special').fill(campaignName);
      await page.getByRole('button', { name: /^Next$/ }).click();
      await page.getByRole('button', { name: /^Next$/ }).click();

      await expect(page.getByRole('heading', { name: 'Ad Creative' })).toBeVisible();
      await expect(page.getByText('Image URL', { exact: true })).toHaveCount(0);
      await page.locator('#vendor-campaign-creative-image-upload').setInputFiles(SAMPLE_IMAGE);
      await expect(page.getByRole('button', { name: 'Replace Image' })).toBeVisible();
      await page.getByPlaceholder('e.g. Award-Winning Wedding Photography').fill(creativeHeadline);
      await page.getByPlaceholder('Describe your services in 2-3 sentences').fill(
        'Wizard flow coverage for vendor ad creative uploads.',
      );

      await page.getByRole('button', { name: /^Next$/ }).click();
      await page.getByRole('button', { name: /^Next$/ }).click();
      await page.getByRole('button', { name: /^Next$/ }).click();
      await expect(page.getByRole('heading', { name: 'Review & Submit' })).toBeVisible();
      await page.getByRole('button', { name: 'Save as Draft' }).click();

      await page.waitForURL((url) => url.pathname === '/portal/ads/campaigns');
      await expect(page.getByRole('heading', { name: campaignName })).toBeVisible();

      await page.goto('/portal/ads/creatives');
      await page.locator('select').first().selectOption({ label: campaignName });
      const wizardCreativeHeading = page.getByRole('heading', { name: creativeHeadline }).first();
      await expect(wizardCreativeHeading).toBeVisible();
      const wizardCreativeCard = wizardCreativeHeading
        .locator('xpath=ancestor::div[contains(@class,"rounded-2xl")]')
        .first();
      const wizardCreativeSrc = await wizardCreativeCard.locator('img').getAttribute('src');
      expect(wizardCreativeSrc).toContain(`/ads/${vendorFixture!.vendorId}/`);

      await page.reload();
      await page.locator('select').first().selectOption({ label: campaignName });
      await expect(page.getByRole('heading', { name: creativeHeadline }).first()).toBeVisible();
      await expect(wizardCreativeCard.locator('img')).toHaveAttribute('src', wizardCreativeSrc!);
    } finally {
      await logoutVendor(page);
    }
  });

  test('vendor settings upload, replace, remove, and persist the business logo without a raw URL field', async ({ page }) => {
    test.skip(!vendorFixture, 'Vendor media fixture did not seed correctly.');

    await loginVendor(page, vendorFixture!.email, vendorFixture!.password);
    try {
      await page.goto('/portal/ads/settings');
      await expect(page.getByRole('heading', { name: 'Business Profile' })).toBeVisible();
      await expect(page.getByText('Logo URL', { exact: true })).toHaveCount(0);

      await page.locator('#vendor-logo-image-upload').setInputFiles(SAMPLE_IMAGE);
      const logoPreview = page.getByAltText(VENDOR_FIXTURE_CONFIG.businessName);
      await expect(logoPreview).toBeVisible();
      await expect
        .poll(async () => await logoPreview.getAttribute('src'), { timeout: 15000 })
        .toContain(`/vendor-profiles/${vendorFixture!.vendorId}/logo/`);
      const firstLogoSrc = await logoPreview.getAttribute('src');
      await page.getByRole('button', { name: 'Save Profile' }).click();
      await expect(page.getByText(/Profile updated successfully/i)).toBeVisible();

      await page.reload();
      const reloadedLogoPreview = page.getByAltText(VENDOR_FIXTURE_CONFIG.businessName);
      await expect(reloadedLogoPreview).toBeVisible();
      await expect(reloadedLogoPreview).toHaveAttribute('src', firstLogoSrc!);

      await page.locator('#vendor-logo-image-upload').setInputFiles(SAMPLE_IMAGE_REPLACEMENT);
      const replacedLogoPreview = page.getByAltText(VENDOR_FIXTURE_CONFIG.businessName);
      await expect
        .poll(async () => await replacedLogoPreview.getAttribute('src'), { timeout: 15000 })
        .not.toBe(firstLogoSrc);
      const secondLogoSrc = await replacedLogoPreview.getAttribute('src');
      expect(secondLogoSrc).not.toBe(firstLogoSrc);
      await page.getByRole('button', { name: 'Save Profile' }).click();
      await expect(page.getByText(/Profile updated successfully/i)).toBeVisible();

      await page.reload();
      await expect(page.getByAltText(VENDOR_FIXTURE_CONFIG.businessName)).toHaveAttribute(
        'src',
        secondLogoSrc!,
      );

      await page.getByRole('button', { name: 'Remove' }).click();
      await page.getByRole('button', { name: 'Save Profile' }).click();
      await expect(page.getByText(/Profile updated successfully/i)).toBeVisible();

      await page.reload();
      await expect(page.getByAltText(VENDOR_FIXTURE_CONFIG.businessName)).toHaveCount(0);
      await expect(page.getByText('Upload your business logo')).toBeVisible();
    } finally {
      await logoutVendor(page);
    }
  });
});
