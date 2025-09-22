import { test, expect } from '@playwright/test';
import { testConfig } from './test-config';

test.describe('Quick Feature Validation', () => {
 
 const { adminCredentials } = testConfig;

 test('Admin login functionality', async ({ page }) => {
 // Navigate to admin login
 await page.goto('/admin/login');
 
 // Wait for page to load and verify login form exists
 await expect(page.locator('text=Admin Login')).toBeVisible();
 
 // Fill login form
 await page.fill('input[type="email"]', adminCredentials.email);
 await page.fill('input[type="password"]', adminCredentials.password);
 
 // Take a screenshot to see the state
 await page.screenshot({ path: 'login-form-filled.png' });
 
 // Check if submit button is enabled
 const submitButton = page.locator('button:has-text("Log In")');
 await expect(submitButton).toBeEnabled();
 
 // Submit login
 await submitButton.click();
 
 // Wait a moment for response
 await page.waitForTimeout(3000);
 
 // Take a screenshot to see what happens
 await page.screenshot({ path: 'after-login-attempt.png' });
 
 // Check current URL to see if redirected
 const currentUrl = page.url();
 console.log('Current URL after login:', currentUrl);
 
 // Check if we're redirected to admin dashboard or if there are any errors
 if (currentUrl.includes('/admin') && !currentUrl.includes('/login')) {
 console.log(' Login successful - redirected to admin area');
 } else {
 console.log('ℹ Login form still visible - checking for errors or responses');
 }
 });

 test('Backend API connectivity', async ({ page }) => {
 // Test health endpoint
 const healthResponse = await page.request.get(`${testConfig.baseUrls.backend}/health/`);
 expect(healthResponse.status()).toBe(200);
 console.log(' Backend health check passed');
 
 // Test login API directly
 const loginResponse = await page.request.post(`${testConfig.baseUrls.backend}/admin/token`, {
 data: {
 email: adminCredentials.email,
 password: adminCredentials.password
 }
 });
 
 expect(loginResponse.status()).toBe(200);
 const loginData = await loginResponse.json();
 expect(loginData).toHaveProperty('access_token');
 console.log(' Direct API login successful');
 });

 test('Check what admin interfaces exist', async ({ page }) => {
 // Try to access various admin pages
 const adminPages = [
 '/admin',
 '/admin/forms',
 '/admin/guests', 
 '/admin/weddings',
 '/admin/saas'
 ];
 
 for (const adminPage of adminPages) {
 const response = await page.request.get(`${testConfig.baseUrls.frontend}${adminPage}`);
 console.log(`${adminPage}: ${response.status()}`);
 }
 });
});