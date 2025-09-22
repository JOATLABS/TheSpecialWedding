const { test, expect } = require('@playwright/test');

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;
const FRONTEND_BASE_URL = process.env.FRONTEND_URL;
const TEST_USER_EMAIL = process.env.TEST_PLANNER_EMAIL;
const TEST_USER_PASSWORD = process.env.TEST_PLANNER_PASSWORD;

let authToken = null;
let testFormId = null;

test.describe('Form UI Integration Tests', () => {
  test.beforeAll(async ({ request }) => {
    // Authenticate and get token
    const response = await request.post(`${API_BASE_URL}/admin/token`, {
      data: {
        email: TEST_USER_EMAIL,
        password: TEST_USER_PASSWORD
      }
    });

    if (response.ok()) {
      const data = await response.json();
      authToken = data.access_token;
    }

    // Create test form via API
    if (authToken) {
      const formResponse = await request.post(
        `${API_BASE_URL}/admin/forms/from-template/wedding_feedback?form_name=Playwright%20UI%20Test%20Form&wedding_id=68ae66c5c30359265c544ca7`,
        {
          headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (formResponse.ok()) {
        const formData = await formResponse.json();
        testFormId = formData.id;
      }
    }
  });

  test.afterAll(async ({ request }) => {
    // Cleanup test form
    if (authToken && testFormId) {
      await request.delete(`${API_BASE_URL}/admin/forms/${testFormId}`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        }
      });
    }
  });

  test('should display forms management page correctly', async ({ page }) => {
    // Navigate to admin forms page
    await page.goto(`${FRONTEND_BASE_URL}/admin/forms`);

    // Check if page loads and contains expected elements
    await expect(page).toHaveTitle(/.*Wedding.*/);

    // Look for key form management elements
    await expect(page.getByText('Form Builder')).toBeVisible();
    await expect(page.getByText('Create New Form')).toBeVisible();
    await expect(page.getByText('Your Forms')).toBeVisible();
  });

  test('should open create form modal and display templates', async ({ page }) => {
    await page.goto(`${FRONTEND_BASE_URL}/admin/forms`);

    // Click create new form button
    await page.getByText('Create New Form').click();

    // Check if modal opens
    await expect(page.getByText('Create New Form')).toBeVisible();
    await expect(page.getByText('Form Name')).toBeVisible();
    await expect(page.getByText('Template')).toBeVisible();

    // Check if template dropdown has options
    const templateSelect = page.locator('select');
    await expect(templateSelect).toBeVisible();

    // Close modal
    await page.getByText('Cancel').click();
  });

  test('should display public form correctly', async ({ page }) => {
    if (!testFormId) {
      test.skip('No test form available');
    }

    // Navigate to public form
    await page.goto(`${FRONTEND_BASE_URL}/forms/${testFormId}`);

    // Check if form loads
    await expect(page.getByText('Playwright UI Test Form')).toBeVisible();

    // Check for form elements
    await expect(page.getByText('Overall Experience Rating')).toBeVisible();
    await expect(page.getByText('Submit')).toBeVisible();

    // Check if form is interactive
    const submitButton = page.getByRole('button', { name: /submit/i });
    await expect(submitButton).toBeVisible();
    await expect(submitButton).toBeEnabled();
  });

  test('should submit public form successfully', async ({ page }) => {
    if (!testFormId) {
      test.skip('No test form available');
    }

    await page.goto(`${FRONTEND_BASE_URL}/forms/${testFormId}`);

    // Fill out form fields
    await page.fill('[placeholder*="name"]', 'Playwright Test User');
    await page.fill('[placeholder*="email"]', 'playwright@test.com');

    // Select rating if available
    const ratingButtons = page.locator('button').filter({ hasText: '★' });
    if (await ratingButtons.count() > 0) {
      await ratingButtons.first().click();
    }

    // Fill textarea if available
    const textareas = page.locator('textarea');
    if (await textareas.count() > 0) {
      await textareas.first().fill('This is a test submission from Playwright');
    }

    // Submit form
    await page.getByRole('button', { name: /submit/i }).click();

    // Check for success message
    await expect(page.getByText('Thank You!')).toBeVisible();
  });

  test('should handle form validation correctly', async ({ page }) => {
    if (!testFormId) {
      test.skip('No test form available');
    }

    await page.goto(`${FRONTEND_BASE_URL}/forms/${testFormId}`);

    // Try to submit without filling required fields
    await page.getByRole('button', { name: /submit/i }).click();

    // Should show validation error or prevent submission
    // Form should still be visible (not submitted)
    await expect(page.getByRole('button', { name: /submit/i })).toBeVisible();
  });

  test('should be responsive on mobile viewport', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    await page.goto(`${FRONTEND_BASE_URL}/admin/forms`);

    // Check if page is still functional on mobile
    await expect(page.getByText('Form Builder')).toBeVisible();
    await expect(page.getByText('Create New Form')).toBeVisible();

    // Check if mobile navigation works
    const createButton = page.getByText('Create New Form');
    await expect(createButton).toBeVisible();
    await createButton.click();

    // Modal should still work on mobile
    await expect(page.getByText('Form Name')).toBeVisible();
  });
});