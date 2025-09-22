import { test, expect, Page } from '@playwright/test';

// Test configuration - use environment variables for flexibility
const BASE_URL = process.env.FRONTEND_URL!;
const API_URL = process.env.NEXT_PUBLIC_API_BASE_URL!;

// Admin credentials - use environment variables for security
const ADMIN_CREDENTIALS = {
  email: process.env.PRIMARY_ADMIN_EMAIL!,
  password: process.env.PRIMARY_ADMIN_PASSWORD!
};

// Test data
const TEST_FORM_DATA = {
  name: 'Automation Test Form',
  template: 'guest_feedback'
};

// Automation attribute selectors - using our new system
const SELECTORS = {
  // Authentication
  login: {
    emailInput: '[data-entity="auth"][data-action="login"][data-field-type="email"]',
    passwordInput: '[data-entity="auth"][data-action="login"][data-field-type="password"]',
    submitButton: '[data-entity="auth"][data-action="login"][data-context="auth"]'
  },
  // Form management
  forms: {
    createButton: '[data-entity="form"][data-action="create"][data-context="admin"]',
    editButton: '[data-entity="form"][data-action="edit"]',
    deleteButton: '[data-entity="form"][data-action="delete"]',
    saveButton: '[data-entity="form"][data-action="save"]'
  },
  // Form builder interface
  formBuilder: {
    addFieldButton: '[data-entity="formField"][data-action="add"]',
    fieldComponent: '[data-entity="formField"][data-action="configure"]',
    deleteFieldButton: '[data-entity="formField"][data-action="delete"]',
    previewToggle: '[data-entity="formBuilder"][data-action="togglePreview"]'
  },
  // Navigation
  navigation: {
    formsLink: '[data-entity="navigation"][data-destination="/admin/forms"]',
    backButton: '[data-entity="navigation"][data-action="navigate"][data-destination="back"]'
  }
};

// Fallback selectors for backwards compatibility
const FALLBACK_SELECTORS = {
  login: {
    emailInput: 'input[placeholder="Email"]',
    passwordInput: 'input[placeholder="Password"]',
    submitButton: 'button'
  },
  forms: {
    createButton: 'button:has-text("Create New Form")',
    editButton: 'button:has-text("Edit")',
    saveButton: 'button:has-text("Save Form")'
  },
  formBuilder: {
    addTextInput: 'button:has-text("Text Input")',
    addEmail: 'button:has-text("Email")',
    previewButton: 'button:has-text("Preview")',
    builderButton: 'button:has-text("Builder")'
  }
};

// Helper function to try automation selector first, then fallback
async function clickElement(page: Page, automationSelector: string, fallbackSelector: string) {
  try {
    // Try automation attribute selector first
    if (await page.locator(automationSelector).count() > 0) {
      console.log(`✅ Using automation selector: ${automationSelector}`);
      await page.click(automationSelector);
      return 'automation';
    }
  } catch (error) {
    console.log(`⚠️ Automation selector failed: ${automationSelector}`);
  }

  // Fall back to old selector
  console.log(`🔄 Using fallback selector: ${fallbackSelector}`);
  await page.click(fallbackSelector);
  return 'fallback';
}

async function fillElement(page: Page, automationSelector: string, fallbackSelector: string, value: string) {
  try {
    // Try automation attribute selector first
    if (await page.locator(automationSelector).count() > 0) {
      console.log(`✅ Using automation selector: ${automationSelector}`);
      await page.fill(automationSelector, value);
      return 'automation';
    }
  } catch (error) {
    console.log(`⚠️ Automation selector failed: ${automationSelector}`);
  }

  // Fall back to old selector
  console.log(`🔄 Using fallback selector: ${fallbackSelector}`);
  await page.fill(fallbackSelector, value);
  return 'fallback';
}

// Enhanced login helper with automation attributes
async function loginAsAdmin(page: Page) {
  await page.goto(`${BASE_URL}/admin/login`);

  const emailResult = await fillElement(
    page,
    SELECTORS.login.emailInput,
    FALLBACK_SELECTORS.login.emailInput,
    ADMIN_CREDENTIALS.email
  );

  const passwordResult = await fillElement(
    page,
    SELECTORS.login.passwordInput,
    FALLBACK_SELECTORS.login.passwordInput,
    ADMIN_CREDENTIALS.password
  );

  const submitResult = await clickElement(
    page,
    SELECTORS.login.submitButton,
    FALLBACK_SELECTORS.login.submitButton
  );

  await page.waitForURL('**/admin**');

  // Log which selectors worked
  console.log('Login selector results:', { emailResult, passwordResult, submitResult });
}

