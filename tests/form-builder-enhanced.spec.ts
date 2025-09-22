import { test, expect, Page } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';
const API_URL = 'http://localhost:8000';

// Test credentials
const TEST_USER = {
  email: 'test.verification@example.com',
  password: 'testpassword123!'
};

// Helper function to login
async function loginAsPlanner(page: Page) {
  await page.goto(`${BASE_URL}/admin/login`);
  await page.fill('#email-input', TEST_USER.email);
  await page.fill('#password-input', TEST_USER.password);
  await page.click('#login-button');
  await page.waitForURL('**/admin/**');
}

// Helper function to get auth token for API tests
async function getAuthToken(): Promise<string> {
  const response = await fetch(`${API_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: TEST_USER.email,
      password: TEST_USER.password
    })
  });

  const data = await response.json();
  return data.access_token;
}

test.describe('Form Builder Enhanced Features', () => {

  test.describe('Test 1: Backend API Form Creation with Frontend Verification', () => {

    test('Create forms via API and verify on frontend', async ({ page }) => {
      // Step 1: Get auth token
      const token = await getAuthToken();

      // Step 2: Create a blank form via API
      const blankFormResponse = await fetch(`${API_URL}/admin/forms/from-template/blank_form?form_name=API%20Blank%20Form%20Test`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      expect(blankFormResponse.ok).toBeTruthy();
      const blankFormData = await blankFormResponse.json();
      const blankFormId = blankFormData.id;
      expect(blankFormId).toBeTruthy();

      // Step 3: Create a template-based form via API
      const templateFormResponse = await fetch(`${API_URL}/admin/forms/from-template/wedding_feedback?form_name=API%20Template%20Form%20Test`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      expect(templateFormResponse.ok).toBeTruthy();
      const templateFormData = await templateFormResponse.json();
      const templateFormId = templateFormData.id;
      expect(templateFormId).toBeTruthy();

      // Step 4: Duplicate the blank form via API
      const duplicateFormResponse = await fetch(`${API_URL}/admin/forms/duplicate/${blankFormId}?new_name=API%20Duplicated%20Form%20Test`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      expect(duplicateFormResponse.ok).toBeTruthy();
      const duplicateFormData = await duplicateFormResponse.json();
      const duplicateFormId = duplicateFormData.id;
      expect(duplicateFormId).toBeTruthy();

      // Step 5: Login to frontend
      await loginAsPlanner(page);

      // Step 6: Navigate to forms page
      await page.goto(`${BASE_URL}/admin/forms`);
      await page.waitForSelector('h1:has-text("Form Builder")');

      // Step 7: Verify all three forms appear in the UI
      await expect(page.locator('text=API Blank Form Test')).toBeVisible();
      await expect(page.locator('text=API Template Form Test')).toBeVisible();
      await expect(page.locator('text=API Duplicated Form Test')).toBeVisible();

      // Step 8: Verify form action buttons exist
      await expect(page.locator(`#edit-form-${blankFormId}`)).toBeVisible();
      await expect(page.locator(`#duplicate-form-${blankFormId}`)).toBeVisible();

      // Step 9: Cleanup - Delete the test forms via API
      const deleteIds = [blankFormId, templateFormId, duplicateFormId];
      for (const formId of deleteIds) {
        await fetch(`${API_URL}/admin/forms/${formId}`, {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });
      }
    });
  });

  test.describe('Test 2: Frontend Form Creation with Backend Verification', () => {

    test('Create forms via frontend and verify on backend', async ({ page }) => {
      // Step 1: Login to frontend
      await loginAsPlanner(page);

      // Step 2: Navigate to forms page
      await page.goto(`${BASE_URL}/admin/forms`);
      await page.waitForSelector('h1:has-text("Form Builder")');

      // Test 2.1: Create Blank Form
      await test.step('Create blank form via UI', async () => {
        // Open create modal
        await page.click('#create-form-button');
        await expect(page.locator('h3:has-text("Create New Form")')).toBeVisible();

        // Select blank form option
        await page.click('#creation-type-blank');

        // Enter form name
        await page.fill('#form-name-input', 'UI Blank Form Test');

        // Verify blank form doesn't require template selection
        await expect(page.locator('#template-select')).not.toBeVisible();

        // Create the form
        await page.click('#confirm-create-button');

        // Wait for modal to close and form to appear
        await page.waitForSelector('text=UI Blank Form Test');
      });

      // Test 2.2: Create Template Form
      await test.step('Create template form via UI', async () => {
        // Open create modal
        await page.click('#create-form-button');

        // Select template option
        await page.click('#creation-type-template');

        // Enter form name
        await page.fill('#form-name-input', 'UI Template Form Test');

        // Select a template
        await page.selectOption('#template-select', 'wedding_feedback');

        // Create the form
        await page.click('#confirm-create-button');

        // Wait for form to appear
        await page.waitForSelector('text=UI Template Form Test');
      });

      // Test 2.3: Duplicate Form
      await test.step('Duplicate form via UI', async () => {
        // Find the blank form and click duplicate
        const blankFormCard = page.locator('div:has-text("UI Blank Form Test")').first();
        const duplicateButton = blankFormCard.locator('button:has-text("Duplicate")');
        await duplicateButton.click();

        // Modal should open with duplicate option selected
        await expect(page.locator('h3:has-text("Create New Form")')).toBeVisible();

        // Form name should be pre-filled with "(Copy)"
        const formNameInput = page.locator('#form-name-input');
        await expect(formNameInput).toHaveValue('UI Blank Form Test (Copy)');

        // Change the name
        await formNameInput.fill('UI Duplicated Form Test');

        // Create the duplicate
        await page.click('#confirm-create-button');

        // Wait for duplicated form to appear
        await page.waitForSelector('text=UI Duplicated Form Test');
      });

      // Step 3: Verify via API that all forms were created
      const token = await getAuthToken();

      const formsResponse = await fetch(`${API_URL}/admin/forms`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      expect(formsResponse.ok).toBeTruthy();
      const forms = await formsResponse.json();

      // Verify all three forms exist in backend
      const formNames = forms.map((f: any) => f.name);
      expect(formNames).toContain('UI Blank Form Test');
      expect(formNames).toContain('UI Template Form Test');
      expect(formNames).toContain('UI Duplicated Form Test');

      // Step 4: Verify form types
      const blankForm = forms.find((f: any) => f.name === 'UI Blank Form Test');
      const templateForm = forms.find((f: any) => f.name === 'UI Template Form Test');
      const duplicatedForm = forms.find((f: any) => f.name === 'UI Duplicated Form Test');

      expect(blankForm.template_type).toBe('blank_form');
      expect(templateForm.template_type).toBe('wedding_feedback');
      expect(duplicatedForm.template_type).toContain('duplicate_of_');

      // Step 5: Cleanup - Delete test forms
      await test.step('Cleanup test forms', async () => {
        const testFormIds = [blankForm.id, templateForm.id, duplicatedForm.id];

        for (const formId of testFormIds) {
          await fetch(`${API_URL}/admin/forms/${formId}`, {
            method: 'DELETE',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            }
          });
        }
      });
    });
  });

  test.describe('Edge Cases and Validation', () => {

    test('Validate form creation requirements', async ({ page }) => {
      await loginAsPlanner(page);
      await page.goto(`${BASE_URL}/admin/forms`);

      // Test: Cannot create form without name
      await test.step('Verify name is required', async () => {
        await page.click('#create-form-button');

        // Try to create without entering name
        await page.click('#creation-type-blank');

        // Create button should be disabled
        const createButton = page.locator('#confirm-create-button');
        await expect(createButton).toBeDisabled();

        // Enter name
        await page.fill('#form-name-input', 'Test Form Name');
        await expect(createButton).toBeEnabled();

        await page.click('#cancel-create-button');
      });

      // Test: Template creation requires template selection
      await test.step('Verify template is required for template type', async () => {
        await page.click('#create-form-button');
        await page.click('#creation-type-template');
        await page.fill('#form-name-input', 'Test Template Form');

        // Without selecting template, button should be disabled
        const createButton = page.locator('#confirm-create-button');
        await expect(createButton).toBeDisabled();

        // Select template
        await page.selectOption('#template-select', 'blank_form');
        await expect(createButton).toBeEnabled();

        await page.click('#cancel-create-button');
      });

      // Test: Duplicate requires form selection
      await test.step('Verify form selection for duplicate', async () => {
        await page.click('#create-form-button');
        await page.click('#creation-type-duplicate');
        await page.fill('#form-name-input', 'Test Duplicate Form');

        // Without selecting form, button should be disabled
        const createButton = page.locator('#confirm-create-button');
        await expect(createButton).toBeDisabled();

        await page.click('#cancel-create-button');
      });
    });
  });

  test.describe('Form Actions Integration', () => {

    test('Verify all form actions work correctly', async ({ page }) => {
      const token = await getAuthToken();

      // Create a test form via API
      const createResponse = await fetch(`${API_URL}/admin/forms/from-template/blank_form?form_name=Action%20Test%20Form`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      const formData = await createResponse.json();
      const formId = formData.id;

      // Login and navigate to forms
      await loginAsPlanner(page);
      await page.goto(`${BASE_URL}/admin/forms`);

      // Test: Edit button navigation
      await test.step('Verify edit navigation', async () => {
        await page.click(`#edit-form-${formId}`);
        await expect(page).toHaveURL(new RegExp(`/admin/forms/${formId}/edit`));
        await page.goBack();
      });

      // Test: Duplicate functionality
      await test.step('Verify duplicate functionality', async () => {
        await page.click(`#duplicate-form-${formId}`);

        // Modal should open with duplicate selected
        await expect(page.locator('#creation-type-duplicate')).toHaveClass(/bg-indigo-600/);

        // Form should be pre-selected
        const duplicateSelect = page.locator('#duplicate-form-select');
        await expect(duplicateSelect).toHaveValue(formId);

        // Create duplicate
        await page.fill('#form-name-input', 'Duplicated Action Test Form');
        await page.click('#confirm-create-button');

        // Verify duplicate appears
        await page.waitForSelector('text=Duplicated Action Test Form');
      });

      // Cleanup
      await fetch(`${API_URL}/admin/forms/${formId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      // Delete the duplicate too
      const forms = await fetch(`${API_URL}/admin/forms`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      }).then(r => r.json());

      const duplicate = forms.find((f: any) => f.name === 'Duplicated Action Test Form');
      if (duplicate) {
        await fetch(`${API_URL}/admin/forms/${duplicate.id}`, {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });
      }
    });
  });
});

// Run tests with: npx playwright test tests/form-builder-enhanced.spec.ts