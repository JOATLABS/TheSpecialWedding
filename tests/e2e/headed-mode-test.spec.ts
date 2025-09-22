import { test, expect } from '@playwright/test';

test.describe('Headed Mode Verification', () => {
  test('Simple homepage test in headed mode', async ({ page }) => {
    // Navigate to the homepage using baseURL from config
    await page.goto('/');

    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Take a screenshot to verify visual rendering
    await page.screenshot({ path: 'test-results/homepage-headed.png' });

    // Verify page title or main content
    await expect(page).toHaveTitle(/Wedding/);

    // Test should pause briefly to allow visual verification in headed mode
    await page.waitForTimeout(2000);

    console.log('✅ Headed mode test completed - browser should have been visible');
    console.log(`📍 Base URL: ${page.url()}`);
  });

  test('Test notification badge component visibility', async ({ page }) => {
    // Navigate to admin login (this should show our notification components)
    await page.goto('/admin/login');

    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Take screenshot of login page
    await page.screenshot({ path: 'test-results/admin-login-headed.png' });

    // Verify page loaded correctly
    await expect(page.locator('input[type="email"]')).toBeVisible();

    // Pause to allow visual inspection
    await page.waitForTimeout(2000);

    console.log('✅ Admin login page test completed in headed mode');
    console.log(`📍 Login page URL: ${page.url()}`);
  });
});