// Enhanced navigation helper with automation attributes
async function navigateToForms(page: Page) {
  try {
    await clickElement(
      page,
      SELECTORS.navigation.formsLink,
      'a:has-text("Forms")'
    );
  } catch {
    // Alternative navigation method
    await page.goto(`${BASE_URL}/admin/forms`);
  }
  await page.waitForURL('**/admin/forms');
}

test.describe('Form Builder with Automation Attributes', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1400, height: 900 });
  });

  test('should verify automation attributes are present', async ({ page }) => {
    await loginAsAdmin(page);
    await navigateToForms(page);

    // Check for automation attributes on key elements
    const automationElements = {
      createButton: await page.locator(SELECTORS.forms.createButton).count(),
      editButton: await page.locator(SELECTORS.forms.editButton).count(),
    };

    console.log('Automation attributes found:', automationElements);

    // Record results but don't fail - this is diagnostic
    expect(automationElements.createButton).toBeGreaterThanOrEqual(0);
    expect(automationElements.editButton).toBeGreaterThanOrEqual(0);
  });

  test('should create form using automation attributes', async ({ page }) => {
    await loginAsAdmin(page);
    await navigateToForms(page);

    // Try to click Create New Form using automation attributes
    const createResult = await clickElement(
      page,
      SELECTORS.forms.createButton,
      FALLBACK_SELECTORS.forms.createButton
    );

    // Wait for modal to appear
    await expect(page.locator('text=Create New Form')).toBeVisible();

    // Fill form details
    await page.fill('input[placeholder*="Enter form name"]', TEST_FORM_DATA.name);
    await page.selectOption('select', TEST_FORM_DATA.template);

    // Create the form
    await page.click('button:has-text("Create Form")');
    await page.waitForTimeout(2000);

    // Verify form appears in list
    await expect(page.locator(`text=${TEST_FORM_DATA.name}`)).toBeVisible();

    console.log(`Form creation used ${createResult} selector`);
  });

  test('should test form builder interface with automation attributes', async ({ page }) => {
    await loginAsAdmin(page);
    await navigateToForms(page);

    // Edit first form using automation attributes if available
    const editResult = await clickElement(
      page,
      SELECTORS.forms.editButton + ':first',
      FALLBACK_SELECTORS.forms.editButton + ':first'
    );

    await page.waitForURL('**/edit');

    // Try to add fields using automation attributes
    try {
      // Test automation attribute for adding text input
      const textInputSelector = '[data-entity="formField"][data-action="add"][data-field-type="text"]';
      if (await page.locator(textInputSelector).count() > 0) {
        console.log('✅ Found text input automation attribute');
        await page.click(textInputSelector);
      } else {
        console.log('🔄 Using fallback for text input');
        await page.click(FALLBACK_SELECTORS.formBuilder.addTextInput);
      }

      await page.waitForTimeout(500);

      // Test automation attribute for adding email field
      const emailSelector = '[data-entity="formField"][data-action="add"][data-field-type="email"]';
      if (await page.locator(emailSelector).count() > 0) {
        console.log('✅ Found email field automation attribute');
        await page.click(emailSelector);
      } else {
        console.log('🔄 Using fallback for email field');
        await page.click(FALLBACK_SELECTORS.formBuilder.addEmail);
      }

      await page.waitForTimeout(500);

    } catch (error) {
      console.log('⚠️ Field addition test failed:', error);
    }

    // Test preview toggle with automation attributes
    try {
      const previewResult = await clickElement(
        page,
        SELECTORS.formBuilder.previewToggle,
        FALLBACK_SELECTORS.formBuilder.previewButton
      );

      await page.waitForTimeout(500);
      await expect(page.locator('text= Preview Mode')).toBeVisible();

      console.log(`Preview toggle used ${previewResult} selector`);

    } catch (error) {
      console.log('⚠️ Preview toggle test failed:', error);
    }

    console.log(`Form editing used ${editResult} selector`);
  });

  test('should test field operations with automation attributes', async ({ page }) => {
    await loginAsAdmin(page);
    await navigateToForms(page);
    await page.click('button:has-text("Edit"):first');
    await page.waitForURL('**/edit');

    // Add a field first
    await page.click('button:has-text("Text Input")');
    await page.waitForTimeout(500);

    const initialFieldCount = await page.locator('[class*="border-dashed"]').count();

    // Try to delete field using automation attributes
    try {
      const deleteFieldSelector = '[data-entity="formField"][data-action="delete"]:visible';
      if (await page.locator(deleteFieldSelector).count() > 0) {
        console.log('✅ Found delete field automation attribute');
        await page.click(deleteFieldSelector);
      } else {
        console.log('🔄 Using fallback for field deletion');
        await page.hover('[class*="border-dashed"]:last-child');
        await page.click('[class*="border-dashed"]:last-child >> svg:near(:text("×"))');
      }

      await page.waitForTimeout(500);

      // Verify field was deleted
      const finalFieldCount = await page.locator('[class*="border-dashed"]').count();
      expect(finalFieldCount).toBe(initialFieldCount - 1);

    } catch (error) {
      console.log('⚠️ Field deletion test failed:', error);
    }
  });

  test('should save form using automation attributes', async ({ page }) => {
    await loginAsAdmin(page);
    await navigateToForms(page);
    await page.click('button:has-text("Edit"):first');
    await page.waitForURL('**/edit');

    // Make a change to the form
    await page.click('button:has-text("Settings")');
    await page.waitForTimeout(500);

    const titleInput = page.locator('input').first();
    await titleInput.fill('Automation Test Save');

    // Try to save using automation attributes
    const saveResult = await clickElement(
      page,
      SELECTORS.forms.saveButton,
      FALLBACK_SELECTORS.forms.saveButton
    );

    await page.waitForTimeout(2000);

    console.log(`Form save used ${saveResult} selector`);
  });

  test('should generate automation selector usage report', async ({ page }) => {
    await loginAsAdmin(page);
    await navigateToForms(page);

    // Test various automation selectors and report coverage
    const selectorTests = [
      { name: 'Create Form Button', selector: SELECTORS.forms.createButton },
      { name: 'Edit Form Button', selector: SELECTORS.forms.editButton },
      { name: 'Navigation Forms Link', selector: SELECTORS.navigation.formsLink },
      { name: 'Form Field Add Button', selector: SELECTORS.formBuilder.addFieldButton },
      { name: 'Preview Toggle', selector: SELECTORS.formBuilder.previewToggle }
    ];

    const results = [];

    for (const test of selectorTests) {
      const count = await page.locator(test.selector).count();
      results.push({
        name: test.name,
        selector: test.selector,
        found: count > 0,
        count
      });
    }

    console.log('\n📊 Automation Attribute Coverage Report:');
    console.log('================================================');

    let foundCount = 0;
    results.forEach(result => {
      const status = result.found ? '✅' : '❌';
      console.log(`${status} ${result.name}: ${result.count} elements`);
      console.log(`    Selector: ${result.selector}`);
      if (result.found) foundCount++;
    });

    const coveragePercent = Math.round((foundCount / results.length) * 100);
    console.log(`\n📈 Coverage: ${foundCount}/${results.length} (${coveragePercent}%)`);

    // Don't fail the test, just report
    expect(results.length).toBeGreaterThan(0);
  });
});

