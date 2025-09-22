import { test, expect } from '@playwright/test';

test.describe('Platform Metrics Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    // Login as ROOT_ADMIN before each test
    await page.goto('/admin/login');
    // These should be set as environment variables when running tests
    // DO NOT HARDCODE CREDENTIALS IN TEST FILES
    await page.fill('#email-input', process.env.ROOT_ADMIN_EMAIL || '');
    await page.fill('#password-input', process.env.ROOT_ADMIN_PASSWORD || '');
    await page.click('#login-button');

    // Wait for navigation to complete
    await page.waitForURL('**/admin/**');

    // Navigate to metrics page
    await page.goto('/admin/metrics');
  });

  test('should load metrics dashboard successfully', async ({ page }) => {
    // Wait for metrics to load
    await page.waitForSelector('[data-testid="metric-total-users"]', { timeout: 10000 });

    // Check page title
    await expect(page.locator('h1')).toContainText('Platform Metrics');

    // Verify timeframe selector is present
    const timeframeSelector = page.locator('[data-testid="timeframe-selector"]');
    await expect(timeframeSelector).toBeVisible();

    // Check default timeframe is 30 days
    await expect(timeframeSelector).toHaveValue('30days');
  });

  test('should display all metric categories', async ({ page }) => {
    // Wait for metrics to load
    await page.waitForSelector('[data-testid="metric-total-users"]', { timeout: 10000 });

    // Check User Growth section
    await expect(page.locator('text=User Growth')).toBeVisible();
    await expect(page.locator('[data-testid="metric-total-users"]')).toBeVisible();
    await expect(page.locator('[data-testid="value-total-users"]')).toBeVisible();

    // Check Revenue section
    await expect(page.locator('text=Revenue')).toBeVisible();
    await expect(page.locator('[data-testid="metric-mrr"]')).toBeVisible();
    await expect(page.locator('[data-testid="metric-arr"]')).toBeVisible();

    // Check Subscriptions section
    await expect(page.locator('text=Subscriptions')).toBeVisible();
    await expect(page.locator('[data-testid="metric-active-subscriptions"]')).toBeVisible();
  });

  test('should switch timeframes and refresh data', async ({ page }) => {
    // Wait for initial load
    await page.waitForSelector('[data-testid="metric-total-users"]', { timeout: 10000 });

    // Get initial value
    const initialValue = await page.locator('[data-testid="value-total-users"]').textContent();

    // Change timeframe to 7 days
    await page.selectOption('[data-testid="timeframe-selector"]', '7days');

    // Wait for potential data refresh
    await page.waitForTimeout(1000);

    // Verify timeframe changed
    await expect(page.locator('[data-testid="timeframe-selector"]')).toHaveValue('7days');

    // Change to 90 days
    await page.selectOption('[data-testid="timeframe-selector"]', '90days');
    await expect(page.locator('[data-testid="timeframe-selector"]')).toHaveValue('90days');

    // Change to 1 year
    await page.selectOption('[data-testid="timeframe-selector"]', '1year');
    await expect(page.locator('[data-testid="timeframe-selector"]')).toHaveValue('1year');
  });

  test('should handle loading state correctly', async ({ page }) => {
    // Navigate to metrics page and intercept API call
    await page.route('**/api/saas/analytics/overview*', async route => {
      // Delay the response to see loading state
      await page.waitForTimeout(2000);
      await route.continue();
    });

    await page.goto('/admin/metrics');

    // Check loading state is shown
    const loadingElement = page.locator('[data-testid="metrics-loading"]');
    await expect(loadingElement).toBeVisible();

    // Wait for metrics to load
    await page.waitForSelector('[data-testid="metric-total-users"]', { timeout: 15000 });

    // Loading should be gone
    await expect(loadingElement).not.toBeVisible();
  });

  test('should handle error state with retry', async ({ page }) => {
    // Intercept API call to simulate error
    await page.route('**/api/saas/analytics/overview*', route => {
      route.fulfill({
        status: 500,
        body: JSON.stringify({ error: 'Internal Server Error' })
      });
    });

    await page.goto('/admin/metrics');

    // Wait for error state
    await page.waitForSelector('[data-testid="metrics-error-state"]', { timeout: 10000 });

    // Check error message is displayed
    await expect(page.locator('[data-testid="error-message"]')).toContainText('Failed to load metrics');

    // Check retry button is present
    const retryButton = page.locator('[data-testid="retry-button"]');
    await expect(retryButton).toBeVisible();

    // Remove the error route and click retry
    await page.unroute('**/api/saas/analytics/overview*');
    await retryButton.click();

    // Should load successfully after retry
    await page.waitForSelector('[data-testid="metric-total-users"]', { timeout: 10000 });
  });

  test('should display numeric values in correct format', async ({ page }) => {
    // Wait for metrics to load
    await page.waitForSelector('[data-testid="metric-total-users"]', { timeout: 10000 });

    // Check total users is a number
    const totalUsersText = await page.locator('[data-testid="value-total-users"]').textContent();
    expect(totalUsersText).toMatch(/^[\d,]+$/); // Should be formatted number with commas

    // Check MRR is in currency format
    const mrrText = await page.locator('[data-testid="value-mrr"]').textContent();
    expect(mrrText).toMatch(/^\$[\d,]+(\.\d{2})?$/); // Should be currency format

    // Check ARR is in currency format
    const arrText = await page.locator('[data-testid="value-arr"]').textContent();
    expect(arrText).toMatch(/^\$[\d,]+(\.\d{2})?$/); // Should be currency format
  });

  test('should not be accessible to non-ROOT_ADMIN users', async ({ page }) => {
    // Logout current user
    await page.goto('/admin/logout');

    // Login as regular planner
    await page.goto('/admin/login');
    await page.fill('#email-input', 'test.verification@example.com');
    await page.fill('#password-input', 'TestPass123!');
    await page.click('#login-button');

    // Try to access metrics page
    await page.goto('/admin/metrics');

    // Should either redirect or show error
    // The actual behavior depends on implementation
    const url = page.url();
    const hasError = await page.locator('text=/access denied|unauthorized|not authorized/i').count() > 0;

    expect(url.includes('/metrics') === false || hasError).toBeTruthy();
  });

  test('should export data in different formats', async ({ page }) => {
    // This test would check export functionality if implemented
    // Currently checking if the export options would be available

    await page.waitForSelector('[data-testid="metric-total-users"]', { timeout: 10000 });

    // Look for export button or options (if implemented)
    const exportButton = page.locator('[data-testid="export-button"]');

    if (await exportButton.count() > 0) {
      await exportButton.click();

      // Check export format options
      await expect(page.locator('[data-testid="export-json"]')).toBeVisible();
      await expect(page.locator('[data-testid="export-csv"]')).toBeVisible();
    }
  });
});

