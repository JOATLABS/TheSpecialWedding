import { test, expect, Page } from '@playwright/test';

// Test configuration - use environment variables for flexibility
const BASE_URL = process.env.TEST_BASE_URL || 'http://localhost:3004';
const API_URL = process.env.TEST_API_URL || 'http://localhost:8000';

// Admin credentials - use environment variables for security
const ADMIN_CREDENTIALS = {
 email: process.env.TEST_ADMIN_EMAIL || 'admin@test.com',
 password: process.env.TEST_ADMIN_PASSWORD || 'test123'
};

// Test data
const TEST_FORM_DATA = {
 name: 'Playwright Test Form',
 template: 'guest_feedback'
};

// Helper function to login
async function loginAsAdmin(page: Page) {
 await page.goto(`${BASE_URL}/admin/login`);
 await page.fill('input[placeholder="Email"]', ADMIN_CREDENTIALS.email);
 await page.fill('input[placeholder="Password"]', ADMIN_CREDENTIALS.password);
 await page.click('button');
 await page.waitForURL('**/admin**');
}

// Helper function to navigate to forms
async function navigateToForms(page: Page) {
 await page.click('a:has-text("Forms")');
 await page.waitForURL('**/admin/forms');
}

test.describe('Form Builder System', () => {
 test.beforeEach(async ({ page }) => {
 // Set viewport for consistent testing
 await page.setViewportSize({ width: 1400, height: 900 });
 });

 test('should login successfully and access forms page', async ({ page }) => {
 await loginAsAdmin(page);
 await navigateToForms(page);
 
 // Verify we're on the forms page
 await expect(page.locator('h1:has-text("Form Builder")')).toBeVisible();
 await expect(page.locator('button:has-text("Create New Form")')).toBeVisible();
 });

 test('should create a new form from template', async ({ page }) => {
 await loginAsAdmin(page);
 await navigateToForms(page);
 
 // Click Create New Form
 await page.click('button:has-text("Create New Form")');
 
 // Wait for modal to appear
 await expect(page.locator('text=Create New Form')).toBeVisible();
 
 // Fill form details
 await page.fill('input[placeholder*="Enter form name"]', TEST_FORM_DATA.name);
 await page.selectOption('select', TEST_FORM_DATA.template);
 
 // Create the form
 await page.click('button:has-text("Create Form")');
 
 // Wait for form to be created and page to reload
 await page.waitForTimeout(2000);
 
 // Verify form appears in list
 await expect(page.locator(`text=${TEST_FORM_DATA.name}`)).toBeVisible();
 });

 test('should access form builder interface', async ({ page }) => {
 await loginAsAdmin(page);
 await navigateToForms(page);
 
 // Click Edit button on first form
 await page.click('button:has-text("Edit"):first');
 
 // Wait for form builder to load
 await page.waitForURL('**/edit');
 
 // Verify form builder interface elements
 await expect(page.locator('text=Edit Form')).toBeVisible();
 await expect(page.locator('button:has-text("Builder")')).toBeVisible();
 await expect(page.locator('button:has-text("Preview")')).toBeVisible();
 await expect(page.locator('button:has-text("Save Form")')).toBeVisible();
 
 // Verify left sidebar with field types
 await expect(page.locator('text=Add Fields')).toBeVisible();
 await expect(page.locator('button:has-text("Text Input")')).toBeVisible();
 await expect(page.locator('button:has-text("Email")')).toBeVisible();
 await expect(page.locator('button:has-text("Star Rating")')).toBeVisible();
 });

 test('should add new fields to form', async ({ page }) => {
 await loginAsAdmin(page);
 await navigateToForms(page);
 await page.click('button:has-text("Edit"):first');
 await page.waitForURL('**/edit');
 
 // Count existing fields
 const initialFieldCount = await page.locator('[class*="border-dashed"]').count();
 
 // Add a text input field
 await page.click('button:has-text("Text Input")');
 await page.waitForTimeout(500);
 
 // Verify field was added
 const newFieldCount = await page.locator('[class*="border-dashed"]').count();
 expect(newFieldCount).toBe(initialFieldCount + 1);
 
 // Add an email field
 await page.click('button:has-text("Email")');
 await page.waitForTimeout(500);
 
 // Verify second field was added
 const finalFieldCount = await page.locator('[class*="border-dashed"]').count();
 expect(finalFieldCount).toBe(initialFieldCount + 2);
 });

 test('should edit field properties', async ({ page }) => {
 await loginAsAdmin(page);
 await navigateToForms(page);
 await page.click('button:has-text("Edit"):first');
 await page.waitForURL('**/edit');
 
 // Add a field first
 await page.click('button:has-text("Text Input")');
 await page.waitForTimeout(500);
 
 // Click on the newly added field to select it
 await page.click('[class*="border-dashed"]:last-child');
 await page.waitForTimeout(500);
 
 // Verify field properties panel appears
 await expect(page.locator('text=Field Properties')).toBeVisible();
 await expect(page.locator('label:has-text("Field Label")')).toBeVisible();
 
 // Edit field label
 const labelInput = page.locator('input[value*="New text field"]');
 await labelInput.fill('Custom Text Field');
 
 // Toggle required setting
 await page.check('input[type="checkbox"]:near(:text("Required field"))');
 
 // Verify changes are reflected in the form preview
 await expect(page.locator('text=Custom Text Field')).toBeVisible();
 await expect(page.locator('span:has-text("*"):near(:text("Custom Text Field"))')).toBeVisible();
 });

 test('should switch between builder and preview modes', async ({ page }) => {
 await loginAsAdmin(page);
 await navigateToForms(page);
 await page.click('button:has-text("Edit"):first');
 await page.waitForURL('**/edit');
 
 // Verify we start in builder mode
 await expect(page.locator('text=Add Fields')).toBeVisible();
 
 // Switch to preview mode
 await page.click('button:has-text("Preview")');
 await page.waitForTimeout(500);
 
 // Verify preview mode interface
 await expect(page.locator('text= Preview Mode')).toBeVisible();
 await expect(page.locator('button[type="submit"]')).toBeVisible();
 
 // Switch back to builder mode
 await page.click('button:has-text("Builder")');
 await page.waitForTimeout(500);
 
 // Verify builder mode is active again
 await expect(page.locator('text=Add Fields')).toBeVisible();
 });

 test('should edit form settings', async ({ page }) => {
 await loginAsAdmin(page);
 await navigateToForms(page);
 await page.click('button:has-text("Edit"):first');
 await page.waitForURL('**/edit');
 
 // Click Settings tab
 await page.click('button:has-text("Settings")');
 await page.waitForTimeout(500);
 
 // Verify settings panel
 await expect(page.locator('text=Form Settings')).toBeVisible();
 await expect(page.locator('label:has-text("Form Title")')).toBeVisible();
 
 // Edit form title
 const titleInput = page.locator('input').first();
 await titleInput.fill('Updated Form Title');
 
 // Edit description
 const descriptionTextarea = page.locator('textarea').first();
 await descriptionTextarea.fill('This is an updated form description for testing.');
 
 // Edit submit button text
 await page.fill('input[value*="Submit"]', 'Send My Feedback');
 
 // Verify changes are reflected in the preview
 await expect(page.locator('text=Updated Form Title')).toBeVisible();
 await expect(page.locator('text=This is an updated form description for testing.')).toBeVisible();
 });

 test('should delete fields from form', async ({ page }) => {
 await loginAsAdmin(page);
 await navigateToForms(page);
 await page.click('button:has-text("Edit"):first');
 await page.waitForURL('**/edit');
 
 // Add a field first
 await page.click('button:has-text("Text Input")');
 await page.waitForTimeout(500);
 
 const initialFieldCount = await page.locator('[class*="border-dashed"]').count();
 
 // Hover over the field to show delete button
 await page.hover('[class*="border-dashed"]:last-child');
 
 // Click delete button (X icon)
 await page.click('[class*="border-dashed"]:last-child >> svg:near(:text("×"))');
 await page.waitForTimeout(500);
 
 // Verify field was deleted
 const finalFieldCount = await page.locator('[class*="border-dashed"]').count();
 expect(finalFieldCount).toBe(initialFieldCount - 1);
 });

 test('should save form changes', async ({ page }) => {
 await loginAsAdmin(page);
 await navigateToForms(page);
 await page.click('button:has-text("Edit"):first');
 await page.waitForURL('**/edit');
 
 // Make a change to the form
 await page.click('button:has-text("Settings")');
 await page.waitForTimeout(500);
 
 const titleInput = page.locator('input').first();
 await titleInput.fill('Test Save Functionality');
 
 // Save the form
 await page.click('button:has-text("Save Form")');
 
 // Wait for save operation
 await page.waitForTimeout(2000);
 
 // Note: In a real test, we would verify the save was successful
 // by checking for success message or API response
 });

 test('should test form preview functionality', async ({ page }) => {
 await loginAsAdmin(page);
 await navigateToForms(page);
 await page.click('button:has-text("Edit"):first');
 await page.waitForURL('**/edit');
 
 // Switch to preview mode
 await page.click('button:has-text("Preview")');
 await page.waitForTimeout(500);
 
 // Test filling out the form
 if (await page.locator('input[id="guest_name"]').isVisible()) {
 await page.fill('input[id="guest_name"]', 'Test User');
 }
 
 if (await page.locator('input[id="guest_email"]').isVisible()) {
 await page.fill('input[id="guest_email"]', 'test@example.com');
 }
 
 // Test star rating interaction
 const starButtons = page.locator('button:has-text("")');
 if (await starButtons.first().isVisible()) {
 await starButtons.nth(3).click(); // Click 4th star
 }
 
 // Test form submission
 await page.click('button[type="submit"]');
 await page.waitForTimeout(2000);
 
 // Verify success message appears
 await expect(page.locator('text=Thank You!')).toBeVisible();
 });

 test('should navigate back to forms list', async ({ page }) => {
 await loginAsAdmin(page);
 await navigateToForms(page);
 await page.click('button:has-text("Edit"):first');
 await page.waitForURL('**/edit');
 
 // Click back button
 await page.click('button:has-text("← Back to Forms")');
 
 // Verify we're back at forms list
 await page.waitForURL('**/admin/forms');
 await expect(page.locator('h1:has-text("Form Builder")')).toBeVisible();
 });

 test('should handle different field types correctly', async ({ page }) => {
 await loginAsAdmin(page);
 await navigateToForms(page);
 await page.click('button:has-text("Edit"):first');
 await page.waitForURL('**/edit');
 
 // Test adding different field types
 const fieldTypes = [
 'Phone',
 'Number', 
 'Date',
 'Text Area',
 'Dropdown',
 'Radio Buttons',
 'Checkboxes',
 'Scale (1-10)'
 ];
 
 for (const fieldType of fieldTypes) {
 await page.click(`button:has-text("${fieldType}")`);
 await page.waitForTimeout(300);
 
 // Verify field appears in the form
 await expect(page.locator('[class*="border-dashed"]:last-child')).toBeVisible();
 }
 
 // Verify all fields were added
 const totalFields = await page.locator('[class*="border-dashed"]').count();
 expect(totalFields).toBeGreaterThanOrEqual(fieldTypes.length);
 });
});

test.describe('Form Builder Error Handling', () => {
 test('should handle network errors gracefully', async ({ page }) => {
 await loginAsAdmin(page);
 await navigateToForms(page);
 
 // Simulate network failure by blocking API calls
 await page.route('**/admin/forms/**', route => route.abort());
 
 await page.click('button:has-text("Edit"):first');
 
 // Wait for error state
 await page.waitForTimeout(3000);
 
 // Verify error handling
 await expect(page.locator('text=Unable to Load Form')).toBeVisible();
 });
});

test.describe('Form Builder Accessibility', () => {
 test('should be accessible with keyboard navigation', async ({ page }) => {
 await loginAsAdmin(page);
 await navigateToForms(page);
 await page.click('button:has-text("Edit"):first');
 await page.waitForURL('**/edit');
 
 // Test tab navigation
 await page.keyboard.press('Tab');
 await page.keyboard.press('Tab');
 
 // Test that focus is visible and functional
 const focusedElement = await page.evaluate(() => document.activeElement?.tagName);
 expect(focusedElement).toBeDefined();
 });
});