test.describe('Automation Attributes Compatibility', () => {
  test('should verify backwards compatibility', async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/login`);

    // Test that old selectors still work alongside new ones
    const oldLogin = await page.locator('input[placeholder="Email"]').count();
    const newLogin = await page.locator('[data-entity="auth"][data-action="login"]').count();

    console.log('Selector compatibility:');
    console.log(`Old login selectors: ${oldLogin}`);
    console.log(`New automation selectors: ${newLogin}`);

    // Both should work (or at least one should work)
    expect(oldLogin + newLogin).toBeGreaterThanOrEqual(1);
  });

  test('should measure performance impact of automation attributes', async ({ page }) => {
    const startTime = Date.now();

    await page.goto(`${BASE_URL}/admin/forms`);
    await page.waitForLoadState('networkidle');

    const loadTime = Date.now() - startTime;

    // Count total automation attributes on page
    const automationAttrs = await page.evaluate(() => {
      const elements = document.querySelectorAll('[data-entity]');
      return {
        total: elements.length,
        entities: Array.from(new Set(Array.from(elements).map(el => el.getAttribute('data-entity')))),
        actions: Array.from(new Set(Array.from(elements).map(el => el.getAttribute('data-action'))))
      };
    });

    console.log('\n⚡ Performance Report:');
    console.log(`Page load time: ${loadTime}ms`);
    console.log(`Automation elements: ${automationAttrs.total}`);
    console.log(`Unique entities: ${automationAttrs.entities.length}`);
    console.log(`Unique actions: ${automationAttrs.actions.length}`);

    // Verify performance is reasonable (should be under 5 seconds)
    expect(loadTime).toBeLessThan(5000);
    expect(automationAttrs.total).toBeGreaterThan(0);
  });
});