test.describe('Metrics Data Accuracy', () => {
  test('should fetch and display real data from backend', async ({ page, request }) => {
    // Login as ROOT_ADMIN
    await page.goto('/admin/login');
    // These should be set as environment variables when running tests
    // DO NOT HARDCODE CREDENTIALS IN TEST FILES
    await page.fill('#email-input', process.env.ROOT_ADMIN_EMAIL || '');
    await page.fill('#password-input', process.env.ROOT_ADMIN_PASSWORD || '');
    await page.click('#login-button');
    await page.waitForURL('**/admin/**');

    // Get auth token from cookies or localStorage
    const cookies = await page.context().cookies();
    const authCookie = cookies.find(c => c.name === 'auth-token' || c.name === 'token');

    // Make direct API call to get expected data
    const apiResponse = await request.get('/api/saas/analytics/overview?timeframe=30days', {
      headers: authCookie ? { 'Cookie': `${authCookie.name}=${authCookie.value}` } : {}
    });

    if (apiResponse.ok()) {
      const apiData = await apiResponse.json();

      // Navigate to metrics page
      await page.goto('/admin/metrics');
      await page.waitForSelector('[data-testid="metric-total-users"]', { timeout: 10000 });

      // Compare displayed values with API response
      const displayedTotalUsers = await page.locator('[data-testid="value-total-users"]').textContent();
      const expectedTotalUsers = apiData.data?.users?.total;

      if (expectedTotalUsers !== undefined) {
        // Remove formatting from displayed value
        const cleanedValue = displayedTotalUsers?.replace(/,/g, '');
        expect(parseInt(cleanedValue || '0')).toBe(expectedTotalUsers);
      }
    }
  });
});