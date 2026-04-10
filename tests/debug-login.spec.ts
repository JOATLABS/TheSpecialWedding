import { test, expect } from '@playwright/test';

test.describe('Debug Login Page', () => {
  test('should load login page and capture details', async ({ page }) => {
    // Enable console logging
    page.on('console', msg => {
      console.log(`CONSOLE ${msg.type()}: ${msg.text()}`);
    });

    // Capture network requests
    page.on('request', request => {
      console.log(`REQUEST: ${request.method()} ${request.url()}`);
    });

    page.on('response', response => {
      console.log(`RESPONSE: ${response.status()} ${response.url()}`);
    });

    // Navigate to the login page
    console.log('Navigating to /admin/login...');
    await page.goto('/admin/login');

    // Wait a bit for the page to load
    await page.waitForTimeout(3000);

    // Capture basic page info
    const title = await page.title();
    const url = page.url();

    console.log(`Page Title: "${title}"`);
    console.log(`Page URL: ${url}`);

    // Check if the login form exists
    const emailInput = page.locator('input[type="email"]');
    const passwordInput = page.locator('input[type="password"]');
    const loginButton = page.locator('button:has-text("Log In")');

    console.log(`Email input exists: ${await emailInput.count() > 0}`);
    console.log(`Password input exists: ${await passwordInput.count() > 0}`);
    console.log(`Login button exists: ${await loginButton.count() > 0}`);

    // Check for the admin header text
    const adminLoginHeader = page.locator('h2:has-text("Admin Login")');
    console.log(`Admin Login header exists: ${await adminLoginHeader.count() > 0}`);

    // Take a screenshot for debugging
    await page.screenshot({ path: 'debug-login-page.png', fullPage: true });

    // Try to fill the form to see if it works
    if (await emailInput.count() > 0) {
      console.log('Attempting to fill email field...');
      await emailInput.fill('test.verification@example.com');
      console.log('Email field filled successfully');
    }

    if (await passwordInput.count() > 0) {
      console.log('Attempting to fill password field...');
      await passwordInput.fill('TestPassword123!');
      console.log('Password field filled successfully');
    }

    // Check if we can interact with the login button
    if (await loginButton.count() > 0) {
      const isButtonEnabled = await loginButton.isEnabled();
      console.log(`Login button enabled: ${isButtonEnabled}`);

      if (isButtonEnabled) {
        console.log('Clicking login button...');
        await loginButton.click();

        // Wait for navigation or error
        await page.waitForTimeout(5000);

        const newUrl = page.url();
        console.log(`URL after login attempt: ${newUrl}`);
      }
    }
  });
});
