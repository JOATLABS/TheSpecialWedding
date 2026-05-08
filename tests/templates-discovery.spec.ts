import { test, expect } from '@playwright/test';

test.use({
  baseURL: process.env.TEST_BASE_URL || 'http://localhost:3000',
});

test.describe('Templates discovery surfaces', () => {
  test('SaasNav exposes a Free templates link from the homepage', async ({ page }) => {
    await page.goto('/');

    const navLink = page.getByRole('link', { name: 'Free templates' }).first();
    await expect(navLink).toBeVisible();

    await navLink.click();
    await expect(page).toHaveURL(/\/resources\/templates$/);
  });

  test('Resources hub renders a templates tile that drives clicks to /resources/templates', async ({ page }) => {
    await page.goto('/resources');

    const tile = page.getByTestId('resources-templates-tile');
    await expect(tile).toBeVisible();

    await tile.click();
    await expect(page).toHaveURL(/\/resources\/templates$/);
  });
});
